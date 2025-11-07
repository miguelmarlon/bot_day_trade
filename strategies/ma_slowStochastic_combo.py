import sys
from pathlib import Path
import time

sys.path.append(str(Path(__file__).parent.parent))

import ta  # Technical Analysis Library
import pandas as pd
from utils.binance_client import BinanceHandler
from scripts.gerenciamento_risco_assin import GerenciamentoRiscoAsync
from strategies.model_xgb import treina_modelo, predict
from strategies.macd_rsi import calcular_indicadores
import asyncio

async def strategy_MA_SlowStochastic_Combo(binance, context, **kwargs):
    """
    Estratégia de Confirmação de Tendência (MA + Slow Stochastic):
    - Usa a Média Móvel como um filtro de tendência de longo prazo.
    - Usa o cruzamento do Oscilador Estocástico Lento como um gatilho de entrada de momentum.
    - ENTRADA LONG: Preço acima da MA E ocorre um cruzamento de alta no Estocástico Lento.
    - ENTRADA SHORT: Preço abaixo da MA E ocorre um cruzamento de baixa no Estocástico Lento.
    
    Args:
        df: DataFrame com colunas ['open', 'high', 'low', 'close', 'volume']
        **kwargs: Parâmetros da estratégia
            - n_ma (int): Período da Média Móvel (default: 80)
            - ma_type (str): Tipo da MA - 'SMA' ou 'EMA' (default: 'EMA')
            - k_sto (int): Período %K do Stochastic (default: 14)
            - d_sto (int): Período %D do Stochastic (default: 21)
            - dd_sto (int): Período da média móvel do %D (default: 5)
    
    Returns:
        str: 'BUY', 'SELL' ou 'HOLD'
    
    Exemplo de parâmetros:
        {'n_ma': 80, 'ma_type': 'EMA', 'k_sto': 14, 'd_sto': 21, 'dd_sto': 5}
    """
    gerenciador_risco = None
    symbols_processed = 0
    symbols_with_signals = 0
    symbols_with_errors = 0
    
    try:
        chat_id = context.job.chat_id if hasattr(context, 'job') else context._chat_id

        timeframe = context.chat_data.get('timeframe_ma_stochastic', '4h')
        take_profit = 0.04
        
        print(f"\n{'='*60}")
        print(f"🚀 Iniciando ciclo da estratégia MA Slow Stochastic")
        print(f"⏰ Timeframe: {timeframe}")
        print(f"🎯 Take Profit: {take_profit*100:.1f}%")
        print(f"{'='*60}\n")

        # Carrega configuração de símbolos
        try:
            df_config = pd.read_csv('config/cripto_tamanho_macd.csv')
            df_config.dropna(inplace=True)
            print(f"📋 Carregados {len(df_config)} símbolos do CSV")
        except FileNotFoundError:
            error_msg = "❌ Arquivo config/cripto_tamanho_macd.csv não encontrado!"
            print(error_msg)
            try:
                await context.bot.send_message(chat_id=chat_id, text=error_msg)
            except:
                pass
            return
        except Exception as csv_error:
            error_msg = f"❌ Erro ao ler CSV: {csv_error}"
            print(error_msg)
            try:
                await context.bot.send_message(chat_id=chat_id, text=error_msg)
            except:
                pass
            return

        gerenciador_risco = GerenciamentoRiscoAsync(binance_handler=binance)

        for idx, row in df_config.iterrows():
            symbol = row['symbol']
            posicao = row['tamanho']
            posicao_max = posicao
            
            # Validação básica do símbolo
            if not symbol or pd.isna(symbol) or not isinstance(symbol, str):
                print(f"⚠️ Símbolo inválido na linha {idx}: {symbol}")
                symbols_with_errors += 1
                continue
                
            # Validação do tamanho da posição
            try:
                posicao_float = float(posicao)
                if posicao_float <= 0:
                    print(f"⚠️ Tamanho de posição inválido para {symbol}: {posicao}")
                    symbols_with_errors += 1
                    continue
            except (ValueError, TypeError):
                print(f"⚠️ Tamanho de posição não numérico para {symbol}: {posicao}")
                symbols_with_errors += 1
                continue
            
            symbols_processed += 1
            
            print(f"🔍 Analisando {symbol} (posição: {posicao_max})...")
            
            # Aguarda entre requisições para evitar rate limiting
            await asyncio.sleep(2)
            
            # Configura alavancagem e margem com tratamento de erros
            try:
                binance.client.set_leverage(10, symbol)
                binance.client.set_margin_mode("ISOLATED", symbol)
            except Exception as config_error:
                print(f"⚠️ Erro ao configurar alavancagem/margem para {symbol}: {config_error}")
                # Não é crítico, continua com as configurações padrão
            
            # Notifica no Telegram
            try:
                await context.bot.send_message(chat_id=chat_id, text=f"🔍 Analisando {symbol}...")
            except Exception as notify_error:
                print(f"Erro ao notificar análise de {symbol}: {notify_error}")

            # Obtém dados de candles com timeout de 30 segundos
            try:
                df = await asyncio.wait_for(
                    binance.obter_dados_candles(symbol, timeframe=timeframe, limit=300),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                error_msg = f"⏱️ Timeout ao obter dados para {symbol}"
                print(error_msg)
                try:
                    await context.bot.send_message(chat_id=chat_id, text=error_msg)
                except:
                    pass
                continue
            except Exception as candle_error:
                error_msg = f"⚠️ Erro ao obter dados para {symbol}: {str(candle_error)[:100]}"
                print(error_msg)
                try:
                    await context.bot.send_message(chat_id=chat_id, text=error_msg)
                except:
                    pass
                continue

            if df is None or df.empty:
                print(f"⚠️ DataFrame vazio para {symbol}")
                try:
                    await context.bot.send_message(chat_id=chat_id, text=f"⚠️ DataFrame vazio para {symbol}")
                except:
                    pass
                continue

            required_cols = ['open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                print(f"⚠️ Colunas faltando no DataFrame de {symbol}: {missing_cols}")
                await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Erro de dados em {symbol}")
                continue
            
            # Obtém preço atual com timeout e retry
            price = None
            try:
                for attempt in range(3):  # 3 tentativas
                    try:
                        trades = await asyncio.wait_for(
                            binance.client.fetch_trades(symbol),
                            timeout=10.0
                        )
                        
                        if not trades:
                            print(f"[AVISO] Nenhum trade recente encontrado para {symbol} (tentativa {attempt+1}/3)")
                            if attempt < 2:
                                await asyncio.sleep(2)
                                continue
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
                                break  # Sucesso, sai do loop
                                
                    except asyncio.TimeoutError:
                        print(f"[TIMEOUT] Tentativa {attempt+1}/3 para obter trades de {symbol}")
                        if attempt < 2:
                            await asyncio.sleep(2)
                        continue
                        
            except Exception as e:
                error_detail = f"[ERRO] Falha ao obter ou formatar o preço para {symbol}: {e}"
                print(error_detail)
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"⚠️ Erro ao obter preço de {symbol}: {str(e)[:100]}"
                    )
                except Exception as notify_error:
                    print(f"Erro ao notificar falha de preço: {notify_error}")
                continue  # Pula para o próximo símbolo se não conseguir obter o preço

            n_ma = kwargs.get("n_ma", 80)
            ma_type = kwargs.get("ma_type", "EMA").strip().lower()

            k_sto = kwargs.get("k_sto", 14)
            d_sto = kwargs.get("d_sto", 21)
            dd_sto = kwargs.get("dd_sto", 5)

            min_periods = max(n_ma, k_sto + d_sto + dd_sto)
            if len(df) < min_periods:
                print(f"⚠️ Dados insuficientes para {symbol}: {len(df)} linhas, necessário {min_periods}")
                continue

            data = df.copy()

            side, _, _, is_open, _, _, _ = await gerenciador_risco.posicoes_abertas(symbol)
            tem_ordem_aberta = await gerenciador_risco.ultima_ordem_aberta(symbol)
            
            if not await gerenciador_risco.posicao_max(symbol, posicao_max) and not tem_ordem_aberta:
                try:
                    
                    if ma_type == "sma":
                        sma = ta.trend.SMAIndicator(data['close'], n_ma)
                        data["MA_Filter"] = sma.sma_indicator()
                    elif ma_type == "ema":
                        ema = ta.trend.EMAIndicator(data['close'], n_ma)
                        data["MA_Filter"] = ema.ema_indicator()
                    else:
                        print(f"⚠️ Tipo de MA inválido para {symbol}: {ma_type}")
                        continue

                    sto = ta.momentum.StochasticOscillator(data['high'], data['low'], data['close'], k_sto, d_sto)
                    data["STO_D"] = sto.stoch_signal()
                    ma_dd = ta.trend.SMAIndicator(data["STO_D"], dd_sto)
                    data["STO_DD"] = ma_dd.sma_indicator()
                    data["STO_DIFF"] = data["STO_D"] - data["STO_DD"]
                    data["STO_DIFF_PREV"] = data["STO_DIFF"].shift(1)

                    data_clean = data.dropna()
                    
                    if data_clean.empty:
                        print(f"⚠️ Dados NaN após cálculo dos indicadores em {symbol}")
                        continue

                    last_close = data_clean['close'].iloc[-1]
                    last_ma = data_clean['MA_Filter'].iloc[-1]
                    last_sto_diff = data_clean['STO_DIFF'].iloc[-1]
                    last_sto_diff_prev = data_clean['STO_DIFF_PREV'].iloc[-1]

                    is_uptrend = last_close > last_ma
                    is_downtrend = last_close < last_ma

                    sto_long_trigger = (last_sto_diff > 0) and (last_sto_diff_prev <= 0)
                    sto_short_trigger = (last_sto_diff < 0) and (last_sto_diff_prev >= 0)

                    if is_uptrend and sto_long_trigger: #and xgb_long:
                        symbols_with_signals += 1
                        await binance.client.cancel_all_orders(symbol)

                        # Calcula stop loss e take profit baseados no modelo de regressão
                        stop_loss_percent = 0.02  # 2% de stop loss
                        
                        print(f"🚀 Abrindo LONG em {symbol} | Preço: {price}")

                        await binance.client.create_order(
                            symbol=symbol,
                            side='buy',
                            type='MARKET',
                            amount=posicao,
                            params={'reduceOnly': False}
                        )

                        # 🛡️ CRÍTICO: Cria stops iniciais IMEDIATAMENTE
                        # Calcula preços de stop
                        stop_loss_price = price * (1 - stop_loss_percent)
                        take_profit_price = price * (1 + take_profit)
                        
                        try:
                            # Cria ordem de Stop Loss
                            await binance.client.create_order(
                                symbol=symbol,
                                side='sell',
                                type='STOP_MARKET',
                                amount=posicao,
                                params={'stopPrice': stop_loss_price, 'reduceOnly': True}
                            )
                            
                            # Cria ordem de Take Profit
                            await binance.client.create_order(
                                symbol=symbol,
                                side='sell',
                                type='TAKE_PROFIT_MARKET',
                                amount=posicao,
                                params={'stopPrice': take_profit_price, 'reduceOnly': True}
                            )
                            
                            print(f"[{symbol}] ✅ Stops iniciais criados | SL: {stop_loss_price:.8f} | TP: {take_profit_price:.8f}")
                        except Exception as stop_error:
                            print(f"[{symbol}] ❌ Erro ao criar stops: {stop_error}")
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=f"⚠️ Erro ao criar stops para {symbol}: {str(stop_error)[:100]}",
                                parse_mode='Markdown'
                            )
                        
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"🚀 Abrindo *LONG* em {symbol}\n"
                                 f"💵 Preço: {price:.2f}\n"
                                 f"🎯 TP: {take_profit*100:.1f}% (${take_profit_price:.2f})\n"
                                 f"🛑 SL: {stop_loss_percent*100:.1f}% (${stop_loss_price:.2f})\n"
                                 f"📊 Quantidade: {posicao}\n"
                                 f"🛡️ Stops criados | 🔄 Monitor ativo para trailing",
                            parse_mode='Markdown'
                        )
                        
                        # Monitor de Risco fará trailing stop se ativado
                        # Use: /iniciarMonitorRisco no Telegram
                        
                    elif is_downtrend and sto_short_trigger: #and xgb_short:
                        symbols_with_signals += 1
                        await binance.client.cancel_all_orders(symbol)

                        stop_loss_percent = 0.02  # 2% de stop loss
                        
                        print(f"🚀 Abrindo SHORT em {symbol} | Preço: {price}")

                        # Entrada a mercado
                        await binance.client.create_order(
                            symbol=symbol,
                            side='sell',
                            type='MARKET',
                            amount=posicao,
                            params={'reduceOnly': False}
                        )

                        # 🛡️ CRÍTICO: Cria stops iniciais IMEDIATAMENTE
                        # Calcula preços de stop
                        # Para SHORT: SL acima do preço, TP abaixo do preço
                        stop_loss_price = price * (1 + stop_loss_percent)
                        take_profit_price = price * (1 - take_profit)
                        
                        try:
                            # Cria ordem de Stop Loss (compra acima do preço)
                            await binance.client.create_order(
                                symbol=symbol,
                                side='buy',
                                type='STOP_MARKET',
                                amount=posicao,
                                params={'stopPrice': stop_loss_price, 'reduceOnly': True}
                            )
                            
                            # Cria ordem de Take Profit (compra abaixo do preço)
                            await binance.client.create_order(
                                symbol=symbol,
                                side='buy',
                                type='TAKE_PROFIT_MARKET',
                                amount=posicao,
                                params={'stopPrice': take_profit_price, 'reduceOnly': True}
                            )
                            
                            print(f"[{symbol}] ✅ Stops iniciais criados | SL: {stop_loss_price:.8f} | TP: {take_profit_price:.8f}")
                        except Exception as stop_error:
                            print(f"[{symbol}] ❌ Erro ao criar stops: {stop_error}")
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=f"⚠️ Erro ao criar stops para {symbol}: {str(stop_error)[:100]}",
                                parse_mode='Markdown'
                            )
                        
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"🚀 Abrindo *SHORT* em {symbol}\n"
                                 f"💵 Preço: {price:.2f}\n"
                                 f"🎯 TP: {take_profit*100:.1f}% (${take_profit_price:.2f})\n"
                                 f"🛑 SL: {stop_loss_percent*100:.1f}% (${stop_loss_price:.2f})\n"
                                 f"📊 Quantidade: {posicao}\n"
                                 f"🛡️ Stops criados | 🔄 Monitor ativo para trailing",
                            parse_mode='Markdown'
                        )
                        
                        # Monitor de Risco fará trailing stop se ativado
                        # Use: /iniciarMonitorRisco no Telegram
                    else:
                        # Sem sinal de entrada
                        print(f"⏸️ Aguardando sinal em {symbol} | Uptrend: {is_uptrend} | Long Trigger: {sto_long_trigger} | Short Trigger: {sto_short_trigger}")
                                    
                except Exception as e:
                    error_detail = f"❌ Erro ao processar {symbol}: {e}"
                    print(error_detail)
                    import traceback
                    print(traceback.format_exc())
                    
                    try:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"⚠️ Erro ao processar {symbol}: {str(e)[:150]}"
                        )
                    except Exception as notify_error:
                        print(f"Erro ao notificar falha de processamento: {notify_error}")
                    continue

        # Resumo do ciclo ao final
        print(f"\n{'='*60}")
        print(f"📊 RESUMO DO CICLO")
        print(f"✅ Símbolos processados: {symbols_processed}")
        print(f"🎯 Sinais detectados: {symbols_with_signals}")
        print(f"❌ Erros encontrados: {symbols_with_errors}")
        print(f"{'='*60}\n")
        
        # Envia resumo para o Telegram
        try:
            summary_msg = (
                f"📊 **Ciclo Concluído**\n"
                f"✅ Processados: {symbols_processed}\n"
                f"🎯 Sinais: {symbols_with_signals}\n"
                f"❌ Erros: {symbols_with_errors}"
            )
            await context.bot.send_message(chat_id=chat_id, text=summary_msg, parse_mode='Markdown')
        except Exception as summary_error:
            print(f"Erro ao enviar resumo: {summary_error}")

    except Exception as e:
        error_msg = f"❌ Erro crítico na estratégia MA_SlowStochastic_Combo: {e}"
        print(error_msg)
        import traceback
        print(traceback.format_exc())
        
        if context:
            try:
                chat_id = context.job.chat_id if hasattr(context, 'job') else context._chat_id
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Erro crítico na estratégia: {str(e)[:200]}"
                )
            except Exception as notify_error:
                print(f"Erro ao notificar erro crítico: {notify_error}")
    
    finally:
        # Fecha o gerenciador de risco se foi criado
        if gerenciador_risco:
            try:
                await gerenciador_risco.close()
                print("✅ Gerenciador de risco fechado")
            except Exception as close_error:
                print(f"⚠️ Erro ao fechar gerenciador: {close_error}")

