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
        self.session = aiohttp.ClientSession()
        self._is_trailing_active: Dict[str, bool] = {} 
        self._load_trailing_data() 

    def _load_trailing_data(self):
            """Carrega os dados do trailing stop do arquivo JSON."""
            if os.path.exists(TRAILING_DATA_FILE):
                try:
                    with open(TRAILING_DATA_FILE, 'r') as f:
                        data = json.load(f)
                        for symbol, values in data.items():
                            self._highest_profit_reached[symbol] = values.get("highest_profit_percentage", -float('inf'))
                            self._is_trailing_active[symbol] = values.get("is_trailing_active", False)
                except json.JSONDecodeError as e:
                    print(f"Erro ao carregar {TRAILING_DATA_FILE}: {e}. O arquivo pode estar corrompido.")
                    # Opcional: fazer um backup do arquivo corrompido e criar um novo vazio
            else:
                print(f"Arquivo {TRAILING_DATA_FILE} não encontrado. Será criado se necessário.")
                self._highest_profit_reached = {}
                self._is_trailing_active = {}

    def _save_trailing_data(self):
        """Salva os dados atuais do trailing stop no arquivo JSON."""
        # Filtra apenas os símbolos que realmente têm dados de trailing ativos ou picos registrados
        data_to_save = {}
        for symbol in set(self._highest_profit_reached.keys()) | set(self._is_trailing_active.keys()):
            if symbol in self._highest_profit_reached and not math.isinf(self._highest_profit_reached[symbol]):
                 data_to_save[symbol] = {
                    "highest_profit_percentage": self._highest_profit_reached.get(symbol, -float('inf')),
                    "is_trailing_active": self._is_trailing_active.get(symbol, False)
                }

        # Garante que o diretório exista
        os.makedirs(CONFIG_DIR, exist_ok=True)
        try:
            with open(TRAILING_DATA_FILE, 'w') as f:
                json.dump(data_to_save, f, indent=2)
        except Exception as e:
            print(f"Erro ao salvar {TRAILING_DATA_FILE}: {e}")

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

    async def encerra_posicao(self, symbol: str, context: CallbackContext = None) -> None:
        """Fecha uma posição de forma assíncrona"""
        try:
            while True:
                side, amount, _, is_open, _, _, _ = await self.posicoes_abertas(symbol)
                if not is_open:
                    if context:
                        await self.enviar_mensagem(context, 'Posição fechada')
                    break

                await self.binance_handler.client.cancel_all_orders (symbol)
                bid, ask = await self.livro_ofertas(symbol)

                if side == 'long':
                    price = self.binance_handler.client.price_to_precision(symbol, ask)
                    await self.binance_handler.client.create_order(
                        symbol, side='sell', type= 'LIMIT', amount=amount, price=price,
                        params={'hedged': 'true'}
                    )
                    msg = f'Fechando long: {amount} de {symbol}'
                elif side == 'short':
                    price = self.binance_handler.client.price_to_precision(symbol, bid)
                    await self.binance_handler.client.create_order(
                        symbol, side='buy', type= 'LIMIT',amount= amount, price=price,
                        params={'hedged': 'true'}
                    )
                    msg = f'Fechando short: {amount} de {symbol}'
                else:
                    msg = 'Impossível encerrar a posição!'

                if context:
                    await self.enviar_mensagem(context, msg)
                await asyncio.sleep(10)

        except Exception as e:
            error_msg = f'Erro ao encerrar posição: {str(e)}'
            print(error_msg)
            if context:
                await self.enviar_mensagem(context, error_msg)

    # async def fecha_pnl(self, symbol: str, loss: float, target: float, context: CallbackContext = None) -> None:
    #     """Gerencia stop loss e take profit de forma assíncrona"""
    #     try:
    #         _, _, _, _, _, percentage, pnl = await self.posicoes_abertas(symbol)
            
    #         if percentage:
    #             pnl_formatted = f"{float(pnl):.2f}"
                
    #             if percentage <= loss:
    #                 print(f'Encerrando posição por loss! {pnl}')
    #                 await self.encerra_posicao(symbol, context)
    #                 msg = f'LOSS de {pnl_formatted} USD'
    #                 if context:
    #                     await self.enviar_mensagem(context, msg)
                    
    #             elif percentage >= target:
    #                 print(f'Encerrando posição por gain! {pnl}')
    #                 await self.encerra_posicao(symbol, context)
    #                 msg = f'GAIN de {pnl_formatted} USD'
    #                 if context:
    #                     await self.enviar_mensagem(context, msg)

    #     except Exception as e:
    #         error_msg = f'Erro no gerenciamento de PNL: {str(e)}'
    #         print(error_msg)
    #         if context:
    #             await self.enviar_mensagem(context, error_msg)

    # async def fecha_pnl(self, 
    #                     symbol: str, 
    #                     loss: float, 
    #                     target: float, 
    #                     trailing_activation_percentage: Optional[float] = None,
    #                     trailing_distance_percentage: Optional[float] = None,   
    #                     context: Optional[CallbackContext] = None) -> None:
    #     """
    #     Gerencia stop loss e take profit de forma assíncrona com Trailing Stop Dinâmico.
    #     """
        
    #     if symbol not in self._highest_profit_reached:
    #         self._highest_profit_reached[symbol] = -float('inf')
    #         self._is_trailing_active[symbol] = False 

    #     current_loss_threshold = loss
        
    #     try:
    #         _, _, _, _, _, percentage, pnl = await self.posicoes_abertas(symbol)
            
    #         if percentage is not None:
    #             pnl_formatted = f"{float(pnl):.2f}"
                
    #             if trailing_activation_percentage is not None and trailing_distance_percentage is not None:
                    
                    
    #                 if percentage > self._highest_profit_reached[symbol]:
    #                     self._highest_profit_reached[symbol] = percentage
                        
    #                     self._save_trailing_data()
    #                     # Opcional: notificar sobre um novo pico se o trailing já estiver ativo
    #                     if self._is_trailing_active[symbol]:
    #                         print(f"Novo pico para {symbol}: {self._highest_profit_reached[symbol]:.2%}")

    #                 if self._highest_profit_reached[symbol] >= trailing_activation_percentage:
                        
    #                     if not self._is_trailing_active[symbol]:
    #                         self._is_trailing_active[symbol] = True
    #                         self._save_trailing_data() 
    #                         print(f"Trailing Stop ATIVADO para {symbol} em {self._highest_profit_reached[symbol]:.2%}")
    #                         if context:
    #                             await self.enviar_mensagem(context, 
    #                                 f"Trailing Stop ATIVADO para {symbol}! Lucro de {self._highest_profit_reached[symbol]:.2%}.")

    #                     calculated_trailing_sl = self._highest_profit_reached[symbol] - trailing_distance_percentage
                        
    #                     current_loss_threshold = max(current_loss_threshold, calculated_trailing_sl)

    #                     if not math.isclose(current_loss_threshold, loss) and \
    #                        (self._highest_profit_reached[symbol] >= trailing_activation_percentage and \
    #                         (calculated_trailing_sl > loss or self._is_trailing_active[symbol])):
    #                         print(f"Trailing Ajustado para {symbol}: "
    #                               f"Pico de Lucro: {self._highest_profit_reached[symbol]:.2%}, "
    #                               f"Distância: {trailing_distance_percentage:.2%}. "
    #                               f"SL Calculado: {calculated_trailing_sl:.2%}. "
    #                               f"SL Atual: {current_loss_threshold:.2%}.")
    #                 else:
    #                     print(f"Trailing para {symbol} não ativado. Lucro atual: {percentage:.2%}, "
    #                           f"Pico: {self._highest_profit_reached[symbol]:.2%}. "
    #                           f"Aguardando {trailing_activation_percentage:.2%} para ativar.")
    #             else:
    #                 print(f"Trailing Stop Dinâmico não configurado para {symbol}. Usando Stop Loss Fixo: {current_loss_threshold:.2%}.")

    #             if percentage <= current_loss_threshold:
    #                 print(f'Encerrando posição por LOSS! PNL: {pnl_formatted} USD (Limite: {current_loss_threshold:.2%})')
    #                 await self.encerra_posicao(symbol, context)
    #                 msg = f'LOSS de {pnl_formatted} USD (atingiu {current_loss_threshold:.2%}) em {symbol}'
    #                 if context:
    #                     await self.enviar_mensagem(context, msg)
                    
    #             elif percentage >= target:
    #                 print(f'Encerrando posição por GAIN! PNL: {pnl_formatted} USD (Alvo: {target:.2%})')
    #                 await self.encerra_posicao(symbol, context)
    #                 msg = f'GAIN de {pnl_formatted} USD (atingiu {target:.2%}) em {symbol}'
    #                 if context:
    #                     await self.enviar_mensagem(context, msg)
    #             else:
    #                 print(f"Posição {symbol} em aberto: PNL atual {percentage:.2%}. "
    #                       f"Stop Loss em {current_loss_threshold:.2%}, Target em {target:.2%}.")

    #         else:
    #             print(f"Não foi possível obter o percentual de PNL para {symbol}. Posição pode não estar aberta ou dados inválidos.")

    #     except Exception as e:
    #         error_msg = f'Erro no gerenciamento de PNL para {symbol}: {str(e)}'
    #         print(error_msg)
    #         if context:
    #             await self.enviar_mensagem(context, error_msg)

    # async def fecha_pnl(self, 
    #                 symbol: str, 
    #                 loss: float, 
    #                 target: float, 
    #                 trailing_activation_percentage: Optional[float] = None,
    #                 trailing_distance_percentage: Optional[float] = None,   
    #                 context: Optional[CallbackContext] = None) -> None:
    #     """
    #     Gerencia stop loss e take profit de forma assíncrona com Trailing Stop Dinâmico.
    #     """

    #     # Inicializa os dados do trailing se ainda não estiverem prontos
    #     if symbol not in self._highest_profit_reached:
    #         self._highest_profit_reached[symbol] = -float('inf')
    #         self._is_trailing_active[symbol] = False

    #     try:
    #         # Obtém os dados da posição atual
    #         side, amount, entry_price, is_open, entry_time, percentage, pnl = await self.posicoes_abertas(symbol)

    #         if percentage is None:
    #             print(f"[{symbol}] Posição aparentemente não está aberta ou dados inválidos.")
    #             return

    #         pnl_formatted = f"{float(pnl):.2f}"
    #         highest = self._highest_profit_reached[symbol]
    #         trailing_ativo = self._is_trailing_active[symbol]

    #         # Atualiza o maior lucro já atingido
    #         if percentage > highest:
    #             self._highest_profit_reached[symbol] = percentage
    #             self._save_trailing_data()
    #             if trailing_ativo:
    #                 print(f"[{symbol}] Novo pico de lucro: {percentage:.2%}")

    #         # Decide se trailing será ativado
    #         if trailing_activation_percentage is not None and trailing_distance_percentage is not None:
    #             if percentage >= trailing_activation_percentage:
    #                 if not trailing_ativo:
    #                     self._is_trailing_active[symbol] = True
    #                     self._save_trailing_data()
    #                     print(f"[{symbol}] ✅ Trailing Stop ativado! Lucro = {percentage:.2%}")
    #                     if context:
    #                         await self.enviar_mensagem(context, f"Trailing Stop ativado para {symbol} com lucro de {percentage:.2%}")

    #                 # Calcula o trailing stop com base no pico de lucro
    #                 calculated_trailing_sl = self._highest_profit_reached[symbol] - trailing_distance_percentage

    #                 # Trailing só é usado se estiver abaixo do lucro atual
    #                 if calculated_trailing_sl < percentage:
    #                     current_loss_threshold = calculated_trailing_sl
    #                 else:
    #                     current_loss_threshold = loss
    #             else:
    #                 current_loss_threshold = loss
    #         else:
    #             current_loss_threshold = loss

    #         # Evita que o "stop" fique maior que 0 (o que não é stop loss, mas lucro)
    #         if current_loss_threshold > 0:
    #             print(f"[{symbol}] ⚠️ Stop Loss ajustado manualmente para 0 pois valor calculado foi positivo ({current_loss_threshold:.2%})")
    #             current_loss_threshold = 0

    #         print(f"[{symbol}] 📊 PNL: {percentage:.2%} | Stop: {current_loss_threshold:.2%} | Target: {target:.2%}")

    #         # Lógica de encerramento por LOSS
    #         if percentage <= current_loss_threshold:
    #             print(f"[{symbol}] 🚨 Encerrando por LOSS. PNL: {pnl_formatted} USD")
    #             await self.encerra_posicao(symbol, context)
    #             msg = f"❌ LOSS de {pnl_formatted} USD (atingiu {percentage:.2%}) em {symbol}"
    #             if context:
    #                 await self.enviar_mensagem(context, msg)

    #         # Lógica de encerramento por GAIN
    #         elif percentage >= target:
    #             print(f"[{symbol}] ✅ Encerrando por GAIN. PNL: {pnl_formatted} USD")
    #             await self.encerra_posicao(symbol, context)
    #             msg = f"✅ GAIN de {pnl_formatted} USD (atingiu {percentage:.2%}) em {symbol}"
    #             if context:
    #                 await self.enviar_mensagem(context, msg)

    #         else:
    #             print(f"[{symbol}] ⏳ Posição em aberto. PNL atual: {percentage:.2%}")

    #     except Exception as e:
    #         error_msg = f"Erro no gerenciamento de PNL para {symbol}: {str(e)}"
    #         print(error_msg)
    #         if context:
    #             await self.enviar_mensagem(context, error_msg)

    async def fecha_pnl(self, 
                        symbol: str, 
                        loss: float, 
                        target: float, 
                        context: Optional[CallbackContext] = None) -> None:
        """
        Gerencia stop loss e take profit de forma assíncrona com Trailing Stop por pontos fixos.
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
            1.00: 0.90,  # 100% de lucro (seu stop gain) -> trailing stop em 90%
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
            self._is_trailing_active[symbol] = False # Mantido para consistência, mas o uso é diferente

        try:
            # Obtém os dados da posição atual
            side, amount, entry_price, is_open, entry_time, percentage, pnl = await self.posicoes_abertas(symbol)

            if percentage is None:
                print(f"[{symbol}] Posição aparentemente não está aberta ou dados inválidos.")
                return

            pnl_formatted = f"{float(pnl):.2f}"
            highest = self._highest_profit_reached[symbol]
            
            if percentage > highest:
                self._highest_profit_reached[symbol] = percentage
                self._save_trailing_data()
          
            current_loss_threshold = loss

            sorted_targets = sorted(fixed_trailing_stops.keys())
            
            for target_profit in sorted_targets:
                if percentage >= target_profit:
                    
                    current_loss_threshold = fixed_trailing_stops[target_profit]
                    
                    if not self._is_trailing_active[symbol]: 
                        self._is_trailing_active[symbol] = True
                        print(f"[{symbol}] ✅ Trailing Stop ajustado para {current_loss_threshold:.2%} (alvo: {target_profit:.2%})")
                        if context:
                            await self.enviar_mensagem(context, f"Trailing Stop para {symbol} ajustado para {current_loss_threshold:.2%} ao atingir {target_profit:.2%}")
                else:
                    
                    break 

            
            if current_loss_threshold > 0 and percentage < current_loss_threshold:
                 
                 if loss <= 0: 
                    current_loss_threshold = max(current_loss_threshold, 0)
                 print(f"[{symbol}] ⚠️ Stop Loss ajustado para {current_loss_threshold:.2%} se o valor calculado foi positivo.")


            print(f"[{symbol}] 📊 PNL: {percentage:.2%} | Stop (ajustado): {current_loss_threshold:.2%} | Target (original): {target:.2%}")

            # Lógica de encerramento por LOSS
            if percentage <= current_loss_threshold:
                print(f"[{symbol}] 🚨 Encerrando por LOSS (ou Trailing Stop atingido). PNL: {pnl_formatted} USD")
                await self.encerra_posicao(symbol, context)
                msg = f"❌ Saída por {('Trailing Stop' if current_loss_threshold > loss else 'LOSS')} de {pnl_formatted} USD (atingiu {percentage:.2%}, stop em {current_loss_threshold:.2%}) em {symbol}"
                if context:
                    await self.enviar_mensagem(context, msg)
                
                del self._highest_profit_reached[symbol]
                del self._is_trailing_active[symbol]

            elif percentage >= target:
                print(f"[{symbol}] ✅ Encerrando por GAIN. PNL: {pnl_formatted} USD")
                await self.encerra_posicao(symbol, context)
                msg = f"✅ GAIN de {pnl_formatted} USD (atingiu {percentage:.2%}) em {symbol}"
                if context:
                    await self.enviar_mensagem(context, msg)
                
                del self._highest_profit_reached[symbol]
                del self._is_trailing_active[symbol]

            else:
                print(f"[{symbol}] ⏳ Posição em aberto. PNL atual: {percentage:.2%}")

        except Exception as e:
            error_msg = f"Erro no gerenciamento de PNL para {symbol}: {str(e)}"
            print(error_msg)
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

    async def stop_dinamico(self, symbol: str, take_profit: float, stop_loss: float, context: CallbackContext = None) -> None:
        """Ajusta stops dinâmicos de forma assíncrona"""
        try:
            position = await self.binance_handler.client.fetch_positions (symbols=[symbol])[0]
            if not position:
                return

            side = position['side']
            amount = position['info']['positionAmt'].replace('-', '')
            entry_price = position['entryPrice']
            mark_price = float(position['info']['markPrice'])

            if not amount or float(amount) == 0:
                return

            orders = await self.binance_handler.client.fetch_orders (symbol)
            if not orders:
                return

            last_order = orders[-1]
            take_profit_price = float(self.binance_handler.client.price_to_precision(symbol, last_order['stopPrice']))

            if side == 'long':
                price_var = ((mark_price - entry_price) / entry_price) * 100
                print(f'{symbol}: {price_var:.2f}% em relação a entrada do {side}')

                if ((take_profit_price - mark_price) / mark_price) <= (0.2 * take_profit):
                    await self.binance_handler.client.cancel_all_orders (symbol)
                    last_trade = self.binance_handler.client.fetch_trades (symbol)[-1]
                    current_price = float(self.binance_handler.client.price_to_precision(symbol, last_trade['price']))

                    stop_loss_price = current_price * (1 - stop_loss)
                    take_profit_price = current_price * (1 + take_profit)

                    await self.binance_handler.create_order(
                        symbol=symbol, side='sell', type='STOP_MARKET',
                        amount=amount, params={'stopPrice': stop_loss_price}
                    )
                    await self.binance_handler.create_order(
                        symbol=symbol, side='sell', type='TAKE_PROFIT_MARKET',
                        amount=amount, params={'stopPrice': take_profit_price}
                    )
                    msg = f'Stop loss e Take Profit atualizadas no long em {symbol}'
                    if context:
                        await self.enviar_mensagem(context, msg)

            elif side == 'short':
                price_var = ((entry_price - mark_price) / mark_price) * 100
                print(f'{symbol}: {price_var:.2f}% em relação a entrada do {side}')

                if ((mark_price - take_profit_price) / take_profit_price) <= (0.2 * take_profit):
                    await self.binance_handler.client.cancel_all_orders (symbol)
                    last_trade = await self.binance_handler.client.fetch_trades (symbol)[-1]
                    current_price = float(self.binance_handler.client.price_to_precision(symbol, last_trade['price']))

                    stop_loss_price = current_price * (1 + stop_loss)
                    take_profit_price = current_price * (1 - take_profit)

                    await self.binance_handler.client.create_order(
                        symbol=symbol, side='buy', type='STOP_MARKET',
                        amount=amount, params={'stopPrice': stop_loss_price}
                    )
                    await self.binance_handler.client.create_order(
                        symbol=symbol, side='buy', type='TAKE_PROFIT_MARKET',
                        amount=amount, params={'stopPrice': take_profit_price}
                    )
                    msg = f'Stop loss e Take Profit atualizadas no short em {symbol}'
                    if context:
                        await self.enviar_mensagem(context, msg)

        except Exception as e:
            error_msg = f'Erro no stop dinâmico: {str(e)}'
            print(error_msg)
            if context:
                await self.enviar_mensagem(context, error_msg)

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

# Exemplo de uso:
# gr = GerenciamentoRiscoAsync()
# await gr.fecha_pnl('BTC/USDT', -5, 10, context)
# await gr.close()