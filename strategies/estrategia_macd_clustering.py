import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import pandas as pd
import asyncio
import ccxt.pro
import os
from dotenv import load_dotenv
from ta.momentum import RSIIndicator
import pandas_ta as ta
from scripts.gerenciamento_risco_assin import GerenciamentoRiscoAsync
from strategies.clustering import SuperTrendAIClusteringAsync
import time
from utils.binance_client import BinanceHandler

async def estrategia_macd_clustering(binance, context):
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
            posicao_max = posicao

            await context.bot.send_message(chat_id=chat_id, text=f"🔍 Analisando {symbol}...")

            # Coleta de candles
            limit = 100
            timeframe_in_ms = binance.client.parse_timeframe(timeframe) * 1000
            now = int(time.time() * 1000)  # timestamp atual em milissegundos
            since = now - (limit * timeframe_in_ms) 
            bars = await binance.client.fetch_ohlcv (symbol=symbol, since=since, timeframe= timeframe, limit=limit)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            macd = df.ta.macd(close='close', fast=12, slow=26, signal=9, append=True)
            rsi = RSIIndicator(df['close'], window=15)
            df['RSI'] = rsi.rsi()
            
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
                
                try:
                    trend, t_stop, ama = await SuperTrendAIClusteringAsync(binance, symbol, timeframe)

                    if df['RSI'].iloc[-1] >= 58 and df['RSI'].iloc[-1] <= 70:
                        if df['MACD_12_26_9'].iloc[-1] >= df['MACDs_12_26_9'].iloc[-1] and df['MACD_12_26_9'].iloc[-2] <= df['MACDs_12_26_9'].iloc[-2]:
                            if trend == 1 and t_stop > ama and side != 'short':

                                await binance.client.cancel_all_orders (symbol)

                                # suporte = float(binance.price_to_precision(symbol, t_stop))
                                stop = float(binance.client.price_to_precision(symbol, ama))
                                alvo = float(binance.client.price_to_precision(symbol, price * (1 + take_profit)))

                                # Primeira Entrada (mercado)
                                await binance.client.create_order (symbol= symbol,side= 'buy', type='MARKET',  amount =posicao , params={'hedged': 'true'})

                                # Stop
                                await binance.client.create_order (symbol= symbol,side= 'sell', type='STOP_MARKET',  amount =posicao, params={'stopPrice': stop})

                                # Take Profit
                                await binance.client.create_order (symbol=  symbol,side= 'sell', type='TAKE_PROFIT_MARKET',  amount =posicao, params={'stopPrice': alvo})

                                await context.bot.send_message(chat_id=chat_id, text=f"🚀 Abrindo *LONG* em {symbol}\n🎯 TP: {alvo}\n🛑 SL: {stop}")

                    elif df['RSI'].iloc[-1] <= 42 and df['RSI'].iloc[-1] >= 30:
                        if df['MACD_12_26_9'].iloc[-1] <= df['MACDs_12_26_9'].iloc[-1] and df['MACD_12_26_9'].iloc[-2] >= df['MACDs_12_26_9'].iloc[-2]:
                            if trend == 0 and t_stop < ama and side != 'long':

                                await binance.client.cancel_all_orders (symbol)

                                # resistencia = float(binance.price_to_precision(symbol, t_stop))
                                stop = float(binance.client.price_to_precision(symbol, ama))
                                alvo = float(binance.client.price_to_precision(symbol, price * (1 - take_profit)))

                                # Primeira Entrada (mercado)
                                await binance.client.create_order (symbol=  symbol,side= 'sell', type='MARKET', amount = posicao, params={'hedged': 'true'})

                                # Stop
                                await binance.client.create_order (symbol= symbol,side= 'buy', type='STOP_MARKET',  amount = posicao, params={'stopPrice': stop})

                                # Take Profit
                                await binance.client.create_order (symbol=  symbol,side= 'buy', type='TAKE_PROFIT_MARKET',  amount = posicao, params={'stopPrice': alvo})

                                await context.bot.send_message(chat_id=chat_id, text=f"🚀 Abrindo *SHORT* em {symbol}\n🎯 TP: {alvo}\n🛑 SL: {stop}")
                                    
                except Exception as e:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"⚠️ Erro ao calcular SuperTrendAI para {symbol}: {e}"
                    )
                    print(f"Erro no clustering de {symbol}: {e}")
                    continue  # Pula esse ativo e segue para o próximo

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Erro na estratégia MACD Clustering: {e}")

async def trading_task_macd_clustering(context):
    try:
        binance = await BinanceHandler.create()
        chat_id = context.job.chat_id
        context._chat_id = chat_id

        await estrategia_macd_clustering(binance, context)

    except Exception as e:
        await context.bot.send_message(chat_id=context.job.chat_id, text=f"❌ Erro no MACD Clustering: {e}")
    
    finally:
        await binance.close()
