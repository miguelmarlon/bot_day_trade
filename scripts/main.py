import logging
import os
from dotenv import load_dotenv
import pandas as pd
from sentiment_analyzer import analisar_sentimento_openrouter, gerar_resumo
from information_tools import get_economic_events_async, buscar_noticias_google
from technical_analysis import calcular_indicadores, verificar_long_btc_1m, verificar_short_btc_1m, verificar_long, verificar_short
import numpy as np
from gerenciamento_risco_assin import GerenciamentoRiscoAsync
from strategies.clustering import SuperTrendAIClusteringAsync
from strategies.estrategia_macd_clustering import trading_task_macd_clustering
from strategies.estrategia_rompimento import trading_task_rompimento
from utils.binance_client import conectar_binance, obter_dados_candles, cancelar_todas_as_ordens, abrir_long, abrir_short
from config.config import TELEGRAM_TOKEN
from prediction_model import treina_modelo, predict

# load_dotenv()
# api_key = os.getenv("BINANCE_API_KEY")
# api_secret = os.getenv("BINANCE_SECRET_KEY")
# TELEGRAM_TOKEN = os.getenv("TOKEN")
# client = os.getenv("OPENAI_API_KEY")

# async def conectar_binance():
#     exchange = ccxt.binance({
#         'enableRateLimit': True,
#         'apiKey': api_key,
#         'secret': api_secret,
#         'options': {'defaultType': 'future'}
#     })
#     return exchange

# async def obter_dados_candles(binance, symbol, timeframe='1h', limit=300):
#     timeframe_in_ms = binance.parse_timeframe(timeframe) * 1000
#     now = int(time.time() * 1000)  
#     since = now - (limit * timeframe_in_ms) 
#     bars = await asyncio.to_thread(binance.fetch_ohlcv, since=since, symbol=symbol, timeframe=timeframe, limit=limit)
#     df_candles = pd.DataFrame(bars, columns=['time', 'abertura', 'max', 'min', 'fechamento', 'volume'])
#     df_candles['time'] = pd.to_datetime(df_candles['time'], unit='ms', utc=True).map(lambda x: x.tz_convert('America/Sao_Paulo'))
#     return df_candles

# def calcular_indicadores(df_candles):
#     rsi = RSIIndicator(df_candles['fechamento'], window=14)
#     df_candles['RSI'] = rsi.rsi()
#     macd = df_candles.ta.macd(close='fechamento', fast=12, slow=26, signal=9, append=True)
#     df_candles['EMA_20'] = ta.ema(df_candles['fechamento'], length=20)
#     df_candles['EMA_50'] = ta.ema(df_candles['fechamento'], length=50)
#     df_candles['EMA_200'] = ta.ema(df_candles['fechamento'], length=200)
#     df_candles['ATR'] = ta.atr(df_candles['max'], df_candles['min'], df_candles['fechamento'], length=14)
#     df_candles['CCI'] = ta.cci(df_candles['max'], df_candles['min'], df_candles['fechamento'], length=20)
#     df_candles['WILLIAMS_R'] = ta.willr(df_candles['max'], df_candles['min'], df_candles['fechamento'], length=14)
#     df_candles['Momentum'] = ta.mom(df_candles['fechamento'], length=10)
#     df_candles.bfill(inplace=True)  
#     df_candles.ffill(inplace=True) 
#     df_candles.dropna(inplace=True)
#     return df_candles

# def treina_modelo(df_candles):
#     df_candles['indice'] = np.arange(len(df_candles))
#     features = ['indice', 'RSI', 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9', 'EMA_50', 'EMA_200', 'ATR', 'CCI', 'WILLIAMS_R', 'Momentum']
#     x = df_candles[features].values[:-1]
#     y = df_candles['fechamento'].values[1:]

#     scaler = StandardScaler()
#     x_norm = scaler.fit_transform(x)
#     model = XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42)
#     model.fit(x_norm, y)
#     return model, scaler

# def predict(df_candles, model, scaler):
#     features = ['indice', 'RSI', 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9', 'EMA_50', 'EMA_200', 'ATR', 'CCI', 'WILLIAMS_R', 'Momentum']
#     ultimo_candle = df_candles[features].iloc[-1].values.reshape(1, -1)
#     ultimo_candle_norm = scaler.transform(ultimo_candle)
#     preco_futuro = model.predict(ultimo_candle_norm)[0]
#     return preco_futuro