async def trading_task_ma_slow_stochastic(context):
    binance = None
    try:
        chat_id = context.job.chat_id
        context._chat_id = chat_id
        
        # Notifica o início da estratégia ANTES de executar
        await context.bot.send_message(chat_id=chat_id, text="🤖 Iniciando estratégia MA Slow Stochastic Combo...")
        
        # Cria conexão com Binance (testnet=False para produção, True para testes)
        binance = await BinanceHandler.create(testnet=True)
        
        # Executa a estratégia passando a conexão
        await strategy_MA_SlowStochastic_Combo(binance, context)
        
        await context.bot.send_message(chat_id=chat_id, text="✅ Ciclo da estratégia MA Slow Stochastic concluído com sucesso!")

    except Exception as e:
        error_msg = f"❌ Erro crítico no MA Slow Stochastic: {str(e)[:200]}"
        print(error_msg)
        import traceback
        print(traceback.format_exc())
        
        try:
            await context.bot.send_message(
                chat_id=context.job.chat_id if hasattr(context, 'job') else context._chat_id, 
                text=error_msg
            )
        except Exception as notify_error:
            print(f"Erro ao enviar notificação: {notify_error}")
    
    finally:
        # Garante fechamento da conexão mesmo em caso de erro
        if binance:
            try:
                await binance.close_connection()
                print("✅ Conexão Binance fechada com sucesso")
            except Exception as close_error:
                print(f"⚠️ Erro ao fechar conexão: {close_error}")


