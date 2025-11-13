import logging
import os
from dotenv import load_dotenv
import pandas as pd
from scripts.sentiment_analyzer import analisar_sentimento_openrouter, gerar_resumo
from scripts.information_tools import get_economic_events_async, buscar_noticias_google
from strategies.macd_rsi import calcular_indicadores, verificar_long, verificar_short
from strategies.btc_1m import verificar_long_btc_1m, verificar_short_btc_1m
import numpy as np
from scripts.gerenciamento_risco_assin import GerenciamentoRiscoAsync
from strategies.clustering import SuperTrendAIClusteringAsync
from strategies.estrategia_macd_clustering import trading_task_macd_clustering
from strategies.estrategia_rompimento import trading_task_rompimento
from strategies.ma_slowStochastic_combo import trading_task_ma_slow_stochastic
from utils.binance_client import BinanceHandler
from config.config import TELEGRAM_TOKEN_BOT_TRADE
from strategies.model_xgb import treina_modelo, predict
from scripts.cryptos_select import selecionar_cryptos_sem_notas, calcular_tamanho_operacoes_sem_notas
from scripts.monitor_risk import monitor_risk_management
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

    print("Bot iniciado com sucesso!")
    await update.message.reply_text(
        "👋 Olá! Eu sou o *Falcon AI Bot*!\n\n"
        "🤖 *Estratégias de Trading:*\n"
        "▫️ /operarXGB [timeframe] – Inicia o bot com candles de 1h, 2h, etc\n"
        "▫️ /pararXGB – Interrompe o bot\n"
        "▫️ /operarMASlowStochastic [timeframe] – Inicia o bot com candles de 4h e 1d, etc\n"
        "▫️ /pararMASlowStochastic – Interrompe o bot\n"
        "▫️ /operar1mBTC – Inicia o bot scalper no 1m\n"
        "▫️ /parar1mBTC – Interrompe o bot\n"
        "▫️ /operarROMPIMENTO – Inicia o bot correlação ETH\n"
        "▫️ /pararROMPIMENTO – Interrompe o bot correlação ETH\n"
        "▫️ /operarMACD – Inicia o bot da estratégia de MACD + Clustering\n"
        "▫️ /pararMACD – Interrompe o bot da estratégia de MACD + Clustering\n\n"
        "🛡️ *Gerenciamento de Risco:*\n"
        "▫️ /iniciarMonitorRisco – Ativa monitor de risco (1 min)\n"
        "▫️ /pararMonitorRisco – Desativa monitor de risco\n\n"              
        "📊 *Análises:*\n"
        "▫️ /selecionarMOEDAS – Seleciona as moedas com maior valor de mercado\n"
        "▫️ /regime [timeframe] – Diagnóstico do regime de mercado\n"
        "▫️ /estrategias – Exibe a lógica das estratégias disponíveis\n"
        "▫️ /supertrend [cripto] [timeframe] – Clustering Supertrend\n"
        "▫️ /eventos – Eventos macroeconômicos relevantes do dia\n"
        "▫️ /noticias – Classificador de notícias",
        parse_mode='Markdown'
    )

# FUNÇÕES DE INICIAR !!

async def iniciar_macd_clustering(update: Update, context: CallbackContext):
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

    # Salva o timeframe no contexto (usando a chave correta que a estratégia espera)
    context.chat_data['timeframe_operacao_macd'] = tf

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