# def verificar_long_btc_1m(df_candles):
#     rsi = df_candles['RSI'].iloc[-1]
#     candle_alta = df_candles['fechamento'].iloc[-1] > df_candles['abertura'].iloc[-1]
#     return rsi <= 15 and candle_alta

# def verificar_short_btc_1m(df):
#     rsi = df['RSI'].iloc[-1]
#     candle_baixa = df['fechamento'].iloc[-1] < df['abertura'].iloc[-1]
#     return rsi >= 85 and candle_baixa

# def verificar_long(df_candles):
#     """Verifica as condições para abrir uma posição LONG"""
#     if df_candles.iloc[-1]['RSI'] > 40 and df_candles.iloc[-1]['RSI'] < 75 and df_candles.iloc[-1]['EMA_20'] >= df_candles.iloc[-1]['fechamento']:
#         if df_candles.iloc[-1]['MACD_12_26_9'] >= df_candles.iloc[-1]['MACDs_12_26_9'] and df_candles.iloc[-2]['MACD_12_26_9'] <= df_candles.iloc[-2]['MACDs_12_26_9']:
#             return True   
#     return False
        
# def verificar_short(df_candles):
#     """Verifica as condições para abrir uma posição SHORT"""
#     if df_candles.iloc[-1]['RSI'] < 60 and df_candles.iloc[-1]['RSI'] > 30 and df_candles.iloc[-1]['EMA_20'] <= df_candles.iloc[-1]['fechamento']:
#         if df_candles.iloc[-1]['MACD_12_26_9'] <= df_candles.iloc[-1]['MACDs_12_26_9'] and df_candles.iloc[-2]['MACD_12_26_9'] >= df_candles.iloc[-2]['MACDs_12_26_9']:
#             return True   
#     return False    

# async def cancelar_todas_as_ordens(binance, symbol, context):
#     async with GerenciamentoRiscoAsync() as gr:
#         if await gr.ultima_ordem_aberta(symbol):
#             try:
#                 await asyncio.to_thread(binance.cancel_all_orders(symbol))
#                 await context.bot.send_message(
#                     chat_id=context.job.chat_id,
#                     text=f"\u26d4 Todas as ordens canceladas para {symbol}.",
#                     parse_mode="Markdown"
#                 )
#             except Exception as e:
#                 await context.bot.send_message(
#                     chat_id=context.job.chat_id,
#                     text=f"Erro ao cancelar ordens em {symbol}: {e}",
#                     parse_mode="Markdown"
#                 )

# async def abrir_long(binance, symbol, posicao_max, context):
#     async with GerenciamentoRiscoAsync() as gr:
#         try:
#             bid, ask = await gr.livro_ofertas(symbol)
#             bid = binance.price_to_precision(symbol, bid)
            
#             await asyncio.to_thread(
#                 binance.create_order,
#                 symbol,
#                 side='buy',
#                 type='LIMIT',
#                 amount=posicao_max,
#                 price=bid,
#                 params={'hedged': 'true', 'postOnly': True}
#             )
            
#             print("***** Executando Ordem de Compra - Long *****")
#             msg = (
#                 f"✅**Ordem de Compra (Long) Enviada!**\n"
#                 f"🔹**Par de Mercado:** {symbol}\n"
#                 f"🔹**Tipo de Ordem:** LIMIT\n"
#                 f"💲**Preço de Entrada:** {bid}\n"
#                 f"📊**Quantidade:** {posicao_max} {symbol.split('/')[0]}"
#             )
#         except Exception as e:
#             print(f"**** Problema ao abrir long! Erro: {e} ****")
#             msg = f"❌ Erro ao abrir long em {symbol}: {e}"

#         await context.bot.send_message(chat_id=context.job.chat_id, text=msg, parse_mode="Markdown")