# # ============================================
# # FUNÇÃO DE TESTE (SEM TELEGRAM BOT)
# # ============================================

# class MockBot:
#     """Bot simulado que imprime mensagens ao invés de enviá-las."""
#     async def send_message(self, chat_id, text, parse_mode=None):
#         print(f"\n📱 [TELEGRAM SIMULADO - Chat {chat_id}]")
#         print(f"{text}")
#         print("-" * 60)


# class MockContext:
#     """Contexto simulado para testar a estratégia sem o Telegram bot."""
    
#     def __init__(self, chat_id=12345, timeframe='4h'):
#         self._chat_id = chat_id
#         self.chat_data = {
#             'timeframe_ma_stochastic': timeframe
#         }
#         self.bot = MockBot()


# async def test_strategy_ma_slow_stochastic(timeframe='4h', testnet=False, **strategy_params):
#     """
#     Testa a estratégia MA Slow Stochastic sem precisar do bot Telegram.
    
#     Args:
#         timeframe (str): Timeframe para análise ('4h', '1d', etc)
#         testnet (bool): Se True, usa a Binance Testnet (padrão: False)
#         **strategy_params: Parâmetros adicionais da estratégia
#             - n_ma (int): Período da Média Móvel (default: 80)
#             - ma_type (str): Tipo da MA - 'SMA' ou 'EMA' (default: 'EMA')
#             - k_sto (int): Período %K do Stochastic (default: 14)
#             - d_sto (int): Período %D do Stochastic (default: 21)
#             - dd_sto (int): Período da média móvel do %D (default: 5)
    
