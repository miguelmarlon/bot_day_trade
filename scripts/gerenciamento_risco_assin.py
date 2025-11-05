import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import os
from dotenv import load_dotenv
import ccxt.pro
import decimal
import asyncio
import aiohttp
from typing import Tuple, Dict, Any
from telegram.ext import CallbackContext
from utils.binance_client import BinanceHandler
from typing import List, Tuple, Optional
import json
import math

CONFIG_DIR = 'config'
TRAILING_DATA_FILE = os.path.join(CONFIG_DIR, 'trailing_data.json')

class GerenciamentoRiscoAsync:

    def __init__(self, binance_handler: BinanceHandler):
        """
        Inicializa o gerenciamento de risco com um handler da Binance já conectado.
        Este __init__ não deve ser chamado diretamente. Use o método create().
        """
        self.binance_handler = binance_handler
        self._closed = False
        self._highest_profit_reached: Dict[str, float] = {} 
         # --- Alterações e Adições aqui ---
        # Mantemos _highest_profit_reached se ele tiver uma finalidade específica como percentual de lucro
        self._highest_profit_reached: Dict[str, float] = {} 
        # Novo atributo para armazenar o preço mais alto/baixo atingido, usado para trailing STOP PRICE
        self._highest_price_reached: Dict[str, float] = {} 
        # Novo atributo para armazenar o preço atual do trailing stop loss (onde a ordem SL deve estar)
        self._current_trailing_stop_price: Dict[str, float] = {}
        # Atributo para controlar se o trailing está ativo para um símbolo
        self._is_trailing_active: Dict[str, bool] = {} 
        # Controla notificações de prejuízo (evita spam)
        self._loss_notified: Dict[str, bool] = {}
        # --- Fim das Alterações e Adições ---

        self.session = aiohttp.ClientSession()
        self._load_trailing_data()

    async def initialize_from_open_positions(self):
        """
        🔧 INICIALIZAÇÃO INTELIGENTE
        
        Reconstrói o tracking de trailing stops baseado em posições e ordens existentes.
        Útil quando:
        - Bot reinicia e trailing_data.json está vazio
        - Há posições abertas com ordens de stop loss já configuradas
        - Precisa recuperar o estado sem perder proteções
        """
        print("\n🔄 Inicializando tracking de posições abertas...")
        
        try:
            # Busca todas as posições abertas
            all_positions = await self.binance_handler.client.fetch_positions()
            open_positions = [
                pos for pos in all_positions
                if pos.get('contracts', 0) > 0 and pos.get('side') in ('long', 'short')
            ]
            
            if not open_positions:
                print("ℹ️ Nenhuma posição aberta para inicializar")
                return
            
            print(f"📊 {len(open_positions)} posição(ões) aberta(s) detectada(s)")
            
            for position in open_positions:
                symbol = position['symbol']
                side = position['side']
                mark_price = float(position['info']['markPrice'])
                entry_price = float(position['entryPrice'])
                
                print(f"\n🔍 Analisando {symbol} ({side.upper()})...")
                
                # Busca ordens abertas para este símbolo
                try:
                    orders = await self.binance_handler.client.fetch_orders(symbol)
                    open_orders = [o for o in orders if o.get('status') == 'open']
                    
                    # Procura ordem de STOP_MARKET
                    stop_loss_order = None
                    for order in open_orders:
                        if order.get('type') == 'STOP_MARKET' and order.get('stopPrice'):
                            stop_loss_order = order
                            break
                    
                    if stop_loss_order:
                        stop_price = float(stop_loss_order['stopPrice'])
                        print(f"   ✅ Ordem de SL encontrada: {stop_price:.8f}")
                        
                        # Reconstrói o highest/lowest price baseado no stop loss
                        # Para LONG: highest_price = stop_loss / (1 - stop_loss_percent)
                        # Para SHORT: lowest_price = stop_loss / (1 + stop_loss_percent)
                        
                        # Estima o percentual de stop loss pela distância
                        if side == 'long':
                            # Para LONG: SL está abaixo do preço atual
                            stop_percent = (mark_price - stop_price) / mark_price
                            
                            # Calcula o maior preço que gerou este SL
                            # Se SL = highest * (1 - stop_percent)
                            # Então: highest = SL / (1 - stop_percent)
                            if stop_percent > 0 and stop_percent < 1:
                                highest_price = stop_price / (1 - stop_percent)
                                
                                # Usa o maior entre o calculado e o preço atual
                                highest_price = max(highest_price, mark_price)
                                
                                self._highest_price_reached[symbol] = highest_price
                                self._current_trailing_stop_price[symbol] = stop_price
                                self._is_trailing_active[symbol] = True
                                
                                print(f"   📈 Reconstruído: highest_price={highest_price:.8f}")
                                print(f"   🛑 Stop loss atual: {stop_price:.8f}")
                            else:
                                # Se não conseguir calcular, usa preço atual como baseline
                                self._highest_price_reached[symbol] = mark_price
                                self._current_trailing_stop_price[symbol] = stop_price
                                print(f"   ⚠️ Usando mark_price como baseline: {mark_price:.8f}")
                        
                        elif side == 'short':
                            # Para SHORT: SL está acima do preço atual
                            stop_percent = (stop_price - mark_price) / mark_price
                            
                            # Calcula o menor preço que gerou este SL
                            # Se SL = lowest * (1 + stop_percent)
                            # Então: lowest = SL / (1 + stop_percent)
                            if stop_percent > 0:
                                lowest_price = stop_price / (1 + stop_percent)
                                
                                # Usa o menor entre o calculado e o preço atual
                                lowest_price = min(lowest_price, mark_price)
                                
                                self._highest_price_reached[symbol] = lowest_price  # Para SHORT, armazena o MENOR preço
                                self._current_trailing_stop_price[symbol] = stop_price
                                self._is_trailing_active[symbol] = True
                                
                                print(f"   📉 Reconstruído: lowest_price={lowest_price:.8f}")
                                print(f"   🛑 Stop loss atual: {stop_price:.8f}")
                            else:
                                # Se não conseguir calcular, usa preço atual como baseline
                                self._highest_price_reached[symbol] = mark_price
                                self._current_trailing_stop_price[symbol] = stop_price
                                print(f"   ⚠️ Usando mark_price como baseline: {mark_price:.8f}")
                    
                    else:
                        # Sem ordem de SL - inicializa com preço atual
                        print(f"   ℹ️ Nenhuma ordem de SL encontrada - inicializando com mark_price")
                        self._highest_price_reached[symbol] = mark_price
                        print(f"   📍 Baseline: {mark_price:.8f}")
                
                except Exception as order_error:
                    print(f"   ⚠️ Erro ao buscar ordens: {order_error}")
                    # Fallback: inicializa com preço atual
                    self._highest_price_reached[symbol] = mark_price
                    print(f"   📍 Fallback baseline: {mark_price:.8f}")
            
            # Salva todos os dados reconstruídos
            self._save_trailing_data()
            print(f"\n✅ Inicialização concluída! Dados salvos em {TRAILING_DATA_FILE}")
        
        except Exception as e:
            print(f"\n❌ Erro na inicialização: {e}")
            import traceback
            print(traceback.format_exc())

    def _load_trailing_data(self):
            """Carrega os dados do trailing stop do arquivo JSON."""
            if os.path.exists(TRAILING_DATA_FILE):
                try:
                    with open(TRAILING_DATA_FILE, 'r') as f:
                        data = json.load(f)
                        
                        if not data:
                            print(f"⚠️ {TRAILING_DATA_FILE} está vazio. Nenhum dado para carregar.")
                            return
                        
                        print(f"📂 Carregando trailing_data.json com {len(data)} símbolo(s)...")
                        
                        for symbol, values in data.items():
                            # Carrega highest_profit_percentage, convertendo None de volta para -inf se necessário
                            profit_percent = values.get("highest_profit_percentage")
                            if profit_percent is None:
                                profit_percent = -float('inf')
                            self._highest_profit_reached[symbol] = profit_percent
                            
                            self._is_trailing_active[symbol] = values.get("is_trailing_active", False)
                            
                            # CRÍTICO: Carrega também o menor/maior preço atingido
                            if "highest_price_reached" in values and values["highest_price_reached"] is not None:
                                self._highest_price_reached[symbol] = values["highest_price_reached"]
                                print(f"[{symbol}] ✅ Carregado highest_price_reached: {values['highest_price_reached']:.8f}")
                            
                            # CRÍTICO: Carrega também o stop loss atual
                            if "current_trailing_stop_price" in values and values["current_trailing_stop_price"] is not None:
                                self._current_trailing_stop_price[symbol] = values["current_trailing_stop_price"]
                                print(f"[{symbol}] ✅ Carregado current_trailing_stop_price: {values['current_trailing_stop_price']:.8f}")
                        
                        print(f"✅ Trailing data carregado com sucesso!")
                        
                except json.JSONDecodeError as e:
                    print(f"❌ Erro ao carregar {TRAILING_DATA_FILE}: {e}. O arquivo pode estar corrompido.")
                except Exception as e:
                    print(f"❌ Erro inesperado ao carregar trailing data: {e}")
            else:
                print(f"📁 Arquivo {TRAILING_DATA_FILE} não encontrado. Será criado quando necessário.")
                self._highest_profit_reached = {}
                self._is_trailing_active = {}

    def _save_trailing_data(self):
        """Salva os dados atuais do trailing stop no arquivo JSON."""
        data_to_save = {}
        
        # Considera todos os dicionários relevantes
        all_symbols = set(self._highest_profit_reached.keys()) | set(self._is_trailing_active.keys()) | \
                      set(self._highest_price_reached.keys()) | set(self._current_trailing_stop_price.keys())
        
        for symbol in all_symbols:
            # CORREÇÃO: Salva se tiver QUALQUER dado relevante, não só highest_profit_reached
            # Basta ter trailing ativo OU preço extremo OU stop loss atual
            should_save = False
            
            # Verifica se há dados válidos para salvar
            if symbol in self._is_trailing_active and self._is_trailing_active[symbol]:
                should_save = True
            
            if symbol in self._highest_price_reached and self._highest_price_reached[symbol] is not None:
                should_save = True
            
            if symbol in self._current_trailing_stop_price and self._current_trailing_stop_price[symbol] is not None:
                should_save = True
            
            if should_save:
                # Obtém highest_profit_percentage, mas converte -inf para None
                profit_percent = self._highest_profit_reached.get(symbol, -float('inf'))
                if math.isinf(profit_percent) and profit_percent < 0:
                    profit_percent = None  # Converte -Infinity para None (válido em JSON)
                
                data_to_save[symbol] = {
                    "highest_profit_percentage": profit_percent,
                    "is_trailing_active": self._is_trailing_active.get(symbol, False),
                    "highest_price_reached": self._highest_price_reached.get(symbol),
                    "current_trailing_stop_price": self._current_trailing_stop_price.get(symbol)
                }
                
                # DEBUG: Log o que está sendo salvo (formatação corrigida)
                sl_value = data_to_save[symbol]['current_trailing_stop_price']
                highest_value = data_to_save[symbol]['highest_price_reached']
                
                sl_str = f"{sl_value:.8f}" if sl_value is not None else "None"
                highest_str = f"{highest_value:.8f}" if highest_value is not None else "None"
                
                print(f"[{symbol}] 💾 Salvando trailing_data: SL={sl_str}, highest={highest_str}")

        # Garante que o diretório exista
        os.makedirs(CONFIG_DIR, exist_ok=True)
        try:
            with open(TRAILING_DATA_FILE, 'w') as f:
                json.dump(data_to_save, f, indent=2)
            print(f"✅ trailing_data.json atualizado com {len(data_to_save)} símbolo(s)")
        except Exception as e:
            print(f"❌ Erro ao salvar {TRAILING_DATA_FILE}: {e}")

    async def close(self):
        """Fecha todos os recursos de forma segura."""
        if self._closed:
            return
        try:
            await self.session.close()
            if hasattr(self.binance_handler, 'close'):
                await self.binance_handler.client.close()  # CCXT >= 4.0.0 suporta close()
        except Exception as e:
            print(f"Erro ao fechar recursos: {e}")
        finally:
            self._closed = True

    async def __aenter__(self):
        """Suporte para uso com 'async with'."""
        
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Garante o fechamento automático."""
        await self.close()

    async def posicoes_abertas(self, symbol: str) -> Tuple:
        """Versão mais robusta que sempre retorna uma tupla"""
        try:
            positions = await self.binance_handler.client.fetch_positions (symbols=[symbol])
            if not positions or len(positions) == 0:
                return (None, None, None, False, None, None, None)

            position = positions[0]  # Pega a primeira posição (assumindo que há apenas uma)
            
            # Garante que todos os campos existam
            side = position.get('side')
            amount = position.get('info', {}).get('positionAmt', '0').replace('-', '')
            entry_price = position.get('entryPrice', 0)
            notional = position.get('notional', 0)
            percentage = position.get('percentage', 0)
            pnl = position.get('info', {}).get('unRealizedProfit', 0)
            is_open = side in ('long', 'short') and float(amount or 0) > 0

            return (side, amount, entry_price, is_open, notional, percentage, pnl)
        
        except Exception as e:
            # logger.error(f"Erro em posicoes_abertas: {e}")
            return (None, None, None, False, None, None, None)

    async def livro_ofertas(self, symbol: str) -> Tuple[decimal.Decimal, decimal.Decimal]:
        """Obtém o livro de ofertas com tratamento de erros robusto."""
        if self._closed:
            raise RuntimeError("Sessão já fechada")

        try:
            order_book = await self.binance_handler.client.fetch_order_book (symbol)
            return decimal.Decimal(order_book['bids'][0][0]), decimal.Decimal(order_book['asks'][0][0])
        except Exception as e:
            await self.close()  # Fecha recursos em caso de falha
            raise

    async def encerra_posicao(self, symbol: str, context: CallbackContext = None, 
                              try_limit_first: bool = True, limit_timeout: int = 10) -> None:
        """
        Fecha uma posição de forma assíncrona usando estratégia híbrida LIMIT -> MARKET.
        
        Estratégia:
        1. Tenta ordem LIMIT primeiro (melhor preço, economiza em taxas)
        2. Aguarda `limit_timeout` segundos para execução
        3. Se não executar, cancela e usa ordem MARKET (execução garantida)
        
        Args:
            symbol: Símbolo do ativo (ex: 'BTC/USDT')
            context: Contexto do Telegram para envio de mensagens
            try_limit_first: Se True, tenta LIMIT antes de MARKET (default: True)
            limit_timeout: Tempo em segundos para aguardar execução da ordem LIMIT (default: 10)
        """
        max_retries = 3
        retry_count = 0
        
        # Notifica início do processo de fechamento
        if context:
            await self.enviar_mensagem(context, f"🔄 Iniciando fechamento de posição: {symbol}")
        
        try:
            while retry_count < max_retries:
                # Verifica se a posição ainda está aberta
                side, amount, _, is_open, _, _, _ = await self.posicoes_abertas(symbol)
                
                if not is_open:
                    msg = f'✅ Posição {symbol} já está fechada'
                    print(msg)
                    if context:
                        await self.enviar_mensagem(context, msg)
                    return
                
                # Valida amount
                try:
                    amount_float = float(amount) if amount not in (None, '', '0') else 0.0
                except (ValueError, TypeError):
                    error_msg = f'❌ Quantidade inválida para {symbol}: {amount}'
                    print(error_msg)
                    if context:
                        await self.enviar_mensagem(context, error_msg)
                    return
                
                if amount_float <= 0:
                    msg = f'⚠️ Quantidade zero para {symbol}, nada para fechar'
                    print(msg)
                    if context:
                        await self.enviar_mensagem(context, msg)
                    return
                
                # Cancela todas as ordens abertas antes de fechar
                try:
                    await self.binance_handler.client.cancel_all_orders(symbol)
                    print(f'[{symbol}] 🗑️ Ordens canceladas antes de fechar posição')
                except Exception as cancel_error:
                    print(f'[{symbol}] ⚠️ Erro ao cancelar ordens: {cancel_error}')
                    # Continua mesmo se falhar ao cancelar
                
                order = None
                order_executed = False
                
                # ESTRATÉGIA HÍBRIDA: Tenta LIMIT primeiro, depois MARKET
                if try_limit_first:
                    try:
                        # Obtém preço do livro de ofertas para ordem LIMIT
                        bid, ask = await self.livro_ofertas(symbol)
                        
                        if side == 'long':
                            # Para fechar LONG, vende - usa o preço BID (melhor preço de compra)
                            limit_price = float(bid)
                            order_side = 'sell'
                            msg_type = 'LONG'
                        elif side == 'short':
                            # Para fechar SHORT, compra - usa o preço ASK (melhor preço de venda)
                            limit_price = float(ask)
                            order_side = 'buy'
                            msg_type = 'SHORT'
                        else:
                            error_msg = f'❌ Side inválido para {symbol}: {side}'
                            print(error_msg)
                            if context:
                                await self.enviar_mensagem(context, error_msg)
                            return
                        
                        # Ajusta precisão do preço
                        limit_price = self.binance_handler.client.price_to_precision(symbol, limit_price)
                        
                        print(f'[{symbol}] 💰 Tentando ordem LIMIT para fechar {msg_type} a {limit_price}')
                        
                        # Notifica tentativa de ordem LIMIT
                        if context:
                            await self.enviar_mensagem(context, 
                                f"💰 Tentando fechar {msg_type}\n"
                                f"Tipo: LIMIT\n"
                                f"Preço: {limit_price}\n"
                                f"Quantidade: {amount_float}")
                        
                        # Cria ordem LIMIT
                        order = await self.binance_handler.client.create_order(
                            symbol=symbol,
                            side=order_side,
                            type='LIMIT',
                            amount=amount_float,
                            price=limit_price,
                            params={
                                'reduceOnly': True,
                                'timeInForce': 'GTC'  # Good Till Cancel
                            }
                        )
                        
                        order_id = order.get('id')
                        print(f'[{symbol}] ⏳ Ordem LIMIT criada (ID: {order_id}), aguardando {limit_timeout}s...')
                        
                        # Aguarda execução da ordem LIMIT
                        for i in range(limit_timeout):
                            await asyncio.sleep(1)
                            
                            # Verifica status da ordem
                            try:
                                order_status = await self.binance_handler.client.fetch_order(order_id, symbol)
                                
                                if order_status['status'] == 'closed':
                                    order_executed = True
                                    success_msg = f'✅ Ordem LIMIT executada! {msg_type} fechado a {limit_price}'
                                    print(success_msg)
                                    if context:
                                        await self.enviar_mensagem(context, success_msg)
                                    break
                                    
                            except Exception as status_error:
                                print(f'[{symbol}] ⚠️ Erro ao verificar status da ordem: {status_error}')
                        
                        # Se ordem LIMIT não foi executada, cancela e vai para MARKET
                        if not order_executed:
                            print(f'[{symbol}] ⏱️ Ordem LIMIT não executada em {limit_timeout}s, cancelando...')
                            
                            # Notifica mudança para MARKET
                            if context:
                                await self.enviar_mensagem(context, 
                                    f"⏱️ Ordem LIMIT não executada\n"
                                    f"Mudando para ordem MARKET em {symbol}")
                            
                            try:
                                await self.binance_handler.client.cancel_order(order_id, symbol)
                                print(f'[{symbol}] 🗑️ Ordem LIMIT cancelada, mudando para MARKET')
                            except Exception as cancel_error:
                                print(f'[{symbol}] ⚠️ Erro ao cancelar ordem LIMIT: {cancel_error}')
                        
                    except Exception as limit_error:
                        print(f'[{symbol}] ⚠️ Erro na ordem LIMIT: {limit_error}, mudando para MARKET')
                        order_executed = False
                
                # Se LIMIT não executou OU não tentou LIMIT, usa MARKET
                if not order_executed:
                    try:
                        if side == 'long':
                            # Para fechar LONG, vende a MARKET
                            order = await self.binance_handler.client.create_order(
                                symbol=symbol,
                                side='sell',
                                type='MARKET',
                                amount=amount_float,
                                params={'reduceOnly': True}
                            )
                            msg = f'🔴 Fechando LONG: {amount_float} de {symbol} a MARKET'
                            
                        elif side == 'short':
                            # Para fechar SHORT, compra a MARKET
                            order = await self.binance_handler.client.create_order(
                                symbol=symbol,
                                side='buy',
                                type='MARKET',
                                amount=amount_float,
                                params={'reduceOnly': True}
                            )
                            msg = f'🔴 Fechando SHORT: {amount_float} de {symbol} a MARKET'
                            
                        else:
                            error_msg = f'❌ Side inválido para {symbol}: {side}'
                            print(error_msg)
                            if context:
                                await self.enviar_mensagem(context, error_msg)
                            return
                        
                        print(msg)
                        if context:
                            await self.enviar_mensagem(context, msg)
                        
                        # Aguarda processamento
                        await asyncio.sleep(2)
                        
                    except Exception as market_error:
                        retry_count += 1
                        error_msg = f'❌ Erro ao criar ordem MARKET para {symbol} (tentativa {retry_count}/{max_retries}): {market_error}'
                        print(error_msg)
                        if context:
                            await self.enviar_mensagem(context, error_msg)
                        
                        if retry_count < max_retries:
                            await asyncio.sleep(3)
                            continue
                        else:
                            raise
                
                # Verifica se a posição foi fechada
                _, _, _, is_still_open, _, _, _ = await self.posicoes_abertas(symbol)
                if not is_still_open:
                    order_type = 'LIMIT' if order_executed else 'MARKET'
                    success_msg = f'✅ Posição {symbol} fechada com sucesso via {order_type}! Ordem ID: {order.get("id", "N/A")}'
                    print(success_msg)
                    if context:
                        await self.enviar_mensagem(context, success_msg)
                    return
                else:
                    retry_count += 1
                    print(f'[{symbol}] ⚠️ Posição ainda aberta após tentativa {retry_count}/{max_retries}')
                    if retry_count < max_retries:
                        await asyncio.sleep(3)
            
            # Se chegou aqui, excedeu as tentativas
            final_error = f'❌ Falha ao fechar posição {symbol} após {max_retries} tentativas'
            print(final_error)
            if context:
                await self.enviar_mensagem(context, final_error)

        except Exception as e:
            error_msg = f'❌ Erro crítico ao encerrar posição {symbol}: {str(e)}'
            print(error_msg)
            if context:
                await self.enviar_mensagem(context, error_msg)

    async def fecha_pnl(self, 
                        symbol: str, 
                        loss: float, 
                        target: float, 
                        context: Optional[CallbackContext] = None,
                        try_limit_first: bool = True) -> None:
        """
        Gerencia stop loss e take profit de forma assíncrona com Trailing Stop por pontos fixos.
        
        Estratégia de Trailing Stop:
        - Monitora o lucro da posição em tempo real
        - Ajusta o stop loss automaticamente conforme o lucro aumenta
        - Fecha posição automaticamente ao atingir stop loss ou take profit
        - Usa estratégia híbrida LIMIT→MARKET para fechamento
        
        Args:
            symbol: Símbolo do ativo (ex: 'BTC/USDT')
            loss: Stop loss inicial em decimal (ex: -0.02 = -2%)
            target: Take profit alvo em decimal (ex: 0.10 = 10%)
            context: Contexto do Telegram para notificações
            try_limit_first: Se True, tenta ordem LIMIT antes de MARKET
        """
        fixed_trailing_stops = {
            0.10: 0.05,  # 10% de lucro -> trailing stop em 5%
            0.20: 0.15,  # 20% de lucro -> trailing stop em 15%
            0.30: 0.25,  # 30% de lucro -> trailing stop em 25%
            0.40: 0.35,  # 40% de lucro -> trailing stop em 35%
            0.50: 0.45,  # 50% de lucro -> trailing stop em 45%
            0.60: 0.55,  # 60% de lucro -> trailing stop em 55%
            0.70: 0.65,  # 70% de lucro -> trailing stop em 65%
            0.80: 0.75,  # 80% de lucro -> trailing stop em 75%
            0.90: 0.85,  # 90% de lucro -> trailing stop em 85%
            1.00: 0.90,  # 100% de lucro -> trailing stop em 90%
            1.10: 1.00,  # 110% de lucro -> trailing stop em 100%
            1.20: 1.10,  # 120% de lucro -> trailing stop em 110%
            1.30: 1.20,  # 130% de lucro -> trailing stop em 120%
            1.40: 1.30,  # 140% de lucro -> trailing stop em 130%
            1.50: 1.40,  # 150% de lucro -> trailing stop em 140%
            1.60: 1.50,  # 160% de lucro -> trailing stop em 150%
            1.70: 1.60,  # 170% de lucro -> trailing stop em 160%
            1.80: 1.70,  # 180% de lucro -> trailing stop em 170%
            1.90: 1.80,  # 190% de lucro -> trailing stop em 180%
            2.00: 1.90   # 200% de lucro -> trailing stop em 190%
        }
        
        # Inicializa os dados do trailing se ainda não estiverem prontos
        if symbol not in self._highest_profit_reached:
            self._highest_profit_reached[symbol] = -float('inf')
            self._is_trailing_active[symbol] = False

        try:
            # Obtém os dados da posição atual
            side, amount, entry_price, is_open, entry_time, percentage_raw, pnl = await self.posicoes_abertas(symbol)

            # Valida se a posição está aberta
            if not is_open:
                print(f"[{symbol}] ⚠️ Posição não está aberta, limpando dados de trailing")
                # Limpa dados do trailing se a posição foi fechada
                if symbol in self._highest_profit_reached:
                    del self._highest_profit_reached[symbol]
                if symbol in self._is_trailing_active:
                    del self._is_trailing_active[symbol]
                if symbol in self._loss_notified:
                    del self._loss_notified[symbol]
                self._save_trailing_data()
                return
            
            # Valida dados da posição
            if percentage_raw is None or pnl is None or entry_price is None or entry_price == 0:
                print(f"[{symbol}] ⚠️ Dados da posição inválidos (percentage: {percentage_raw}, pnl: {pnl}, entry: {entry_price})")
                return

            # Calcula o percentual de lucro/prejuízo com base no preço de entrada e PNL
            # Forma mais confiável que usar percentage_raw da API
            try:
                pnl_float = float(pnl)
                entry_price_float = float(entry_price)
                amount_float = float(amount) if amount not in (None, '', '0') else 0.0
                
                if amount_float == 0:
                    print(f"[{symbol}] ⚠️ Quantidade da posição é zero")
                    return
                
                # Calcula o valor nocional da posição (preço de entrada * quantidade)
                position_value = entry_price_float * amount_float
                
                # Percentual de lucro = PNL / valor da posição
                percentage = (pnl_float / position_value) if position_value > 0 else 0.0
                
            except (ValueError, TypeError, ZeroDivisionError) as calc_error:
                print(f"[{symbol}] ❌ Erro ao calcular percentual de lucro: {calc_error}")
                return
            
            pnl_formatted = f"{pnl_float:.2f}"
            highest = self._highest_profit_reached[symbol]
            
            # Atualiza o maior lucro atingido
            if percentage > highest:
                self._highest_profit_reached[symbol] = percentage
                self._save_trailing_data()
                print(f"[{symbol}] 📈 Novo pico de lucro: {percentage:.4%} (anterior: {highest:.4%})")
                
                # Notifica novo pico de lucro se for significativo (> 5%)
                if percentage > 0.05 and (percentage - highest) > 0.02:  # Incremento de pelo menos 2%
                    if context:
                        await self.enviar_mensagem(context, 
                            f"📈 Novo pico de lucro!\n"
                            f"Símbolo: {symbol}\n"
                            f"Lucro atual: {percentage:.2%}\n"
                            f"PNL: {pnl_formatted} USD")
          
            # Determina o stop loss atual (pode ser ajustado pelo trailing stop)
            current_loss_threshold = loss
            previous_threshold = loss
            
            # Verifica se deve ativar trailing stop
            sorted_targets = sorted(fixed_trailing_stops.keys())
            
            for target_profit in sorted_targets:
                if percentage >= target_profit:
                    previous_threshold = current_loss_threshold
                    current_loss_threshold = fixed_trailing_stops[target_profit]
                    
                    # Notifica se o trailing stop foi ajustado para um novo nível
                    if current_loss_threshold != previous_threshold:
                        self._is_trailing_active[symbol] = True
                        print(f"[{symbol}] ✅ Trailing Stop ajustado de {previous_threshold:.4%} para {current_loss_threshold:.4%} (lucro atual: {percentage:.4%})")
                        if context:
                            await self.enviar_mensagem(context, 
                                f"🔄 Trailing Stop {symbol}\n"
                                f"De: {previous_threshold:.2%} → Para: {current_loss_threshold:.2%}\n"
                                f"Lucro atual: {percentage:.2%} ({pnl_formatted} USD)")
                        self._save_trailing_data()
                else:
                    break

            # Log do status atual
            print(f"[{symbol}] 📊 PNL: {percentage:.4%} ({pnl_formatted} USD) | "
                  f"Stop: {current_loss_threshold:.4%} | Target: {target:.4%} | "
                  f"Pico: {self._highest_profit_reached[symbol]:.4%}")
            
            # Envia status periódico ao Telegram (apenas se trailing ativo e lucro > 3%)
            if self._is_trailing_active[symbol] and percentage > 0.03:
                # Envia update a cada 5% de progresso ou quando está próximo do stop/target
                distance_to_stop = abs(percentage - current_loss_threshold)
                distance_to_target = abs(target - percentage)
                
                if distance_to_stop < 0.02 or distance_to_target < 0.03:  # Próximo de eventos importantes
                    if context:
                        await self.enviar_mensagem(context, 
                            f"⚠️ Status {symbol}\n"
                            f"PNL: {percentage:.2%} ({pnl_formatted} USD)\n"
                            f"Stop: {current_loss_threshold:.2%}\n"
                            f"Target: {target:.2%}\n"
                            f"Trailing: 🔄 ATIVO")

            # Verifica se deve fechar por STOP LOSS (ou trailing stop)
            if percentage <= current_loss_threshold:
                reason = 'Trailing Stop' if self._is_trailing_active[symbol] and current_loss_threshold > loss else 'STOP LOSS'
                print(f"[{symbol}] 🚨 Encerrando por {reason}. PNL: {percentage:.4%} ({pnl_formatted} USD)")
                
                await self.encerra_posicao(symbol, context, try_limit_first=try_limit_first)
                
                msg = (f"❌ Saída por {reason}\n"
                       f"PNL: {pnl_formatted} USD ({percentage:.2%})\n"
                       f"Stop: {current_loss_threshold:.2%}\n"
                       f"Símbolo: {symbol}")
                if context:
                    await self.enviar_mensagem(context, msg)
                
                # Limpa dados do trailing
                if symbol in self._highest_profit_reached:
                    del self._highest_profit_reached[symbol]
                if symbol in self._is_trailing_active:
                    del self._is_trailing_active[symbol]
                if symbol in self._loss_notified:
                    del self._loss_notified[symbol]
                self._save_trailing_data()

            # Verifica se deve fechar por TAKE PROFIT
            elif percentage >= target:
                print(f"[{symbol}] ✅ Encerrando por TAKE PROFIT. PNL: {percentage:.4%} ({pnl_formatted} USD)")
                
                await self.encerra_posicao(symbol, context, try_limit_first=try_limit_first)
                
                msg = (f"✅ TAKE PROFIT atingido!\n"
                       f"PNL: {pnl_formatted} USD ({percentage:.2%})\n"
                       f"Target: {target:.2%}\n"
                       f"Símbolo: {symbol}")
                if context:
                    await self.enviar_mensagem(context, msg)
                
                # Limpa dados do trailing
                if symbol in self._highest_profit_reached:
                    del self._highest_profit_reached[symbol]
                if symbol in self._is_trailing_active:
                    del self._is_trailing_active[symbol]
                if symbol in self._loss_notified:
                    del self._loss_notified[symbol]
                self._save_trailing_data()

            else:
                # Posição ainda em aberto, dentro dos limites
                trailing_status = "🔄 ATIVO" if self._is_trailing_active[symbol] else "⏸️ INATIVO"
                print(f"[{symbol}] ⏳ Posição em aberto | PNL: {percentage:.4%} | Trailing: {trailing_status}")
                
                # Notifica quando posição entra em prejuízo significativo (apenas uma vez)
                if percentage < -0.01 and symbol not in self._loss_notified:
                    self._loss_notified[symbol] = True
                    
                    if context:
                        await self.enviar_mensagem(context, 
                            f"⚠️ Posição em prejuízo\n"
                            f"Símbolo: {symbol}\n"
                            f"PNL: {percentage:.2%} ({pnl_formatted} USD)\n"
                            f"Stop Loss: {current_loss_threshold:.2%}")
                
                # Notifica quando posição volta ao lucro após estar em prejuízo
                elif percentage > 0 and symbol in self._loss_notified:
                    del self._loss_notified[symbol]
                    
                    if context:
                        await self.enviar_mensagem(context, 
                            f"✅ Posição recuperada!\n"
                            f"Símbolo: {symbol}\n"
                            f"PNL: {percentage:.2%} ({pnl_formatted} USD)\n"
                            f"Status: Voltou ao lucro")

        except Exception as e:
            error_msg = f"❌ Erro no gerenciamento de PNL para {symbol}: {str(e)}"
            print(error_msg)
            import traceback
            print(traceback.format_exc())
            if context:
                await self.enviar_mensagem(context, error_msg)

    async def posicao_max(self, symbol: str, max_pos: float) -> bool:
        """Verifica se a posição atingiu o tamanho máximo"""
        try:
            _, amount, _, _, _, _, _ = await self.posicoes_abertas(symbol)
            
            # Converter amount para float com segurança
            try:
                amount_float = float(amount) if amount not in (None, '', '0') else 0.0
            except (ValueError, TypeError):
                amount_float = 0.0
                
            return amount_float >= max_pos
        except Exception as e:
            # logger.error(f"Erro em posicao_max: {e}")
            return False

    async def ultima_ordem_aberta(self, symbol: str) -> bool:
        """Verifica se há ordens abertas de forma assíncrona"""
        try:
            orders = await self.binance_handler.client.fetch_orders (symbol)
            return orders[-1]['status'] == 'open' if orders else False
        except Exception:
            return False

    async def enviar_mensagem(self, context: CallbackContext, texto: str) -> None:
        """Envia mensagem via Telegram de forma assíncrona"""
        try:
            await context.bot.send_message(
                chat_id=context.job.chat_id if hasattr(context, 'job') else context._chat_id,
                text=texto,
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"Erro ao enviar mensagem: {e}")

    async def stop_dinamico(self, symbol: str, take_profit: float, stop_loss: float, context: CallbackContext = None) -> None:
        """
        Ajusta stops dinâmicos de forma assíncrona.
        
        A função monitora a posição e ajusta stop loss/take profit quando:
        - Para LONG: preço atual está a 50% ou mais do caminho até o take profit
        - Para SHORT: preço atual está a 50% ou mais do caminho até o take profit
        
        Args:
            symbol: Símbolo do ativo (ex: 'BTC/USDT')
            take_profit: Percentual de lucro alvo (ex: 0.05 = 5%)
            stop_loss: Percentual de perda máxima (ex: 0.02 = 2%)
            context: Contexto do Telegram para envio de mensagens
        """

        def is_number(value) -> bool:
                try:
                    float(value)
                    return True
                except (ValueError, TypeError):
                    return False
                
        try:
            # Obtém posições com timeout
            try:
                positions = await asyncio.wait_for(
                    self.binance_handler.client.fetch_positions(symbols=[symbol]),
                    timeout=15.0
                )
            except asyncio.TimeoutError:
                error_msg = f"[{symbol}] ⏱️ Timeout ao buscar posições no stop dinâmico"
                print(error_msg)
                if context:
                    try:
                        await self.enviar_mensagem(context, error_msg)
                    except:
                        pass
                return
            
            position = positions[0] if positions else None
            if not position:
                print(f"[{symbol}] Nenhuma posição encontrada ou dados inválidos para gerenciar.")
                # IMPORTANTE: NÃO limpa dados de trailing imediatamente
                # Mantém os dados por alguns ciclos para evitar perda de histórico durante atualizações de ordens
                print(f"[{symbol}] ⚠️ Mantendo dados de trailing (posição pode estar sendo atualizada)")
                return
        
            side = position['side']
            amount = abs(float(position['info']['positionAmt'])) 
            entry_price = float(position['entryPrice'])
            mark_price = float(position['info']['markPrice'])
            
            # 🚨 VERIFICAÇÃO DE EMERGÊNCIA: Stop loss já violado durante reinício/downtime?
            if symbol in self._current_trailing_stop_price:
                saved_stop_loss = self._current_trailing_stop_price[symbol]
                
                if side == 'long':
                    # Para LONG: se preço caiu abaixo do stop loss
                    if mark_price <= saved_stop_loss:
                        emergency_msg = (
                            f"🚨 EMERGÊNCIA: Stop Loss violado em {symbol}!\n"
                            f"💰 LONG | Preço atual: {mark_price:.8f}\n"
                            f"🛑 Stop Loss: {saved_stop_loss:.8f}\n"
                            f"⚠️ Fechando posição imediatamente..."
                        )
                        print(emergency_msg)
                        if context:
                            try:
                                await self.enviar_mensagem(context, emergency_msg)
                            except:
                                pass
                        
                        # Fecha posição imediatamente
                        try:
                            await self.fecha_pnl(
                                symbol=symbol,
                                quantidade=amount,
                                operacao='long',
                                context=context,
                                motivo="Stop Loss violado durante downtime"
                            )
                            return
                        except Exception as close_error:
                            error_msg = f"❌ Erro ao fechar posição de emergência: {close_error}"
                            print(error_msg)
                            if context:
                                try:
                                    await self.enviar_mensagem(context, error_msg)
                                except:
                                    pass
                            return
                
                elif side == 'short':
                    # Para SHORT: se preço subiu acima do stop loss
                    if mark_price >= saved_stop_loss:
                        emergency_msg = (
                            f"🚨 EMERGÊNCIA: Stop Loss violado em {symbol}!\n"
                            f"💰 SHORT | Preço atual: {mark_price:.8f}\n"
                            f"🛑 Stop Loss: {saved_stop_loss:.8f}\n"
                            f"⚠️ Fechando posição imediatamente..."
                        )
                        print(emergency_msg)
                        if context:
                            try:
                                await self.enviar_mensagem(context, emergency_msg)
                            except:
                                pass
                        
                        # Fecha posição imediatamente
                        try:
                            await self.fecha_pnl(
                                symbol=symbol,
                                quantidade=amount,
                                operacao='short',
                                context=context,
                                motivo="Stop Loss violado durante downtime"
                            )
                            return
                        except Exception as close_error:
                            error_msg = f"❌ Erro ao fechar posição de emergência: {close_error}"
                            print(error_msg)
                            if context:
                                try:
                                    await self.enviar_mensagem(context, error_msg)
                                except:
                                    pass
                            return
            
            # Validação crítica: verifica se a posição está realmente aberta
            is_position_open = side in ('long', 'short') and amount > 0
            
            if not is_position_open or amount == 0:
                print(f"[{symbol}] Posição não está aberta ou quantidade é zero (side: {side}, amount: {amount})")
               
                # IMPORTANTE: NÃO limpa dados de trailing imediatamente
                # Mantém os dados por alguns ciclos para evitar perda de histórico durante atualizações de ordens
                # Os dados serão limpos apenas quando confirmado que a posição foi realmente fechada
                print(f"[{symbol}] ⚠️ Mantendo dados de trailing (posição pode estar sendo atualizada)")
                
                # Apenas limpa se realmente não houver posição após verificação adicional
                # Esta limpeza será feita em fecha_pnl quando a posição for realmente fechada
                return

            # Busca ordens existentes com timeout
            try:
                orders = await asyncio.wait_for(
                    self.binance_handler.client.fetch_orders(symbol),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                print(f"[{symbol}] ⏱️ Timeout ao buscar ordens, continuando com cálculo de TP baseado na entrada")
                orders = []
            except Exception as orders_error:
                print(f"[{symbol}] ⚠️ Erro ao buscar ordens: {orders_error}")
                orders = []
            
            take_profit_price = None
            # if orders:
            #     for order in orders:
            #         if order.get('type') == 'TAKE_PROFIT_MARKET' and \
            #             order.get('stopPrice') is not None and \
            #             is_number(order['stopPrice']):
            #             take_profit_order_price = float(order['stopPrice'])
            #             break 
                
            #     if take_profit_order_price is None:
            #         last_order = orders[-1]
            #         if last_order.get('stopPrice') is not None and \
            #             is_number(last_order['stopPrice']):
            #             take_profit_order_price = float(last_order['stopPrice'])
            #         else:
            #             print(f"[{symbol}] Aviso: last_order['stopPrice'] não é um número válido ou ordem sem stopPrice. Valor: {last_order.get('stopPrice')}, Ordem Tipo: {last_order.get('type')}")
            
            #-------- ACERTAR ESSA LÓGICA --------
            if orders:
                # Primeiro, tente encontrar uma ordem TAKE_PROFIT_MARKET ativa com stopPrice
                for order in orders:
                    if order.get('type') == 'TAKE_PROFIT_MARKET' and \
                        order.get('status') == 'open' and \
                        order.get('stopPrice') is not None and \
                        is_number(order['stopPrice']):
                        take_profit_price = float(order['stopPrice'])
                        print(f"[{symbol}] Ordem TAKE_PROFIT_MARKET ativa encontrada com stopPrice: {take_profit_price}")
                        break
        
            # Se nenhuma ordem TAKE_PROFIT_MARKET ativa foi encontrada, recalcule o preço do Take Profit
            if take_profit_price is None:
                # Calcule o Take Profit com base no preço de entrada (ou preço de marcação, dependendo da sua lógica)
                # Geralmente é baseado no preço de entrada para definir um alvo fixo
                if side == 'long':
                    take_profit_price = entry_price * (1 + take_profit)
                elif side == 'short':
                    take_profit_price = entry_price * (1 - take_profit)
                
                print(f"[{symbol}] Nenhuma ordem TAKE_PROFIT_MARKET ativa encontrada. Recalculando take_profit_price para: {take_profit_price:.8f}")
            
            if take_profit_price is None:
                print(f"[{symbol}] Nenhuma ordem de Take Profit válida encontrada. Não é possível gerenciar stops dinâmicos.")
                return
           
            # current_take_profit_reference_price = take_profit_order_price

            if side == 'long':
                # Calcula variação de preço em relação à entrada
                price_var = ((mark_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                
                # Calcula quanto falta para o take profit (em valor absoluto)
                distance_to_tp = abs(take_profit_price - mark_price)
                total_distance = abs(take_profit_price - entry_price)
                
                # Validação crítica: evita divisão por zero
                if total_distance <= 0 or abs(take_profit_price - entry_price) < 0.0001:
                    print(f"[{symbol}] ⚠️ Distância total inválida (entry: {entry_price}, TP: {take_profit_price})")
                    return
                
                progress_percent = ((total_distance - distance_to_tp) / total_distance) * 100
                
                # Inicializa o maior preço atingido (para trailing stop em LONG)
                # CRÍTICO: Se já existir, usa o MAIOR entre o valor atual e o mark_price
                if symbol not in self._highest_price_reached:
                    self._highest_price_reached[symbol] = mark_price
                    print(f"[{symbol}] 🆕 Inicializando rastreamento de maior preço: {mark_price:.8f}")
                    self._save_trailing_data()  # Salva imediatamente
                else:
                    old_highest = self._highest_price_reached[symbol]
                    # Se já existe, garante que nunca diminui (só aumenta)
                    if mark_price > self._highest_price_reached[symbol]:
                        self._highest_price_reached[symbol] = mark_price
                        print(f"[{symbol}] 📈 Novo maior preço atingido: {old_highest:.8f} → {mark_price:.8f}")
                        self._save_trailing_data()  # Salva imediatamente
                    else:
                        # Preço caiu - mantém o maior preço registrado
                        print(f"[{symbol}] ℹ️ Preço atual {mark_price:.8f} < maior preço {self._highest_price_reached[symbol]:.8f} (mantendo maior)")
                
                highest_price = self._highest_price_reached[symbol]
                
                # DEBUG: Mostra valor atual armazenado
                print(f"[{symbol}] 🔍 DEBUG: highest_price usado para cálculo: {highest_price:.8f}")
                
                # msg = f'📊 {symbol} LONG: {price_var:.2f}% | Progresso até TP: {progress_percent:.1f}% | Maior preço: {highest_price:.8f}'
                # print(msg)
                if context:
                    try:
                        await self.enviar_mensagem(context, msg)
                    except Exception as notify_error:
                        print(f"[{symbol}] Erro ao enviar mensagem de progresso: {notify_error}")

                # CONDIÇÃO AJUSTADA: Ativa quando atingir 50% do caminho até o take profit
                # Isso torna o trailing stop mais agressivo e protege lucros mais cedo
                if progress_percent >= 50:
                    # Verifica se já existe um trailing stop ativo
                    current_stop_loss_in_order = None
                    if symbol in self._current_trailing_stop_price:
                        current_stop_loss_in_order = self._current_trailing_stop_price[symbol]
                    
                    # Calcula novo stop loss baseado no MAIOR PREÇO atingido, não no preço atual
                    # Isso garante que o SL só sobe (protege lucros) e nunca desce (aumenta risco)
                    new_stop_loss_price = highest_price * (1 - stop_loss)
                    new_take_profit_price = highest_price * (1 + take_profit)
                    
                    # VALIDAÇÃO ADICIONAL: Verifica se highest_price não diminuiu (bug detection)
                    if current_stop_loss_in_order is not None:
                        # Calcula qual seria o highest_price anterior baseado no SL anterior
                        previous_highest_price = current_stop_loss_in_order / (1 - stop_loss)
                        
                        if highest_price < previous_highest_price:
                            # ALERTA: highest_price DIMINUIU! Isso é um bug!
                            print(f"[{symbol}] 🚨 BUG DETECTADO: Maior preço diminuiu de {previous_highest_price:.8f} para {highest_price:.8f}!")
                            print(f"[{symbol}] 🔧 CORREÇÃO: Usando o maior preço anterior para manter proteção")
                            highest_price = previous_highest_price
                            self._highest_price_reached[symbol] = highest_price  # Corrige o valor armazenado
                            self._save_trailing_data()  # Salva a correção imediatamente
                            
                            # Recalcula stops com o valor correto
                            new_stop_loss_price = highest_price * (1 - stop_loss)
                            new_take_profit_price = highest_price * (1 + take_profit)
                    
                    # CRÍTICO: Só ajusta o stop loss se ele for MAIOR que o anterior
                    # Para LONG: queremos que o SL SUBA conforme o preço sobe
                    should_update = False
                    
                    if current_stop_loss_in_order is None:
                        # Primeira vez ativando trailing stop
                        should_update = True
                        print(f"[{symbol}] 🔄 Ativando trailing stop pela primeira vez - Progresso: {progress_percent:.1f}%")
                    elif new_stop_loss_price > current_stop_loss_in_order:
                        # SL está subindo (bom para LONG - protege mais lucro)
                        should_update = True
                        print(f"[{symbol}] 📈 Stop Loss subindo: {current_stop_loss_in_order:.8f} → {new_stop_loss_price:.8f}")
                    else:
                        # SL tentaria descer (RUIM para LONG - não permitir!)
                        print(f"[{symbol}] ⚠️ Stop Loss não atualizado (tentaria descer de {current_stop_loss_in_order:.8f} para {new_stop_loss_price:.8f})")
                        print(f"[{symbol}] ℹ️ Mantendo SL em {current_stop_loss_in_order:.8f} | Preço atual: {mark_price:.8f} | Maior preço: {highest_price:.8f}")
                    
                    if should_update:
                        # Marca trailing como ativo
                        self._is_trailing_active[symbol] = True
                        
                        # Cancela ordens anteriores com timeout
                        try:
                            await asyncio.wait_for(
                                self.binance_handler.client.cancel_all_orders(symbol),
                                timeout=10.0
                            )
                        except asyncio.TimeoutError:
                            print(f"[{symbol}] ⏱️ Timeout ao cancelar ordens")
                        except Exception as cancel_error:
                            print(f"[{symbol}] ⚠️ Erro ao cancelar ordens: {cancel_error}")
                        
                        print(f"[{symbol}] 📍 Preço atual: {mark_price:.8f}")
                        print(f"[{symbol}] 📍 Maior preço atingido: {highest_price:.8f}")
                        print(f"[{symbol}] 🛑 Novo Stop Loss: {new_stop_loss_price:.8f} ({-stop_loss*100:.2f}%)")
                        print(f"[{symbol}] 🎯 Novo Take Profit: {new_take_profit_price:.8f} ({take_profit*100:.2f}%)")

                        try:
                            # Cria ordem de Stop Loss com timeout
                            await asyncio.wait_for(
                                self.binance_handler.client.create_order(
                                    symbol=symbol, 
                                    side='sell', 
                                    type='STOP_MARKET',
                                    amount=amount, 
                                    params={'stopPrice': new_stop_loss_price, 'reduceOnly': True}
                                ),
                                timeout=15.0
                            )
                            
                            # Cria ordem de Take Profit com timeout
                            await asyncio.wait_for(
                                self.binance_handler.client.create_order(
                                    symbol=symbol, 
                                    side='sell', 
                                    type='TAKE_PROFIT_MARKET',
                                    amount=amount, 
                                    params={'stopPrice': new_take_profit_price, 'reduceOnly': True}
                                ),
                                timeout=15.0
                            )
                            
                            # Salva estado de trailing
                            self._current_trailing_stop_price[symbol] = new_stop_loss_price
                            self._save_trailing_data()
                            
                            msg = f'✅ Stops atualizados para LONG em {symbol}\n' \
                                  f'🛑 SL: {new_stop_loss_price:.8f} (baseado no maior preço: {highest_price:.8f})\n' \
                                  f'🎯 TP: {new_take_profit_price:.8f}'
                            print(msg)
                            if context:
                                try:
                                    await self.enviar_mensagem(context, msg)
                                except Exception as notify_error:
                                    print(f"[{symbol}] Erro ao notificar atualização de stops: {notify_error}")
                        
                        except asyncio.TimeoutError:
                            error_msg = f"⏱️ Timeout ao criar ordens de stop para {symbol}"
                            print(error_msg)
                            if context:
                                try:
                                    await self.enviar_mensagem(context, error_msg)
                                except:
                                    pass
                                    
                        except Exception as order_error:
                            error_msg = f"❌ Erro ao criar ordens para {symbol}: {str(order_error)[:150]}"
                            print(error_msg)
                            import traceback
                            print(traceback.format_exc())
                            if context:
                                try:
                                    await self.enviar_mensagem(context, error_msg)
                                except:
                                    pass
                else:
                    print(f"[{symbol}] ⏸️ Aguardando progresso de 50% para LONG (atual: {progress_percent:.1f}%)")

            elif side == 'short':
                # Calcula variação de preço em relação à entrada (SHORT: lucro quando preço cai)
                price_var = ((entry_price - mark_price) / mark_price) * 100 if mark_price > 0 else 0
                
                # Calcula quanto falta para o take profit
                distance_to_tp = abs(mark_price - take_profit_price)
                total_distance = abs(entry_price - take_profit_price)
                
                # Validação crítica: evita divisão por zero
                if total_distance <= 0 or abs(entry_price - take_profit_price) < 0.0001:
                    print(f"[{symbol}] ⚠️ Distância total inválida para SHORT (entry: {entry_price}, TP: {take_profit_price})")
                    return
                
                progress_percent = ((total_distance - distance_to_tp) / total_distance) * 100
                
                # Inicializa o menor preço atingido (para trailing stop em SHORT)
                # CRÍTICO: Se já existir, usa o MENOR entre o valor atual e o mark_price
                if symbol not in self._highest_price_reached:
                    self._highest_price_reached[symbol] = mark_price
                    print(f"[{symbol}] 🆕 Inicializando rastreamento de menor preço: {mark_price:.8f}")
                    self._save_trailing_data()  # Salva imediatamente
                else:
                    old_lowest = self._highest_price_reached[symbol]
                    # Se já existe, garante que nunca aumenta (só diminui)
                    if mark_price < self._highest_price_reached[symbol]:
                        self._highest_price_reached[symbol] = mark_price
                        print(f"[{symbol}] 📉 Novo menor preço atingido: {old_lowest:.8f} → {mark_price:.8f}")
                        self._save_trailing_data()  # Salva imediatamente
                    else:
                        # Preço subiu - mantém o menor preço registrado
                        print(f"[{symbol}] ℹ️ Preço atual {mark_price:.8f} > menor preço {self._highest_price_reached[symbol]:.8f} (mantendo menor)")
                
                lowest_price = self._highest_price_reached[symbol]
                
                # DEBUG: Mostra valor atual armazenado
                print(f"[{symbol}] 🔍 DEBUG: lowest_price usado para cálculo: {lowest_price:.8f}")
                
                # msg = f'📊 {symbol} SHORT: {price_var:.2f}% | Progresso até TP: {progress_percent:.1f}% | Menor preço: {lowest_price:.8f}'
                # print(msg)
                if context:
                    try:
                        await self.enviar_mensagem(context, msg)
                    except Exception as notify_error:
                        print(f"[{symbol}] Erro ao enviar mensagem de progresso: {notify_error}")

                # CONDIÇÃO AJUSTADA: Ativa quando atingir 25% do caminho até o take profit
                if progress_percent >= 25:
                    # Verifica se já existe um trailing stop ativo
                    current_stop_loss_in_order = None
                    if symbol in self._current_trailing_stop_price:
                        current_stop_loss_in_order = self._current_trailing_stop_price[symbol]
                    
                    # Calcula novo stop loss baseado no MENOR PREÇO atingido, não no preço atual
                    # Isso garante que o SL só desce (protege lucros) e nunca sobe (aumenta risco)
                    new_stop_loss_price = lowest_price * (1 + stop_loss)
                    new_take_profit_price = lowest_price * (1 - take_profit)
                    
                    # VALIDAÇÃO ADICIONAL: Verifica se lowest_price não aumentou (bug detection)
                    if current_stop_loss_in_order is not None:
                        # Calcula qual seria o lowest_price anterior baseado no SL anterior
                        previous_lowest_price = current_stop_loss_in_order / (1 + stop_loss)
                        
                        if lowest_price > previous_lowest_price:
                            # ALERTA: lowest_price AUMENTOU! Isso é um bug!
                            print(f"[{symbol}] 🚨 BUG DETECTADO: Menor preço aumentou de {previous_lowest_price:.8f} para {lowest_price:.8f}!")
                            print(f"[{symbol}] 🔧 CORREÇÃO: Usando o menor preço anterior para manter proteção")
                            lowest_price = previous_lowest_price
                            self._highest_price_reached[symbol] = lowest_price  # Corrige o valor armazenado
                            self._save_trailing_data()  # Salva a correção imediatamente
                            
                            # Recalcula stops com o valor correto
                            new_stop_loss_price = lowest_price * (1 + stop_loss)
                            new_take_profit_price = lowest_price * (1 - take_profit)
                    
                    # CRÍTICO: Só ajusta o stop loss se ele for MENOR que o anterior
                    # Para SHORT: queremos que o SL DESÇA conforme o preço desce
                    should_update = False
                    
                    if current_stop_loss_in_order is None:
                        # Primeira vez ativando trailing stop
                        should_update = True
                        print(f"[{symbol}] 🔄 Ativando trailing stop pela primeira vez - Progresso: {progress_percent:.1f}%")
                    elif new_stop_loss_price < current_stop_loss_in_order:
                        # SL está descendo (bom para SHORT - protege mais lucro)
                        should_update = True
                        print(f"[{symbol}] 📉 Stop Loss descendo: {current_stop_loss_in_order:.8f} → {new_stop_loss_price:.8f}")
                    else:
                        # SL tentaria subir (RUIM para SHORT - não permitir!)
                        print(f"[{symbol}] ⚠️ Stop Loss não atualizado (tentaria subir de {current_stop_loss_in_order:.8f} para {new_stop_loss_price:.8f})")
                        print(f"[{symbol}] ℹ️ Mantendo SL em {current_stop_loss_in_order:.8f} | Preço atual: {mark_price:.8f} | Menor preço: {lowest_price:.8f}")
                    
                    if should_update:
                        # Marca trailing como ativo
                        self._is_trailing_active[symbol] = True
                        
                        # Cancela ordens anteriores com timeout
                        try:
                            await asyncio.wait_for(
                                self.binance_handler.client.cancel_all_orders(symbol),
                                timeout=10.0
                            )
                        except asyncio.TimeoutError:
                            print(f"[{symbol}] ⏱️ Timeout ao cancelar ordens no SHORT")
                        except Exception as cancel_error:
                            print(f"[{symbol}] ⚠️ Erro ao cancelar ordens no SHORT: {cancel_error}")
                        
                        print(f"[{symbol}] 📍 Preço atual: {mark_price:.8f}")
                        print(f"[{symbol}] 📍 Menor preço atingido: {lowest_price:.8f}")
                        print(f"[{symbol}] 🛑 Novo Stop Loss: {new_stop_loss_price:.8f} ({stop_loss*100:.2f}%)")
                        print(f"[{symbol}] 🎯 Novo Take Profit: {new_take_profit_price:.8f} ({-take_profit*100:.2f}%)")

                        try:
                            # Cria ordem de Stop Loss (compra acima do preço atual) com timeout
                            await asyncio.wait_for(
                                self.binance_handler.client.create_order(
                                    symbol=symbol, 
                                    side='buy', 
                                    type='STOP_MARKET',
                                    amount=amount, 
                                    params={'stopPrice': new_stop_loss_price, 'reduceOnly': True}
                                ),
                                timeout=15.0
                            )
                            
                            # Cria ordem de Take Profit (compra abaixo do preço atual) com timeout
                            await asyncio.wait_for(
                                self.binance_handler.client.create_order(
                                    symbol=symbol, 
                                    side='buy', 
                                    type='TAKE_PROFIT_MARKET',
                                    amount=amount, 
                                    params={'stopPrice': new_take_profit_price, 'reduceOnly': True}
                                ),
                                timeout=15.0
                            )
                            
                            # Salva estado de trailing
                            self._current_trailing_stop_price[symbol] = new_stop_loss_price
                            self._save_trailing_data()
                            
                            msg = f'✅ Stops atualizados para SHORT em {symbol}\n' \
                                  f'🛑 SL: {new_stop_loss_price:.8f} (baseado no menor preço: {lowest_price:.8f})\n' \
                                  f'🎯 TP: {new_take_profit_price:.8f}'
                            print(msg)
                            if context:
                                try:
                                    await self.enviar_mensagem(context, msg)
                                except Exception as notify_error:
                                    print(f"[{symbol}] Erro ao notificar atualização de stops SHORT: {notify_error}")
                        
                        except asyncio.TimeoutError:
                            error_msg = f"⏱️ Timeout ao criar ordens de stop SHORT para {symbol}"
                            print(error_msg)
                            if context:
                                try:
                                    await self.enviar_mensagem(context, error_msg)
                                except:
                                    pass
                                    
                        except Exception as order_error:
                            error_msg = f"❌ Erro ao criar ordens SHORT para {symbol}: {str(order_error)[:150]}"
                            print(error_msg)
                            import traceback
                            print(traceback.format_exc())
                            if context:
                                try:
                                    await self.enviar_mensagem(context, error_msg)
                                except:
                                    pass
                else:
                    print(f"[{symbol}] ⏸️ Aguardando progresso de 25% para SHORT (atual: {progress_percent:.1f}%)")
            
            else:
                print(f"[{symbol}] ⚠️ Side inválido ou posição não identificada: {side}")

        except Exception as e:
            error_msg = f'❌ Erro crítico no stop dinâmico para {symbol}: {str(e)[:200]}'
            print(error_msg)
            import traceback
            print(traceback.format_exc())
            
            if context:
                try:
                    await self.enviar_mensagem(context, f"❌ Erro no stop dinâmico de {symbol}: {str(e)[:100]}")
                except Exception as notify_error:
                    print(f"[{symbol}] Erro ao notificar erro crítico: {notify_error}")
            
# Exemplo de uso:
# gr = GerenciamentoRiscoAsync()
# await gr.fecha_pnl('BTC/USDT', -5, 10, context)
# await gr.close()