# async def abrir_short(binance, symbol, posicao_max, context):
#     async with GerenciamentoRiscoAsync() as gr:
#         try:
#             bid, ask = await gr.livro_ofertas(symbol)
#             ask =  binance.price_to_precision(symbol, ask)
#             await asyncio.to_thread(
#                 binance.create_order,
#                 symbol, 
#                 side='sell', 
#                 type='LIMIT', 
#                 price=ask,
#                 amount=posicao_max,
#                 params={'hedged': 'true', 'postOnly': True}
#             )
#             print("***** Executando Ordem de Venda - Short *****")
#             msg = (
#                 f"✅**Ordem de Venda (Short) Enviada!**\n"
#                 f"🔹**Par de Mercado:** {symbol}\n"
#                 f"🔹**Tipo de Ordem:** LIMIT\n"
#                 f"💲**Preço de Entrada:** {ask}\n"
#                 f"📊**Quantidade:** {posicao_max} {symbol.split('/')[0]}"
#             )
#         except Exception as e:
#             print(f"**** Problema ao abrir short! Erro: {e} ****")
#             msg = f"❌ Erro ao abrir short em {symbol}: {e}"

#         await context.bot.send_message(chat_id=context.job.chat_id, text=msg, parse_mode="Markdown")

import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext
import asyncio

# Configuração básica de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: CallbackContext):
    """Handler do comando /start"""
    await update.message.reply_text(
        "👋 Olá! Eu sou o seu *Trading System*!\n\n"
        "Comandos disponíveis:\n"
        "▫️ /operarXGB [timeframe] – Inicia o bot com candles de 1h, 2h, etc\n"
        "▫️ /pararXGB – Interrompe o bot\n"
        "▫️ /operar1mBTC – Inicia o bot scalper no 1m\n"
        "▫️ /parar1mBTC – Interrompe o bot\n"
        "▫️ /operarROMPIMENTO – Inicia o bot correlação ETH\n"
        "▫️ /pararROMPIMENTO – Interrompe o bot correlação ETH\n"
        "▫️ /operarMACD – Inicia o bot da estratégia de MACD + Clustering ETH\n"
        "▫️ /pararMACD – Interrompe o bot da estratégia de MACD + Clustering\n"              
        "▫️ /regime [timeframe] – Diagnóstico do regime de mercado\n"
        "▫️ /estrategias – Exibe a lógica das estratégias disponíveis\n"
        "▫️ /supertrend [cripto] [timeframe] – Clustering Supertrend\n"
        "▫️ /eventos Eventos macroeconômicos relevantes do dia"
        "▫️ /noticias Classificador de notícias",
        parse_mode='Markdown'
    )

# FUNÇÕES DE INICIAR !!

async def iniciar_macd(update: Update, context: CallbackContext):
    tf = context.args[0] if context.args else '4h'
    
    # Validação dos timeframes permitidos
    timeframes_validos = ['1h', '2h', '4h']
    if tf not in timeframes_validos:
        await update.message.reply_text(
            "⛔ Timeframe inválido. Escolha entre: 1h, 2h ou 4h."
        )
        return

    # Extrair o número do timeframe (ex.: '4h' -> 4)
    horas = int(tf.replace('h', ''))

    # Salva o timeframe no contexto
    context.chat_data['timeframe_operacao'] = tf

    # Cancela job anterior se existir
    for job in context.job_queue.jobs():
        if job.name == "macd_job":
            job.schedule_removal()

    # Cria o novo job
    context.job_queue.run_repeating(
        trading_task_macd_clustering,
        interval=60 * 60 * horas,  # segundos * minutos * horas
        first=5,
        chat_id=update.effective_chat.id,
        name="macd_job"
    )

    await update.message.reply_text(
        f"✅ Estratégia MACD Clustering ativada! TF = {tf}",
        parse_mode="Markdown"
    )

