import ccxt.pro
import pandas as pd
import numpy as np
from scipy.stats import norm
import asyncio
from scripts.binance_server import BinanceHandler

async def rodar_diagnostico_tail1(symbol='BTC/USDT', timeframe='1h', window_size=100, holding_periods=[8], acf_threshold=0.03):
    # Inicializa Binance
    binance = await BinanceHandler.create()

    # Função assíncrona para puxar os candles
    candles = await binance.fetch_ohlcv (symbol, timeframe, None, 1500)

    # Transforma em DataFrame
    df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    returns = df['close'].pct_change().dropna()

    # --- Funções auxiliares ---
    def variance_ratio_rolling(returns, q, window):
        var_1 = returns.rolling(window).var()
        sum_q = returns.rolling(q).sum()
        var_q = sum_q.rolling(window).var()
        vr = var_q / (q * var_1)
        T = window
        var_vr = (2 * (2 * q - 1) * (q - 1)) / (3 * q * T)
        z_score = (vr - 1) / np.sqrt(var_vr)
        p_value = 2 * (1 - norm.cdf(np.abs(z_score)))
        return vr, p_value

    def rolling_avg_autocorr(series, max_lag, window):
        def avg_acorr(x):
            return np.mean([pd.Series(x).autocorr(lag=i) for i in range(1, max_lag + 1)])
        return series.rolling(window).apply(avg_acorr, raw=False)

    def gerar_diagnostico_previsibilidade(vr_data, acf_data, pval_data):
        diagnosticos = []
        vr_cols = [col for col in vr_data.columns if col.startswith('VR_')]
        pval_cols = [col for col in pval_data.columns if col.startswith('PVal_')]
        common_periods = [col.split('_')[1] for col in vr_cols if f'PVal_{col.split("_")[1]}' in pval_cols]

        for i in range(len(vr_data)):
            regime_detectado = []
            index = vr_data.index[i]

            for period in common_periods:
                vr = vr_data.get(f'VR_{period}', pd.Series(index=vr_data.index)).iloc[i]
                if pd.notna(vr):
                    if vr > 1.05:
                        regime_detectado.append('momentum')
                    elif vr < 0.95:
                        regime_detectado.append('reversão')

            acf_val = acf_data.iloc[i]
            if pd.notna(acf_val):
                if acf_val > acf_threshold:
                    regime_detectado.append('momentum (ACF)')
                elif acf_val < -acf_threshold:
                    regime_detectado.append('reversão (ACF)')

            if 'momentum' in regime_detectado and 'reversão' not in regime_detectado:
                regime = 'MOMENTUM'
            elif 'reversão' in regime_detectado and 'momentum' not in regime_detectado:
                regime = 'REVERSÃO À MÉDIA'
            elif 'momentum' in regime_detectado and 'reversão' in regime_detectado:
                regime = 'CONFLITO de sinais: Momentum e Reversão'
            else:
                regime = 'Regime INDEFINIDO ou aleatório'

            diagnosticos.append({'timestamp': index, 'regime': regime})

        return pd.DataFrame(diagnosticos).set_index('timestamp')

    # --- Cálculo de métricas ---
    vr_data = pd.DataFrame(index=returns.index)
    pval_data = pd.DataFrame(index=returns.index)
    for q in holding_periods:
        vr, pval = variance_ratio_rolling(returns, q, window_size)
        vr_data[f'VR_{q}'] = vr
        pval_data[f'PVal_{q}'] = pval

    acf_avg = rolling_avg_autocorr(returns, max_lag=3, window=window_size)
    diagnostico_df = gerar_diagnostico_previsibilidade(vr_data, acf_avg, pval_data)

    return diagnostico_df.tail(1)