#     Exemplo de uso:
#         # Teste básico
#         await test_strategy_ma_slow_stochastic()
        
#         # Teste com timeframe 1d
#         await test_strategy_ma_slow_stochastic(timeframe='1d')
        
#         # Teste na testnet com parâmetros customizados
#         await test_strategy_ma_slow_stochastic(
#             timeframe='4h',
#             testnet=True,
#             n_ma=100,
#             ma_type='SMA',
#             k_sto=20
#         )
#     """
#     binance = None
#     try:
#         print("=" * 80)
#         print("🧪 TESTE DA ESTRATÉGIA MA SLOW STOCHASTIC COMBO")
#         print("=" * 80)
#         print(f"\n⚙️ Configurações:")
#         print(f"   • Timeframe: {timeframe}")
#         print(f"   • Modo: {'🧪 TESTNET (Simulação)' if testnet else '💰 PRODUÇÃO (Real)'}")
#         print(f"   • Parâmetros customizados: {strategy_params if strategy_params else 'Padrão'}")
#         print("\n" + "-" * 80)
        
#         # Cria conexão com a Binance (testnet ou produção)
#         binance = await BinanceHandler.create(testnet=testnet)
        
#         # Cria contexto simulado
#         mock_context = MockContext(timeframe=timeframe)
        
