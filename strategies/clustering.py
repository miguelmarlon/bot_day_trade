import asyncio
import pandas as pd
import numpy as np
import pandas_ta as ta
import time

async def SuperTrendAIClusteringAsync(binance, symbol, timeframe, atr_length=5, minMult=1, maxMult=1.8, step=0.1, perf_alpha=5, n_candles=15, max_retries=4):
    retries = 0
    while retries < max_retries:
        try:
            timeframe_in_ms = binance.parse_timeframe(timeframe) * 1000
            limit = 1500
            now = int(time.time() * 1000)  # timestamp atual em milissegundos
            since = now - (limit * timeframe_in_ms) 
            bars = await asyncio.to_thread(binance.fetch_ohlcv, symbol=symbol, since=since, timeframe=timeframe, limit=limit)
            break
        except Exception as e:
            retries += 1
            print(f"Tentativa {retries} de {max_retries} falhou: {e}")
            await asyncio.sleep(5)
            if retries == max_retries:
                print("Erro crítico: falha ao obter dados de candles.")
                return None, None, None

    df = pd.DataFrame(bars, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms', utc=True).map(lambda x: x.tz_convert('America/Sao_Paulo'))
    df['hl2'] = (df['high'] + df['low']) / 2
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=atr_length)

    fators = np.arange(minMult, maxMult + step, step)
    holder = pd.DataFrame({
        "upper": df['hl2'].iloc[0],
        "lower": df['hl2'].iloc[0],
        "output": [0] * len(fators),
        "perf": [0] * len(fators),
        "factor": fators,
        "trend": [0] * len(fators)
    })

    for i in range(atr_length, len(df)):
        row = df.iloc[i]
        prev_close = df['close'].iloc[i - 1]
        for k, factor in enumerate(fators):
            up = row['hl2'] + row['atr'] * factor
            dn = row['hl2'] - row['atr'] * factor

            upper = holder.at[k, 'upper']
            lower = holder.at[k, 'lower']
            output = holder.at[k, 'output']
            trend = holder.at[k, 'trend']
            perf = holder.at[k, 'perf']

            trend = 1 if row['close'] > upper else 0 if row['close'] < lower else trend
            upper = min(up, upper) if prev_close < upper else up
            lower = max(dn, lower) if prev_close > lower else dn

            diff = np.sign(prev_close - output)
            perf += (2 / (perf_alpha + 1)) * ((row['close'] - prev_close) * diff - perf)
            output = lower if trend == 1 else upper

            holder.at[k, 'upper'] = upper
            holder.at[k, 'lower'] = lower
            holder.at[k, 'output'] = output
            holder.at[k, 'perf'] = perf
            holder.at[k, 'trend'] = trend

    # K-means clustering manual
    data = holder['perf'].tolist()
    factor_array = holder['factor'].tolist()
    centroids = [np.percentile(data, q) for q in (25, 50, 75)]

    for _ in range(100):
        clusters = {i: [] for i in range(3)}
        factor_groups = {i: [] for i in range(3)}
        for val, fac in zip(data, factor_array):
            dists = [abs(val - c) for c in centroids]
            idx = int(np.argmin(dists))
            clusters[idx].append(val)
            factor_groups[idx].append(fac)
        new_centroids = [np.mean(clusters[i]) for i in range(3)]
        if np.allclose(new_centroids, centroids, atol=1e-5):
            break
        centroids = new_centroids

    best_cluster = int(np.argmax(centroids))
    if not clusters[best_cluster]:
        raise ValueError("Clusters inválidos.")

    target_factor = np.mean(factor_groups[best_cluster])
    den = df['close'].diff().abs().ewm(span=perf_alpha).mean().iloc[-1]
    perf_idx = max(np.mean(clusters[best_cluster]), 0) / den

    # Cálculo final de tendência + stop + AMA
    trend_final = None
    upper = lower = None
    ts_list = []
    for i in range(-n_candles, 0):
        row = df.iloc[i]
        up = row['hl2'] + row['atr'] * target_factor
        dn = row['hl2'] - row['atr'] * target_factor

        if i == -n_candles:
            upper = up
            lower = dn
        else:
            upper = min(up, upper) if df['close'].iloc[i - 1] < upper else up
            lower = max(dn, lower) if df['close'].iloc[i - 1] > lower else dn

        trend_final = 1 if row['close'] > upper else 0 if row['close'] < lower else trend_final
        ts = lower if trend_final == 1 else upper
        ts_list.append(ts)

        if i == -n_candles:
            ama = ts
        else:
            ama += perf_idx * (ts - ama)

    return trend_final, ts_list[-1], ama
