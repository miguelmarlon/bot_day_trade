import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import pandas as pd
import asyncio
from scripts.gerenciamento_risco_assin import GerenciamentoRiscoAsync
from scripts.binance_server import BinanceHandler
import asyncio
import time
import ccxt.pro

async def estrategia_rompimento_eth_altcoins(binance, context):
    try:
        symbol = 'ETH/USDT'
        limit = 100
        timeframe = context.chat_data.get('timeframe_operacao_rompimento', '15m')
        chat_id = context.job.chat_id if hasattr(context, 'job') else context._chat_id
        timeframe_in_ms = binance.parse_timeframe(timeframe) * 1000
        now = int(time.time() * 1000)  # timestamp atual em milissegundos
        since = now - (limit * timeframe_in_ms) 
        bars = await binance.fetch_ohlcv (symbol=symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(bars, columns=['timestamp', 'abertura', 'max', 'min', 'fechamento', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).map(lambda x: x.tz_convert('America/Sao_Paulo'))

        suporte = df['min'].rolling(window=50).min().iloc[-2]
        resistencia = df['max'].rolling(window=50).max().iloc[-2]
        eth_price = await binance.fetch_trades (symbol)[-1]['price']

        alt_coins = pd.read_csv('cripto_tamanho_rompimento.csv')  # ajuste o caminho se necessário
        alt_coins.dropna(inplace=True)

        # alt_coins = {'LINK/USDT': 20, 'CHZ/USDT': 3000, '1000SHIB/USDT': 15000, 'MATIC/USDT': 800, 'TIA/USDT': 50}
        stop_loss = 0.03
        take_profit = 0.06

        rompimento = None
        if eth_price > resistencia:
            rompimento = 'long'
        elif eth_price < suporte:
            rompimento = 'short'

        if not rompimento:
            await context.bot.send_message(chat_id=chat_id, text="ℹ️ ETH ainda dentro do range.")
            return

        await context.bot.send_message(chat_id=chat_id, text=f"📢 ETH rompeu {'RESISTÊNCIA' if rompimento == 'long' else 'SUPORTE'}!\n🔍 Buscando altcoin atrasada...")

        entrada = 'buy' if rompimento == 'long' else 'sell'
        saida = 'sell' if rompimento == 'long' else 'buy'

        coinData = {}
        for _, row in alt_coins.iterrows():
            coin = row['symbol']
            alt_price = await binance.fetch_trades (coin)[-1]['price']
            coinData[coin] = abs((alt_price - eth_price) / eth_price) * 100

        most_lagging = min(coinData, key=coinData.get)
        pos = alt_coins.loc[alt_coins['symbol'] == most_lagging, 'tamanho'].values[0]
        alt_price = await binance.fetch_trades (most_lagging)[-1]['price']
        alt_price = float(binance.price_to_precision(most_lagging, alt_price))

        stop = alt_price * (1 - stop_loss) if rompimento == 'long' else alt_price * (1 + stop_loss)
        target = alt_price * (1 + take_profit) if rompimento == 'long' else alt_price * (1 - take_profit)
        stop = float(binance.price_to_precision(most_lagging, stop))
        target = float(binance.price_to_precision(most_lagging, target))

        async with GerenciamentoRiscoAsync() as gr:
            if not await gr.posicao_max(most_lagging, pos):
                await binance.cancel_all_orders (most_lagging)
                await binance.create_order,symbol= most_lagging (side=entrada, type= 'MARKET', amount= pos, params= {'hedged': 'true'})
                await binance.create_order,symbol= most_lagging (side=saida, type='STOP_MARKET', amount= pos, params=  {'stopPrice': stop})
                await binance.create_order,symbol= most_lagging (side=saida, type= 'TAKE_PROFIT_MARKET', amount=pos,params=  {'stopPrice': target})

                await context.bot.send_message(chat_id=chat_id, text=f"✅ Entrada em {most_lagging} ({rompimento.upper()})\n🎯 TP: {target:.4f} | 🛑 SL: {stop:.4f}")
            else:
                await context.bot.send_message(chat_id=chat_id, text=f"🔒 Já há posição máxima aberta em {most_lagging}.")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Erro na estratégia ETH/Altcoins: {e}")


async def trading_task_rompimento(context):
    try:
        binance = await BinanceHandler.create()
        chat_id = context.job.chat_id
        context._chat_id = chat_id

        await estrategia_rompimento_eth_altcoins(binance, context)

    except Exception as e:
        await context.bot.send_message(chat_id=context.job.chat_id, text=f"❌ Erro no rompimento ETH/Altcoins: {e}")
