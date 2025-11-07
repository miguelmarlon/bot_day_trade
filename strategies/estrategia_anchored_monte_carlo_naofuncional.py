import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import numpy as np
import pandas as pd
from utils.binance_client import BinanceHandler
import time
import pandas_ta as ta
import asyncio
from scripts.backtest import calcular_retorno_sinais
import pandas_ta as ta
from scripts.gerenciamento_risco_assin import GerenciamentoRiscoAsync

async def estrategia_anchored_monte_carlo(binance,
                                          symbol,
                                          context,
                                          timeframe='15min', 
                                          lookback_bars = 60,
                                          simulation_count = 500, 
                                          forecast_horizon = 30, 
                                          randomize_direction = True
                                          ):
    try:
        chat_id = context.job.chat_id if hasattr(context, 'job') else context._chat_id

        timeframe = context.chat_data.get('timeframe_operacao_macd', '4h')
        take_profit = 0.04

        df_config = pd.read_csv('config/cripto_tamanho_macd.csv') 
        df_config.dropna(inplace=True)

        gerenciador_risco = GerenciamentoRiscoAsync(binance_handler=binance)

        for _, row in df_config.iterrows():
            symbol = row['symbol']
            await asyncio.sleep(2) 
            posicao = row['tamanho']
            operacao = row['acao']
            posicao_max = posicao
            
            binance.client.set_leverage(10, symbol)
            binance.client.set_margin_mode("ISOLATED", symbol)
            await context.bot.send_message(chat_id=chat_id, text=f"🔍 Analisando {symbol}...")

            # Coleta de candles
            limit = 1500
            timeframe_in_ms = binance.client.parse_timeframe(timeframe) * 1000
            now = int(time.time() * 1000)

            required_bars = lookback_bars + forecast_horizon + 100 
            since = now - (required_bars * timeframe_in_ms)

            print(f"Coletando dados para {symbol} no timeframe {timeframe} desde {pd.to_datetime(since, unit='ms')}...")
            bars = await binance.client.fetch_ohlcv(symbol=symbol, since=since, timeframe=timeframe, limit=limit)
            data = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

            try:
                trades = await binance.client.fetch_trades (symbol)
                if not trades:
                    print(f"[AVISO] Nenhum trade recente encontrado para {symbol}")
                    price = None
                else:
                    last_trade = trades[-1]
                    if 'price' not in last_trade or last_trade['price'] is None:
                        print(f"[AVISO] Último trade de {symbol} não possui preço válido.")
                        price = None
                    else:
                        price_raw = last_trade['price']
                        price_str = binance.client.price_to_precision(symbol, price_raw)
                        price = float(price_str)
            except Exception as e:
                print(f"[ERRO] Falha ao obter ou formatar o preço para {symbol}: {e}")
                context.bot.send_message(
                                chat_id=chat_id,
                                text=f"⚠️ [ERRO] Falha ao obter ou formatar o preço para {symbol}: {e}"
                            )
                price = None
            
            side, _, _, is_open, _, _, _ = await gerenciador_risco.posicoes_abertas(symbol)
            tem_ordem_aberta = await gerenciador_risco.ultima_ordem_aberta(symbol)

            if not await gerenciador_risco.posicao_max(symbol, posicao_max) and not tem_ordem_aberta:

                if len(data) < lookback_bars + forecast_horizon:
                    print(f"Erro: Não há dados suficientes para realizar o backtest. "
                        f"Dados coletados: {len(data)}, Mínimo necessário: {lookback_bars + forecast_horizon}")
                        
                    return pd.DataFrame()

                data['RSI'] = ta.rsi(data['close'], length=14)
                
                if len(data) < forecast_horizon + lookback_bars:
                    print("Erro: Dados insuficientes para realizar a operação Anchored Monte Carlo.")
                    return pd.DataFrame()

                data['upper_band_proj'] = np.nan
                data['lower_band_proj'] = np.nan
                # data['sinal'] = np.nan

                for i in range(lookback_bars, len(data) - forecast_horizon):

                    janela_lookback = data['close'].iloc[i - lookback_bars : i] 
                    current_price = data['close'].iloc[i] 

                    historical_changes = janela_lookback.pct_change().dropna().values

                    if len(historical_changes) == 0:
                        print(f"Aviso: Não há mudanças históricas suficientes na barra {i} para gerar mudanças. Pulando esta iteração.")
                        continue
                    
                    simulated_paths = np.zeros((forecast_horizon, simulation_count))
                    
                    for j in range(simulation_count):
                        changes_for_this_simulation = historical_changes.copy()

                        if randomize_direction:
                    
                            changes_for_this_simulation[1::2] *= -1 
                        
                        np.random.shuffle(changes_for_this_simulation)

                        path = np.zeros(forecast_horizon)
                        if len(changes_for_this_simulation) > 0:

                            path[0] = current_price * (1 + changes_for_this_simulation[0])
                        else:
                            
                            path[0] = current_price

                        for t in range(1, forecast_horizon):
                            
                            change = changes_for_this_simulation[t % len(changes_for_this_simulation)] if len(changes_for_this_simulation) > 0 else 0
                            path[t] = path[t-1] * (1 + change)

                        simulated_paths[:, j] = path

                    final_prices_at_horizon = simulated_paths[forecast_horizon - 1, :] 
                    
                    avg_final_price = np.mean(final_prices_at_horizon)
                    std_final_price = np.std(final_prices_at_horizon)

                    upper_band_proj = avg_final_price + std_final_price 
                    lower_band_proj = avg_final_price - std_final_price 

                    rsi_atual = data['RSI'].iloc[i]
                    low_price = data['low'].iloc[-1]
                    high_price = data['high'].iloc[-1]

                    # sinal = 0 

                    if low_price < lower_band_proj and 25 <= rsi_atual <= 50:
                        if side != 'short' and current_price < lower_band_proj:
                        
                            print(f"📈 Sinal de COMPRA detectado em {symbol} na barra {i} (RSI: {rsi_atual}, Preço: {current_price})")
                            await context.bot.send_message(chat_id=chat_id, text=f"📈 Sinal de COMPRA detectado em {symbol} (Preço: {current_price})")
                            await binance.abrir_long(symbol, posicao_max, context)

                    elif high_price > upper_band_proj and 50 <= rsi_atual <= 75:
                        if side != 'long' and current_price > upper_band_proj:
                        
                            print(f"📉 Sinal de VENDA detectado em {symbol} na barra {i} (RSI: {rsi_atual}, Preço: {current_price})")
                            await context.bot.send_message(chat_id=chat_id, text=f"📉 Sinal de VENDA detectado em {symbol} (Preço: {current_price})")
                            await binance.abrir_short(symbol, posicao_max, context)

                    # data.loc[data.index[i], 'upper_band_proj'] = upper_band_proj
                    # data.loc[data.index[i], 'lower_band_proj'] = lower_band_proj
                    # data.loc[data.index[i], 'sinal'] = sinal

                    # if i % 100 == 0:
                    #     print(f"Processando barra {i}/{len(data) - forecast_horizon - 1}...")

                return data

    except Exception as e:
        print(f"Erro na estratégia Anchored Monte Carlo: {e}")
        return pd.DataFrame() 

async def main():
    timeframes = ['1min', '5min', '15min', '30min', '60min']
    try:
        binance = await BinanceHandler.create()
        for timeframe in timeframes:
            df = await estrategia_anchored_monte_carlo(binance=binance, timeframe=timeframe, symbol='BTC/USDT', csv=True)

            df.to_csv(f'outputs/data/analise_montecarlo/conf_agressiva/sinais_monte_carlo_{timeframe}_rsi_agressivo.csv', index=False)

            if df is not None:
                retorno = calcular_retorno_sinais(df, horizontes=[5, 10, 20, 30, 60, 120, 240])
                retorno.to_csv(f'outputs/data/analise_montecarlo/conf_conservadora/calculo_retorno_monte_carlo_{timeframe}_rsi_agressivo.csv', index=False)
            else:
                print("Nenhum dado retornado da estratégia Anchored Monte Carlo.")

    except Exception as e:
        print(f"Erro na estratégia Anchored Monte Carlo: {e}")
    finally:
        await binance.close_connection()

if __name__ == "__main__":
    asyncio.run(main())