#         print("\n🚀 Iniciando análise das criptomoedas...\n")
        
#         # Executa a estratégia
#         await strategy_MA_SlowStochastic_Combo(binance, mock_context, **strategy_params)
        
#         print("\n" + "=" * 80)
#         print("✅ TESTE CONCLUÍDO COM SUCESSO!")
#         print("=" * 80)
        
#     except KeyboardInterrupt:
#         print("\n\n⚠️ Teste interrompido pelo usuário (Ctrl+C)")
        
#     except Exception as e:
#         print("\n" + "=" * 80)
#         print("❌ ERRO NO TESTE!")
#         print("=" * 80)
#         print(f"Erro: {e}")
#         import traceback
#         print("\n📋 Traceback completo:")
#         print(traceback.format_exc())
        
#     finally:
#         if binance:
#             await binance.close_connection()
#             print("\n✅ Conexão com a Binance fechada.")


# # ============================================
# # EXECUÇÃO DIRETA DO ARQUIVO
# # ============================================

# if __name__ == "__main__":
#     print("\n🎯 Executando teste da estratégia MA Slow Stochastic Combo...\n")
    
#     # Escolha uma das opções abaixo:
    
#     # Opção 1: Teste básico (timeframe 4h, produção, parâmetros padrão)
#     asyncio.run(test_strategy_ma_slow_stochastic())
    
#     # Opção 2: Teste com timeframe 1d
#     # asyncio.run(test_strategy_ma_slow_stochastic(timeframe='1d'))
    
#     # Opção 3: Teste na TESTNET (recomendado para primeiros testes)
#     # asyncio.run(test_strategy_ma_slow_stochastic(testnet=True))
    
#     # Opção 4: Teste com parâmetros customizados
#     # asyncio.run(test_strategy_ma_slow_stochastic(
#     #     timeframe='4h',
#     #     testnet=True,
#     #     n_ma=100,
#     #     ma_type='SMA',
#     #     k_sto=20,
#     #     d_sto=21,
#     #     dd_sto=5
#     # ))