async def iniciar_rompimento(update: Update, context: CallbackContext):
    try:
        tf = context.args[0] if context.args else '15m'
        context.chat_data['timeframe_operacao'] = tf

        for job in context.job_queue.jobs():
            if job.name == "rompimento_job":
                job.schedule_removal()

        context.job_queue.run_repeating(
            trading_task_rompimento,
            interval=60.0,  # por exemplo, a cada 1 minuto
            first=5,
            chat_id=update.effective_chat.id,
            name="rompimento_job"
        )

        await update.message.reply_text(f"✅ Estratégia *ROMPIMENTO ETH/Altcoins* ativada! TF = {tf}", parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao iniciar estratégia de rompimento: {e}")

async def iniciar_bot(update: Update, context: CallbackContext):
    """Handler do comando /operar com suporte a timeframe"""
    try:
        # Lê o argumento (ex: /operar 2h)
        tf = context.args[0] if context.args else '1h'

        # Timeframes válidos
        timeframes_validos = ['1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d']
        if tf not in timeframes_validos:
            await update.message.reply_text(f"⛔ Timeframe inválido: {tf}\nEscolha entre: {', '.join(timeframes_validos)}")
            return

        # Salva o timeframe por chat
        context.chat_data['timeframe_operacao'] = tf

        # Remove jobs antigos
        for job in context.job_queue.jobs():
            if job.name == "trading_job":
                job.schedule_removal()

        # Inicia o novo job
        context.job_queue.run_repeating(
            trading_task,
            interval=20.0,
            first=5,
            chat_id=update.effective_chat.id,
            name="trading_job"
        )

        await update.message.reply_text(f"✅ Bot XGB iniciado com *timeframe {tf}*!", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Erro ao iniciar bot: {e}")
        await update.message.reply_text(f"❌ Erro ao iniciar: {str(e)}")

async def iniciar_bot_simples(update: Update, context: CallbackContext):
    try:
        tf = '1m'
        context.chat_data['timeframe_operacao_simples'] = tf

        # Remove tarefas antigas desse bot
        for job in context.job_queue.jobs():
            if job.name == "btc_simples_job":
                job.schedule_removal()

        context.job_queue.run_repeating(
            trading_task_btc_1m,
            interval=18.0,
            first=5,
            chat_id=update.effective_chat.id,
            name="btc_simples_job"
        )

        await update.message.reply_text(f"🚀 Estratégia BTC 1m Scalper ativada! TF = {tf}", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Erro ao iniciar bot simples: {e}")
        await update.message.reply_text(f"❌ Erro ao iniciar bot simples: {str(e)}")

# FUNÇÕES DE ESTRATÉGIAS DIRETAS - NÃO IMPORT !
async def trading_task(context):
    async with GerenciamentoRiscoAsync() as gr:
        try:
            chat_id = context.job.chat_id
            await context.bot.send_message(chat_id=chat_id, text="⏳ Executando análise de mercado...")

            df_config = pd.read_csv('config/cripto_tamanho_xgb.csv')  # 15 dolares com 10x
            df_config.dropna(inplace=True)

            timeframe = context.chat_data.get('timeframe_operacao', '1h')
            binance = await conectar_binance()

            for _, row in df_config.iterrows():
                symbol = row['symbol']
                posicao_max = row['tamanho']

                await gr.fecha_pnl(symbol, loss=-25, target=50)
                await cancelar_todas_as_ordens(binance, symbol, context)

                df = await obter_dados_candles(binance, symbol, timeframe=timeframe)
                df = calcular_indicadores(df)
                #print(df)

                if not await gr.posicao_max(symbol, posicao_max):
                    side, amount, _, is_open, _, _, _ = await gr.posicoes_abertas(symbol)

                    if side is None:
                        logger.info(f"{symbol}: Nenhuma posição aberta (side=None)")
                        side = 'none'

                    if amount is None:
                        amount = 0

                    tem_ordem_aberta = await gr.ultima_ordem_aberta(symbol)
                    print(tem_ordem_aberta)
                    print(side)

                    if not tem_ordem_aberta:
                        if side != 'short' and verificar_long(df):
                            model, scaler = treina_modelo(df)
                            preco_futuro = predict(df, model=model, scaler=scaler)
                            await context.bot.send_message(chat_id=chat_id, text=f"⏳ Modelo XGB sendo calculado em {symbol}...")

                            if df['fechamento'].iloc[-1] <= preco_futuro:
                                await abrir_long(binance, symbol, posicao_max, context)

                        elif side != 'long' and verificar_short(df):
                            model, scaler = treina_modelo(df)
                            preco_futuro = predict(df, model=model, scaler=scaler)
                            await context.bot.send_message(chat_id=chat_id, text=f"⏳ Modelo XGB sendo calculado em {symbol}...")

                            if df['fechamento'].iloc[-1] >= preco_futuro:
                                await abrir_short(binance, symbol, posicao_max, context)
            
            await gr.close()

        except Exception as e:
            logger.error(f"Erro no trading task: {e}")
            if 'chat_id' in locals():
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Erro na análise: {str(e)}")

async def trading_task_btc_1m(context):
    async with GerenciamentoRiscoAsync() as gr:
        try:
            chat_id = context.job.chat_id
            #await context.bot.send_message(chat_id=chat_id, text="📊 Analisando BTC (estratégia 1m scalper)...")

            symbol = 'BTC/USDT'
            posicao_max = 0.007
            timeframe = context.chat_data.get('timeframe_operacao_simples', '1m')
            binance = await conectar_binance()
            
            await gr.fecha_pnl(symbol, loss=-25, target=50, context=context)

            # Verificar posição
            side, amount, _, is_open, _, _, _ = await gr.posicoes_abertas(symbol)

            if side is None:
                logger.info(f"{symbol}: Nenhuma posição aberta (side=None)")
                side = 'none'

            if amount is None:
                amount = 0

            # Se não tem posição aberta, cancela ordens penduradas
            if not is_open:
                await cancelar_todas_as_ordens(binance, symbol, context)

            # Coletar dados e indicadores
            df = await obter_dados_candles(binance, symbol, timeframe)
            df = calcular_indicadores(df)

            # Verifica se há espaço para abrir nova posição
            if not await gr.posicao_max(symbol, posicao_max):
                tem_ordem_aberta = await gr.ultima_ordem_aberta(symbol)

                if not tem_ordem_aberta:
                    if side != 'short' and verificar_long_btc_1m(df):
                        await abrir_long(binance, symbol, posicao_max, context)

                    elif side != 'long' and verificar_short_btc_1m(df):
                        await abrir_short(binance, symbol, posicao_max, context)

        except Exception as e:
            logger.error(f"Erro na estratégia simples BTC: {e}")
            await context.bot.send_message(chat_id=context.job.chat_id, text=f"❌ Erro BTC simples: {str(e)}")

# FUNCOES DE PARAR !!!
async def parar_rompimento(update: Update, context: CallbackContext):
    try:
        for job in context.job_queue.jobs():
            if job.name == "rompimento_job":
                job.schedule_removal()
        await update.message.reply_text("🛑 Estratégia de rompimento parada com sucesso!")
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao parar rompimento: {e}")

async def parar_bot(update: Update, context: CallbackContext):
    """Handler do comando /parar"""
    try:
        if hasattr(context, 'job_queue') and context.job_queue:
            for job in context.job_queue.jobs():
                job.schedule_removal()
        
        await update.message.reply_text("🛑 Bot parado com sucesso!")
        
        # Aqui você adicionaria o código para fechar posições
        # await fechar_posicoes_abertas()
        
    except Exception as e:
        logger.error(f"Erro ao parar bot: {e}")
        await update.message.reply_text(f"❌ Erro ao parar: {str(e)}")

async def parar_bot_simples(update: Update, context: CallbackContext):
    try:
        for job in context.job_queue.jobs():
            if job.name == "btc_simples_job":
                job.schedule_removal()

        await update.message.reply_text("🛑 Estratégia BTC simples parada com sucesso!")
    except Exception as e:
        logger.error(f"Erro ao parar bot simples: {e}")
        await update.message.reply_text(f"❌ Erro ao parar bot simples: {str(e)}")

async def parar_macd(update: Update, context: CallbackContext):
    for job in context.job_queue.jobs():
        if job.name == "macd_job":
            job.schedule_removal()
    await update.message.reply_text("🛑 Estratégia MACD Clustering parada!")

# FUNCOES NÃO TRADING !!
async def regime_handler(update: Update, context: CallbackContext):
    try:
        # Pega o argumento, se houver
        timeframe = context.args[0] if context.args else '1h'

        # Validações simples (opcional)
        if timeframe not in ['15m', '2h', '5m', '30m', '1h', '4h', '1d']:
            await update.message.reply_text(f"⛔ Timeframe inválido: {timeframe}. Use: 15m, 1h, 4h, etc.")
            return

        await update.message.reply_text(f"🔍 Calculando o regime de mercado em *{timeframe}*, aguarde...")

        from strategies.diagnostico_precos_ccxt import rodar_diagnostico_tail1
        diagnostico = await rodar_diagnostico_tail1(timeframe=timeframe)
        regime = diagnostico['regime'].iloc[-1]
        # timestamp = diagnostico.index[-1].strftime('%Y-%m-%d %H:%M')

        msg = f"📈 *Diagnóstico de Mercado AutoCorr*\n🕒 *Timeframe:* `{timeframe}`\n📊 *Regime Detectado:* `{regime}`"
        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao calcular o regime: {str(e)}")

async def supertrend_handler(update: Update, context: CallbackContext):
    try:
        if len(context.args) < 2:
            await update.message.reply_text("⛔ Uso correto: /supertrend [SYMBOL] [TIMEFRAME]\nExemplo: `/supertrend BTCUSDT 1h`", parse_mode="Markdown")
            return

        symbol = context.args[0].upper()
        timeframe = context.args[1]

        await update.message.reply_text(f"⏳ Calculando SuperTrend AI para {symbol} no timeframe {timeframe}...")

        binance = await conectar_binance()
        trend, stop, ama = await SuperTrendAIClusteringAsync(binance, symbol, timeframe)

        trend_text = "🟢 Alta (1)" if trend == 1 else "🔴 Baixa (0)"

        msg = (
            f"📊 *SuperTrend AI Clustering*\n\n"
            f"🔹 *Ativo:* `{symbol}`\n"
            f"🔹 *Timeframe:* `{timeframe}`\n"
            f"🔹 *Tendência:* {trend_text}\n"
            f"🔹 *Stop:* `{float(stop):.4f}`\n"
            f"🔹 *AMA:* `{float(ama):.4f}`"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao calcular SuperTrend: {str(e)}")

# import aiohttp
# import asyncio

# async def get_economic_events_async():
#     url = 'https://economic-calendar.tradingview.com/events'
#     today = pd.Timestamp.today().normalize()

#     start_time_sp = today + pd.Timedelta(hours=6)
#     end_time_sp = today + pd.Timedelta(days=1)

#     headers = {'Origin': 'https://in.tradingview.com'}
#     params = {
#         'from': start_time_sp.isoformat() + '.000Z',
#         'to': end_time_sp.isoformat() + '.000Z',
#         'countries': 'US'
#     }

#     attempts = 0
#     max_attempts = 5

#     while attempts < max_attempts:
#         try:
#             async with aiohttp.ClientSession() as session:
#                 async with session.get(url, headers=headers, params=params) as response:
#                     data = await response.json()

#             df = pd.DataFrame(data['result'])
#             df = df[df['importance'] == 1][['title', 'indicator', 'actual', 'previous', 'forecast', 'importance', 'date']]
#             df['date'] = pd.to_datetime(df['date'])

#             if df['date'].dt.tz is None:
#                 df['date'] = df['date'].dt.tz_localize('UTC')
#             df['date'] = df['date'].dt.tz_convert('America/Sao_Paulo')
#             df['hora'] = df['date'].dt.strftime('%H:%M')

#             return df

#         except Exception as e:
#             print(f"Erro ao buscar dados econômicos: {e}")
#             attempts += 1
#             await asyncio.sleep(5)

#     return None

async def eventos_handler(update: Update, context: CallbackContext):
    try:
        await update.message.reply_text("📡 Buscando eventos econômicos importantes dos EUA para hoje...")

        df = await get_economic_events_async()

        if df is None or df.empty:
            await update.message.reply_text("⚠️ Nenhum evento relevante encontrado.")
            return

        mensagens = []
        for _, row in df.iterrows():
            msg = (
                f"📅 {row['hora']} - *{row['title']}*\n"
                f"🔹 *Indicador:* {row['indicator']}\n"
                f"🔸 *Atual:* {row['actual']}\n"
                f"🔸 *Anterior:* {row['previous']}\n"
                f"🔸 *Previsão:* {row['forecast']}"
            )
            mensagens.append(msg)

        for m in mensagens[:5]:  # Limite de envio
            await update.message.reply_text(m, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao buscar eventos: {str(e)}")

async def noticias_handler(update: Update, context: CallbackContext):
    try:
        if len(context.args) < 2:
            await update.message.reply_text(
                "⚠️ Uso correto:\n/noticias termo idioma\n\nExemplos:\n"
                "/noticias PETR4 pt\n/noticias Bitcoin en"
            )
            return

        termo = context.args[0]
        idioma = context.args[1].lower()

        await update.message.reply_text(f"🔍 Buscando notícias sobre *{termo}* em *{idioma.upper()}*...")

        df_noticias = await buscar_noticias_google([termo], idioma=idioma, dias=1, max_paginas=3)

        if df_noticias.empty:
            await update.message.reply_text("⚠️ Nenhuma notícia encontrada nas últimas horas.")
            return

        titulos = df_noticias['titulo'].dropna().unique().tolist()
        await update.message.reply_text(f"📰 {len(titulos)} notícias encontradas. Classificando sentimentos...")
        sentimentos = await analisar_sentimento_openrouter(titulos, idioma=idioma)

        df_sentimentos = pd.DataFrame(sentimentos)
        df_final = df_noticias.reset_index(drop=True).join(df_sentimentos)
        
        output_dir = 'outputs'
        os.makedirs(output_dir, exist_ok=True)
        nome_arquivo = f'noticias_{termo}.csv'
        caminho_completo = os.path.join(output_dir, nome_arquivo)
        df_final.to_csv(caminho_completo, index=False, encoding='utf-8-sig')

        resumo = gerar_resumo(df_final)

        await update.message.reply_text(resumo, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {e}")

# async def buscar_noticias_google(termos, idioma='en', dias=1, max_paginas=2):
#     lang = idioma.lower()
#     region = 'BR' if lang == 'pt' else 'EN'

#     googlenews = GoogleNews(lang=lang, region=region, period=f'{dias}d')
#     resultados = []

#     for termo in termos:
#         googlenews.search(termo)

#         for pagina in range(1, max_paginas + 1):
#             googlenews.getpage(pagina)
#             noticias = googlenews.result()

#             for n in noticias:
#                 data = n.get('date', '').lower()

#                 if any(x in data for x in ['minutes', 'minutos', 'hora', 'hour']):
#                     resultados.append({
#                         'termo': termo,
#                         'titulo': n.get('title'),
#                         'data': n.get('date'),
#                         'link': n.get('link'),
#                         'fonte': n.get('media'),
#                         'desc': n.get('desc')
#                     })

#             await asyncio.sleep(0.5)

#         googlenews.clear()

#     df = pd.DataFrame(resultados).drop_duplicates(subset=['titulo', 'link'])
#     return df

# async def analisar_sentimento_openai(textos, idioma='en', seed=42):
#     resultados = []
#     for texto in textos:
#         prompt = f"""
# You are a financial sentiment classifier.
# Read the news headline below and classify it as POSITIVE, NEGATIVE, or NEUTRAL.
# Then, write a one-sentence justification.

# Respond ONLY in this JSON format:
# {{
#   "sentiment": "...",
#   "justification": "..."
# }}

# Headline: "{texto}"
# """ if idioma == 'en' else f"""
# Você é um classificador de sentimento financeiro.
# Leia o título da notícia abaixo e classifique como POSITIVO, NEGATIVO ou NEUTRO.
# Em seguida, escreva uma justificativa em uma frase.

# Responda APENAS neste formato JSON:
# {{
#   "sentimento": "...",
#   "justificativa": "..."
# }}

# Título: "{texto}"
# """
#         try:
#             response = await asyncio.to_thread(
#                 client.chat.completions.create,
#                 model="gpt-4-turbo",
#                 messages=[{"role": "user", "content": prompt}],
#                 temperature=0.1,
#                 seed=seed
#             )
#             conteudo = response.choices[0].message.content.strip()

#             try:
#                 resultados.append(eval(conteudo))
#             except:
#                 resultados.append({"sentiment": "ERROR", "justification": conteudo})

#         except Exception as e:
#             resultados.append({"sentiment": "ERROR", "justification": str(e)})

#         await asyncio.sleep(0.5)

#     return resultados

# def gerar_resumo(df):
#     total = len(df)
#     resumo = df['sentiment'].value_counts(normalize=True) * 100
#     counts = df['sentiment'].value_counts()

#     resumo_texto = "\n".join([f"• {s}: {counts[s]} ({resumo[s]:.1f}%)" for s in resumo.index])

#     data_min = df['data'].min()
#     data_max = df['data'].max()

#     noticia_mais_nova = df[df['data'] == data_min].iloc[0]
#     noticia_mais_antiga = df[df['data'] == data_max].iloc[0]

#     texto = (
#         f"📰 *Resumo das Notícias*\n"
#         f"• Total de notícias: {total}\n\n"
#         f"*Distribuição de Sentimento:*\n{resumo_texto}\n\n"
#         f"🕒 *Mais recente:* \"{noticia_mais_nova['titulo']}\" - {noticia_mais_nova['data']}\n"
#         f"🔗 {noticia_mais_nova['link']}\n\n"
#         f"🕰️ *Mais antiga:* \"{noticia_mais_antiga['titulo']}\" - {noticia_mais_antiga['data']}\n"
#         f"🔗 {noticia_mais_antiga['link']}"
#     )
#     return texto

async def estrategia_handler(update: Update, context: CallbackContext):
    msg = (
        "📚 *Estratégia XGB Scalper*\n"
        "🔹 *Lógica Técnica:*\n"
        "• Preço vs EMA 20\n"
        "• Cruzamento do MACD\n"
        "• RSI entre 40 e 70 (long) ou entre 30 e 60 (short)\n\n"
        "🔹 *Modelo Preditivo:*\n"
        "• XGBRegressor\n"
        "• Features: RSI, MACD, MACD_Signal, MACD_Hist, EMA50, EMA200, ATR, CCI, WILLIAMS%R, Momentum\n\n"
        "⚠️ A posição só é aberta quando há confluência entre indicadores técnicos e previsão do modelo.\n\n"
        "📚 *Estratégia 1m Scalper BTC*\n"
        "🔹 *Lógica Técnica:*\n"
        "• RSI Extremo (< 15 ou > 85)\n"
        "• Candle de força\n\n"
        "📚 *Estratégia ROMPIMENTO*\n"
        "🔹 *Lógica Técnica:*\n"
        "• Opera a correlação das altcoins em relação ao ETH\n\n"
        "📚 *Estratégia MACD Supertrend*\n"
        "🔹 *Lógica Técnica:*\n"
        "• Cruzamento do MACD\n"
        "• Confluência com RSI + Supertrend \n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

def main():
    """Função principal para iniciar o bot"""
    try:
        # Cria a aplicação
        application = (
            ApplicationBuilder()
            .token(TELEGRAM_TOKEN)
            .concurrent_updates(True)
            .build()
        )

        # Adiciona handlers
        application.add_handler(CommandHandler("ola", start))
        application.add_handler(CommandHandler("operarXGB", iniciar_bot))
        application.add_handler(CommandHandler("pararXGB", parar_bot))
        application.add_handler(CommandHandler("regime", regime_handler))
        application.add_handler(CommandHandler("estrategias", estrategia_handler))
        application.add_handler(CommandHandler("operar1mBTC", iniciar_bot_simples))
        application.add_handler(CommandHandler("parar1mBTC", parar_bot_simples))
        application.add_handler(CommandHandler("operarROMPIMENTO", iniciar_rompimento))
        application.add_handler(CommandHandler("pararROMPIMENTO", parar_rompimento))
        application.add_handler(CommandHandler("supertrend", supertrend_handler))
        application.add_handler(CommandHandler("eventos", eventos_handler))
        application.add_handler(CommandHandler("operarMACD", iniciar_macd))
        application.add_handler(CommandHandler("pararMACD", parar_macd))
        application.add_handler(CommandHandler("noticias", noticias_handler))

        # Inicia o bot
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
    finally:
        logger.info("Bot encerrado")
if __name__ == '__main__':
    main()