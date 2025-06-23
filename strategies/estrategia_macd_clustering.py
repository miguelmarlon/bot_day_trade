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

        for _, row in df_config.iterrows():
            symbol = row['symbol']
            await asyncio.sleep(2) 
            posicao = row['tamanho']
            posicao_max = posicao

            await context.bot.send_message(chat_id=chat_id, text=f"🔍 Analisando {symbol}...")

            # Coleta de candles
            limit = 100
            timeframe_in_ms = binance.parse_timeframe(timeframe) * 1000
            now = int(time.time() * 1000)  # timestamp atual em milissegundos
            since = now - (limit * timeframe_in_ms) 
            bars = await binance.fetch_ohlcv (symbol=symbol, since=since, timeframe= timeframe, limit=limit)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            # Indicadores
            # df['EMA_9'] = ta.ema(df['close'], length=9)
            # df['EMA_21'] = ta.ema(df['close'], length=21)
            # df['EMA_50'] = ta.ema(df['close'], length=50)

            macd = df.ta.macd(close='close', fast=12, slow=26, signal=9, append=True)
            rsi = RSIIndicator(df['close'], window=15)
            df['RSI'] = rsi.rsi()

            # tendencia_alta = df['close'].iloc[-1] >= df['EMA_50'].iloc[-1] and df['EMA_9'].iloc[-1] > df['EMA_21'].iloc[-1]
            # tendencia_baixa = df['close'].iloc[-1] <= df['EMA_50'].iloc[-1] and df['EMA_9'].iloc[-1] <= df['EMA_21'].iloc[-1]

            # price = await binance.fetch_trades (symbol)[-1]['price']
            # price = float(binance.price_to_precision(symbol, price))
            
            try:
                trades = await binance.fetch_trades (symbol)
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
                        price_str = binance.price_to_precision(symbol, price_raw)
                        price = float(price_str)
            except Exception as e:
                print(f"[ERRO] Falha ao obter ou formatar o preço para {symbol}: {e}")
                context.bot.send_message(
                                chat_id=chat_id,
                                text=f"⚠️ [ERRO] Falha ao obter ou formatar o preço para {symbol}: {e}"
                            )
                price = None
            async with GerenciamentoRiscoAsync as gr:
                side, _, _, is_open, _, _, _ = await gr.posicoes_abertas(symbol)
                tem_ordem_aberta = await gr.ultima_ordem_aberta(symbol)

                if not await gr.posicao_max(symbol, posicao_max) and not tem_ordem_aberta:
                    
                    try:
                        trend, t_stop, ama = await SuperTrendAIClusteringAsync(binance, symbol, timeframe)

                        if df['RSI'].iloc[-1] >= 58 and df['RSI'].iloc[-1] <= 70:
                            if df['MACD_12_26_9'].iloc[-1] >= df['MACDs_12_26_9'].iloc[-1] and df['MACD_12_26_9'].iloc[-2] <= df['MACDs_12_26_9'].iloc[-2]:
                                if trend == 1 and t_stop > ama and side != 'short':

                                    await binance.cancel_all_orders (symbol)

                                    # suporte = float(binance.price_to_precision(symbol, t_stop))
                                    stop = float(binance.price_to_precision(symbol, ama))
                                    alvo = float(binance.price_to_precision(symbol, price * (1 + take_profit)))

                                    # Primeira Entrada (mercado)
                                    await binance.create_order (symbol= symbol,side= 'buy', type='MARKET',  amount =posicao , params={'hedged': 'true'})

                                    # Segunda Entrada (limit)
                                    # await binance.create_order (symbol= symbol,side= 'buy', type='LIMIT',  amount =posicao / 2, suporte, params={'hedged': 'true'})

                                    # Stop
                                    await binance.create_order (symbol= symbol,side= 'sell', type='STOP_MARKET',  amount =posicao, params={'stopPrice': stop})

                                    # Take Profit
                                    await binance.create_order (symbol=  symbol,side= 'sell', type='TAKE_PROFIT_MARKET',  amount =posicao, params={'stopPrice': alvo})

                                    await context.bot.send_message(chat_id=chat_id, text=f"🚀 Abrindo *LONG* em {symbol}\n🎯 TP: {alvo}\n🛑 SL: {stop}")

                        elif df['RSI'].iloc[-1] <= 42 and df['RSI'].iloc[-1] >= 30:
                            if df['MACD_12_26_9'].iloc[-1] <= df['MACDs_12_26_9'].iloc[-1] and df['MACD_12_26_9'].iloc[-2] >= df['MACDs_12_26_9'].iloc[-2]:
                                if trend == 0 and t_stop < ama and side != 'long':

                                    await binance.cancel_all_orders (symbol)

                                    # resistencia = float(binance.price_to_precision(symbol, t_stop))
                                    stop = float(binance.price_to_precision(symbol, ama))
                                    alvo = float(binance.price_to_precision(symbol, price * (1 - take_profit)))

                                    # Primeira Entrada (mercado)
                                    await binance.create_order (symbol=  symbol,side= 'sell', type='MARKET', amount = posicao, params={'hedged': 'true'})

                                    # Segunda Entrada (limit)
                                    # await binance.create_order (symbol=  symbol,side= 'sell', type='LIMIT', amount = posicao / 2, resistencia, params={'hedged': 'true'})

                                    # Stop
                                    await binance.create_order (symbol= symbol,side= 'buy', type='STOP_MARKET',  amount = posicao, params={'stopPrice': stop})

                                    # Take Profit
                                    await binance.create_order (symbol=  symbol,side= 'buy', type='TAKE_PROFIT_MARKET',  amount = posicao, params={'stopPrice': alvo})

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