async def iniciar_ma_slowStochastic(update: Update, context: CallbackContext):
    tf = context.args[0] if context.args else '4h'
    
    # Validação dos timeframes permitidos
    timeframes_validos = ['4h', '1d']
    if tf not in timeframes_validos:
        await update.message.reply_text(
            "⛔ Timeframe inválido. Escolha entre: 4h ou 1d."
        )
        return

    # Converter timeframe para horas
    if tf.endswith('h'):
        horas = int(tf.replace('h', ''))
    elif tf == '1d':
        horas = 24
    else:
        await update.message.reply_text("⛔ Formato de timeframe inválido.")
        return

    # Salva o timeframe no contexto (usando chave específica para MA Slow Stochastic)
    context.chat_data['timeframe_ma_stochastic'] = tf

    # Cancela job anterior se existir
    for job in context.job_queue.jobs():
        if job.name == "ma_slow_stochastic_job":
            job.schedule_removal()

    # Cria o novo job
    context.job_queue.run_repeating(
        trading_task_ma_slow_stochastic,
        interval=60 * 60 * horas,  # segundos * minutos * horas
        first=5,
        chat_id=update.effective_chat.id,
        name="ma_slow_stochastic_job"
    )

    await update.message.reply_text(
        f"✅ Estratégia MA Slow Stochastic ativada!\n"
        f"⏰ Timeframe: {tf} (intervalo: {horas}h)\n"
        f"🔄 Primeira verificação em 5 segundos",
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

async def iniciar_mr_xgb(update: Update, context: CallbackContext):
    """Handler do comando /operar com suporte a timeframe"""
    try:
        # Lê o argumento (ex: /operar 2h)
        tf = context.args[0] if context.args else '1h'
        ALAVANCAGEM = 10  # Alavancagem padrão de 10x
        TIPO_MARGEM = 'ISOLATED'
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
            macd_rsi_xgb,
            interval=20.0,
            first=5,
            chat_id=update.effective_chat.id,
            name="trading_job"
        )

        await update.message.reply_text(f"✅ Bot XGB iniciado com *timeframe {tf}*!", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Erro ao iniciar bot: {e}")
        await update.message.reply_text(f"❌ Erro ao iniciar: {str(e)}")

async def iniciar_bot_1m_btc(update: Update, context: CallbackContext):
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

async def selecionar_moedas_handler(update: Update, context: CallbackContext):
    """
    Função assíncrona chamada pelo handler do comando /selecionarMOEDAS.
    
    Args:
        update (Update): Objeto que contém todas as informações da mensagem recebida.
                         Fornecido automaticamente pela biblioteca python-telegram-bot.
        context (ContextTypes.DEFAULT_TYPE): Objeto que pode ser usado para passar informações
                                             entre diferentes handlers. Fornecido automaticamente.
    """
    
    logger.info(f"Comando /selecionarMOEDAS recebido.")

    try:
        await update.message.reply_text("✅ Comando recebido! Iniciando o processo de análise e trade...")
        
        await update.message.reply_text("🔎 Etapa 1/2: Analisando mercado e indicadores...")
        df = await selecionar_cryptos_sem_notas(limite_moedas=150)

        await update.message.reply_text("🔍 Etapa 2/2: Calculando tamanhos de operações...")
        df_resultado_analise = await calcular_tamanho_operacoes_sem_notas(df)

        if not df_resultado_analise.empty:
            mensagem = []
            mensagem.append(f"Moedas selecionadas:\n{', '.join(df_resultado_analise['symbol'].unique())}")
            await update.message.reply_text(mensagem)
            
        else:
            await update.message.reply_text("ℹ️ Nenhuma moeda atendeu aos critérios da análise no momento.")
        
        await update.message.reply_text("✌️ Processo finalizado com sucesso!")

    except Exception as e:
        
        logger.error(f"Erro ao executar a seleção de moedas: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ocorreu um erro ao processar sua solicitação: {e}")
        
# FUNÇÕES DE ESTRATÉGIAS DIRETAS - NÃO IMPORT !
async def macd_rsi_xgb(context):
    binance = None
    gerenciador_risco = None
    try:
        
        chat_id = context.job.chat_id
        await context.bot.send_message(chat_id=chat_id, text="⏳ Executando análise de mercado...")

        binance = await BinanceHandler.create(testnet=True)
        gerenciador_risco = GerenciamentoRiscoAsync(binance_handler=binance)
        
        async with gerenciador_risco as gr:
            # Validação do arquivo de configuração
            try:
                df_config = pd.read_csv('config/cripto_tamanho_xgb.csv')
                df_config.dropna(inplace=True)
                
                if df_config.empty:
                    await context.bot.send_message(
                        chat_id=chat_id, 
                        text="❌ Arquivo de configuração está vazio!"
                    )
                    return
            except FileNotFoundError:
                await context.bot.send_message(
                    chat_id=chat_id, 
                    text="❌ Arquivo config/cripto_tamanho_xgb.csv não encontrado!"
                )
                return
            except Exception as e:
                await context.bot.send_message(
                    chat_id=chat_id, 
                    text=f"❌ Erro ao ler configuração: {e}"
                )
                return

            timeframe = context.chat_data.get('timeframe_operacao', '1h')

            for _, row in df_config.iterrows():
                symbol = row['symbol']
                posicao_max = row['tamanho']
                # await context.bot.send_message(chat_id=chat_id, text=f"🔎 Analisando {symbol} no timeframe {timeframe}...")
                # print(f"Analisando {symbol} no timeframe {timeframe}...")
                
                # CORRIGIDO: stop_loss deve ser positivo (0.02, não -0.02)
                await gr.stop_dinamico(
                        symbol=symbol, 
                        take_profit=0.04,
                        stop_loss=0.02,
                        context=context 
                    )
                
                await binance.cancelar_todas_as_ordens(symbol, context)

                df = await binance.obter_dados_candles(symbol=symbol, timeframe=timeframe)
                
                df = calcular_indicadores(df)
                
                if df is None or df.empty:
                    logger.warning(f"DataFrame vazio para {symbol} no timeframe {timeframe}. Pulando para o próximo ativo.")
                    await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Dados insuficientes para {symbol}")
                    continue

                if not await gr.posicao_max(symbol, posicao_max):
                    side, amount, _, is_open, _, _, _ = await gr.posicoes_abertas(symbol)

                    if side is None:
                        logger.info(f"{symbol}: Nenhuma posição aberta (side=None)")
                        side = 'none'

                    if amount is None:
                        amount = 0

                    tem_ordem_aberta = await gr.ultima_ordem_aberta(symbol)
                    
                    if not tem_ordem_aberta:
                        # CORRIGIDO: Validação adicional antes de verificar long
                        if side != 'short' and df is not None and not df.empty and verificar_long(df):
                            await context.bot.send_message(chat_id=chat_id, text=f"⏳ Modelo XGB sendo calculado em {symbol} (LONG)...")
                            
                            # CORRIGIDO: Validação do modelo
                            model, scaler = treina_modelo(df)
                            if model is None or scaler is None:
                                await context.bot.send_message(
                                    chat_id=chat_id, 
                                    text=f"❌ Erro ao treinar modelo para {symbol}"
                                )
                                continue
                            
                            preco_futuro = predict(df, model=model, scaler=scaler)
                            if preco_futuro is None:
                                await context.bot.send_message(
                                    chat_id=chat_id, 
                                    text=f"❌ Erro na predição para {symbol}"
                                )
                                continue
                            
                            await context.bot.send_message(chat_id=chat_id, text=f"💰 Valor previsto para {symbol}: {preco_futuro}")
                            await context.bot.send_message(chat_id=chat_id, text=f"💰 Valor atual para {symbol}: {df['close'].iloc[-1]}")

                            if df['close'].iloc[-1] <= preco_futuro:
                                await binance.abrir_long(symbol, posicao_max, context)
                            else:
                                await context.bot.send_message(chat_id=chat_id, text=f"❌ Não foi possível abrir posição: a predição da IA é de QUEDA.")

                        # CORRIGIDO: Validação adicional antes de verificar short
                        elif side != 'long' and df is not None and not df.empty and verificar_short(df):
                            await context.bot.send_message(chat_id=chat_id, text=f"⏳ Modelo XGB sendo calculado em {symbol} (SHORT)...")
                            
                            # CORRIGIDO: Validação do modelo
                            model, scaler = treina_modelo(df)
                            if model is None or scaler is None:
                                await context.bot.send_message(
                                    chat_id=chat_id, 
                                    text=f"❌ Erro ao treinar modelo para {symbol}"
                                )
                                continue
                            
                            preco_futuro = predict(df, model=model, scaler=scaler)
                            if preco_futuro is None:
                                await context.bot.send_message(
                                    chat_id=chat_id, 
                                    text=f"❌ Erro na predição para {symbol}"
                                )
                                continue
                            
                            await context.bot.send_message(chat_id=chat_id, text=f"💰 Valor previsto para {symbol}: {preco_futuro}")
                            await context.bot.send_message(chat_id=chat_id, text=f"💰 Valor atual para {symbol}: {df['close'].iloc[-1]}")
                            
                            if df['close'].iloc[-1] >= preco_futuro:
                                await binance.abrir_short(symbol, posicao_max, context)
                            else:
                                await context.bot.send_message(chat_id=chat_id, text=f"❌ Não foi possível abrir posição: a predição da IA é de ALTA.")

    except Exception as e:
        logger.error(f"Erro no trading task: {e}")
        if 'chat_id' in locals():
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Erro na análise: {str(e)}")
    finally:
        # 4. Garante que o handler principal da Binance seja fechado no final de tudo
        if binance:
            await binance.close_connection()

async def trading_task_btc_1m(context):
    """Função de trading para a estratégia simples de BTC 1m"""
    binance = await BinanceHandler.create()
    gerenciador_risco = GerenciamentoRiscoAsync(binance_handler=binance)
    async with gerenciador_risco as gr:
        try:
            chat_id = context.job.chat_id
            #await context.bot.send_message(chat_id=chat_id, text="📊 Analisando BTC (estratégia 1m scalper)...")

            symbol = 'BTC/USDT'
            posicao_max = 0.003
            timeframe = context.chat_data.get('timeframe_operacao_simples', '1m')
            #binance = await BinanceHandler.create()
            
            # await gr.fecha_pnl(
            #             symbol=symbol, 
            #             loss=-0.25,
            #             target=2.0, 
            #             context=context 
            #         )
            
            # CORRIGIDO: stop_loss deve ser positivo
            await gr.stop_dinamico(
                        symbol=symbol, 
                        take_profit=0.08,
                        stop_loss=0.02,
                        context=context 
                    )
            # Verificar posição
            side, amount, _, is_open, _, _, _ = await gr.posicoes_abertas(symbol)

            if side is None:
                logger.info(f"{symbol}: Nenhuma posição aberta (side=None)")
                side = 'none'

            if amount is None:
                amount = 0

            # Se não tem posição aberta, cancela ordens penduradas
            if not is_open:
                await binance.cancelar_todas_as_ordens(symbol, context)

            # Coletar dados e indicadores
            df = await binance.obter_dados_candles(symbol, timeframe)
            df = calcular_indicadores(df)

            # Verifica se há espaço para abrir nova posição
            if not await gr.posicao_max(symbol, posicao_max):
                tem_ordem_aberta = await gr.ultima_ordem_aberta(symbol)

                if not tem_ordem_aberta:
                    if side != 'short' and verificar_long_btc_1m(df):
                        await binance.abrir_long(symbol, posicao_max, context)

                    elif side != 'long' and verificar_short_btc_1m(df):
                        await binance.abrir_short(symbol, posicao_max, context)

        except Exception as e:
            logger.error(f"Erro na estratégia simples BTC: {e}")
            await context.bot.send_message(chat_id=context.job.chat_id, text=f"❌ Erro BTC simples: {str(e)}")
        finally:
            if binance:
                await binance.close_connection()
                logger.info("Conexão com a Binance (BTC 1m) fechada.")

# FUNCOES DE PARAR !!!
async def parar_rompimento(update: Update, context: CallbackContext):
    try:
        for job in context.job_queue.jobs():
            if job.name == "rompimento_job":
                job.schedule_removal()
        await update.message.reply_text("🛑 Estratégia de rompimento parada com sucesso!")
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao parar rompimento: {e}")

async def parar_bot_mr_xgb(update: Update, context: CallbackContext):
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

async def parar_bot_1m_btc(update: Update, context: CallbackContext):
    try:
        for job in context.job_queue.jobs():
            if job.name == "btc_simples_job":
                job.schedule_removal()

        await update.message.reply_text("🛑 Estratégia BTC simples parada com sucesso!")
    except Exception as e:
        logger.error(f"Erro ao parar bot simples: {e}")
        await update.message.reply_text(f"❌ Erro ao parar bot simples: {str(e)}")

async def parar_macd_clustering(update: Update, context: CallbackContext):
    for job in context.job_queue.jobs():
        if job.name == "macd_job":
            job.schedule_removal()
    await update.message.reply_text("🛑 Estratégia MACD Clustering parada!")

async def parar_ma_slow_stochastic(update: Update, context: CallbackContext):
    for job in context.job_queue.jobs():
        if job.name == "ma_slow_stochastic_job":
            job.schedule_removal()
    await update.message.reply_text("🛑 Estratégia MA Slow Stochastic parada!")

# MONITOR DE RISCO - PROCESSO INDEPENDENTE !!

async def iniciar_monitor_risco(update: Update, context: CallbackContext):
    """
    Inicia o monitor de gerenciamento de risco que roda a cada 1 minuto.
    Monitora TODAS as posições abertas e aplica stop dinâmico automaticamente.
    """
    def _parse_percentage_arg(arg: str, default: float) -> float:
        """Converte argumento textual em decimal (2% -> 0.02)."""
        if arg is None:
            return default
        cleaned = arg.strip().replace('%', '').replace(',', '.').lower()
        if not cleaned:
            return default
        try:
            value = float(cleaned)
            # Se o valor for maior que 1 (ex: 2 para 2%), converte para decimal
            if value > 1:
                value /= 100.0
            # Garante que o valor seja positivo
            if value <= 0:
                raise ValueError
            return value
        except (ValueError, TypeError):
            return default

    # Valores padrão
    default_stop = 0.02
    default_take = 0.02

    # Lê argumentos do comando: /iniciarMonitorRisco [stop_loss] [take_profit]
    args = context.args if context.args else []
    stop_loss = _parse_percentage_arg(args[0] if len(args) > 0 else None, default_stop)
    take_profit = _parse_percentage_arg(args[1] if len(args) > 1 else None, default_take)

    # Persiste a configuração no chat_data para referência futura, se necessário
    context.chat_data['risk_monitor_config'] = {
        'stop_loss': stop_loss,
        'take_profit': take_profit,
    }

    # Cancela job anterior se existir
    for job in context.job_queue.jobs():
        if job.name == "risk_monitor_job":
            job.schedule_removal()
    
    # Cria o novo job - roda a cada 60 segundos
    context.job_queue.run_repeating(
        monitor_risk_management,
        interval=60,  # 1 minuto
        first=5,  # Começa após 5 segundos
        chat_id=update.effective_chat.id,
        name="risk_monitor_job",
        # Passa os valores para o job
        data={'stop_loss': stop_loss, 'take_profit': take_profit}
    )
    
    await update.message.reply_text(
        "✅ *Monitor de Risco Ativado!*\n\n"
        "🔄 Verificando posições abertas a cada 1 minuto\n"
        "📊 Aplicando stop dinâmico automaticamente\n"
        f"🛑 Stop Loss: *{stop_loss:.2%}*\n"
        f"🎯 Take Profit: *{take_profit:.2%}*\n"
        "⚡ Funciona com TODAS as estratégias simultaneamente",
        parse_mode="Markdown"
    )

async def parar_monitor_risco(update: Update, context: CallbackContext):
    """Para o monitor de gerenciamento de risco"""
    job_removed = False
    for job in context.job_queue.jobs():
        if job.name == "risk_monitor_job":
            job.schedule_removal()
            job_removed = True
    
    if job_removed:
        await update.message.reply_text("🛑 Monitor de Risco parado!")
    else:
        await update.message.reply_text("⚠️ Monitor de Risco não estava ativo")

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

        binance = await BinanceHandler.create()
        trend, stop, ama = await SuperTrendAIClusteringAsync(binance, symbol, timeframe)

        trend_text = "🟢 Alta (1)" if trend == 1 else "🔴 Baixa (0)"

        msg = (
            f"📊 *SuperTrend AI Clustering*\n\n"
            f"🔹 *Ativo:* `{symbol}`\n"
            f"🔹 *Timeframe:* `{timeframe}`\n"
            f"🔹 *Tendência:* {trend_text}\n"
            f"🔹 *Stop:* `{float(stop):.4f}`\n"
            f"🔹 *Média Móvel Adaptativa:* `{float(ama):.4f}`"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao calcular SuperTrend: {str(e)}")

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
            .token(TELEGRAM_TOKEN_BOT_TRADE)
            .concurrent_updates(True)
            .build()
        )

        # Adiciona handlers
        application.add_handler(CommandHandler("ola", start))
        application.add_handler(CommandHandler("selecionarMOEDAS", selecionar_moedas_handler))
        application.add_handler(CommandHandler("operarXGB", iniciar_mr_xgb))
        application.add_handler(CommandHandler("pararXGB", parar_bot_mr_xgb))
        application.add_handler(CommandHandler("operarMASlowStochastic", iniciar_ma_slowStochastic))
        application.add_handler(CommandHandler("pararMASlowStochastic", parar_ma_slow_stochastic))
        application.add_handler(CommandHandler("regime", regime_handler))
        application.add_handler(CommandHandler("estrategias", estrategia_handler))
        application.add_handler(CommandHandler("operar1mBTC", iniciar_bot_1m_btc))
        application.add_handler(CommandHandler("parar1mBTC", parar_bot_1m_btc))
        application.add_handler(CommandHandler("operarROMPIMENTO", iniciar_rompimento))
        application.add_handler(CommandHandler("pararROMPIMENTO", parar_rompimento))
        application.add_handler(CommandHandler("supertrend", supertrend_handler))
        application.add_handler(CommandHandler("eventos", eventos_handler))
        application.add_handler(CommandHandler("operarMACD", iniciar_macd_clustering))
        application.add_handler(CommandHandler("pararMACD", parar_macd_clustering))
        application.add_handler(CommandHandler("noticias", noticias_handler))
        application.add_handler(CommandHandler("iniciarMonitorRisco", iniciar_monitor_risco))
        application.add_handler(CommandHandler("pararMonitorRisco", parar_monitor_risco))

        # Inicia o bot
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
    finally:
        logger.info("Bot encerrado")
if __name__ == '__main__':
    main()