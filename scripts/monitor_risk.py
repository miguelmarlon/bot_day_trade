"""
Monitor de Gerenciamento de Risco - Processo Independente
Monitora continuamente todas as posições abertas e aplica stop dinâmico.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import asyncio
import logging
from typing import Dict, Set
from telegram.ext import CallbackContext
from utils.binance_client import BinanceHandler
from scripts.gerenciamento_risco_assin import GerenciamentoRiscoAsync

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Cache de posições monitoradas para evitar spam de notificações
_positions_cache: Set[str] = set()

# Cache para armazenar última porcentagem notificada por símbolo
# Formato: {symbol: last_notified_percentage}
_last_notified_pnl: Dict[str, float] = {}


async def _notify_pnl_change(
    symbol: str,
    current_pnl_percentage: float,
    unrealized_pnl: float,
    side: str,
    context: CallbackContext,
    chat_id: int
) -> None:
    """
    Notifica mudanças significativas no PNL (0.5% ou mais).
    
    Args:
        symbol: Símbolo do ativo
        current_pnl_percentage: Percentual atual de PNL
        unrealized_pnl: PNL não realizado em USD
        side: Lado da posição ('long' ou 'short')
        context: Contexto do Telegram
        chat_id: ID do chat
    """
    global _last_notified_pnl
    
    # Inicializa se for primeira vez
    if symbol not in _last_notified_pnl:
        _last_notified_pnl[symbol] = current_pnl_percentage
        # Notifica posição inicial
        side_emoji = "🟢" if side == 'long' else "🔴"
        status_emoji = "📈" if current_pnl_percentage >= 0 else "📉"
        
        msg = (
            f"{side_emoji} *{symbol}* | {side.upper()}\n"
            f"{status_emoji} PNL: *{current_pnl_percentage:+.2f}%* (${unrealized_pnl:+.2f})"
        )
        
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=msg,
                parse_mode='Markdown'
            )
            logger.info(f"📊 Notificação inicial enviada para {symbol}: {current_pnl_percentage:.2f}%")
        except Exception as e:
            logger.error(f"Erro ao enviar notificação inicial para {symbol}: {e}")
        return
    
    last_pnl = _last_notified_pnl[symbol]
    pnl_change = abs(current_pnl_percentage - last_pnl)

    # Notifica se mudou 1.0% ou mais
    if pnl_change >= 1.0:
        # Determina direção da mudança
        if current_pnl_percentage > last_pnl:
            direction = "⬆️"
            change_text = f"+{current_pnl_percentage - last_pnl:.2f}%"
        else:
            direction = "⬇️"
            change_text = f"{current_pnl_percentage - last_pnl:.2f}%"
        
        # Emoji de status
        side_emoji = "🟢" if side == 'long' else "🔴"
        
        # Emoji baseado no valor atual
        if current_pnl_percentage >= 2.0:
            status_emoji = "🚀"  # Lucro alto
        elif current_pnl_percentage >= 1.0:
            status_emoji = "📈"  # Lucro médio
        elif current_pnl_percentage >= 0:
            status_emoji = "➡️"  # Break-even ou pequeno lucro
        elif current_pnl_percentage >= -1.0:
            status_emoji = "⚠️"  # Pequeno prejuízo
        else:
            status_emoji = "🔻"  # Prejuízo significativo
        
        msg = (
            f"{side_emoji} *{symbol}* {direction}\n"
            f"{status_emoji} PNL: *{current_pnl_percentage:+.2f}%* (${unrealized_pnl:+.2f})\n"
            f"Δ {change_text}"
        )
        
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=msg,
                parse_mode='Markdown'
            )
            logger.info(f"📊 {symbol} mudou {pnl_change:.2f}% → Notificação enviada")
        except Exception as e:
            logger.error(f"Erro ao enviar notificação de mudança para {symbol}: {e}")
        
        # Atualiza cache
        _last_notified_pnl[symbol] = current_pnl_percentage

async def monitor_risk_management(context: CallbackContext) -> None:
    """
    Job que monitora todas as posições abertas e aplica gerenciamento de risco.
    
    Esta função:
    1. Busca TODAS as posições abertas na conta
    2. Aplica stop_dinamico para cada posição
    3. Roda a cada 1 minuto de forma independente
    
    Args:
        context: Contexto do Telegram para notificações
    """
    binance = None
    gerenciador = None
    
    try:
        chat_id = context.job.chat_id if hasattr(context, 'job') else context._chat_id
        
        # Cria conexão com Binance
        binance = await BinanceHandler.create(testnet=True)
        gerenciador = GerenciamentoRiscoAsync(binance_handler=binance)
        
        # Busca TODAS as posições abertas na conta (muito mais eficiente)
        try:
            all_positions = await asyncio.wait_for(
                binance.client.fetch_positions(),
                timeout=20.0
            )
        except asyncio.TimeoutError:
            logger.error("⏱️ Timeout ao buscar posições no monitor de risco")
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ Timeout ao buscar posições no monitor de risco"
            )
            return
        
        # Filtra apenas posições realmente abertas
        open_positions = [
            pos for pos in all_positions
            if pos.get('contracts', 0) > 0 and pos.get('side') in ('long', 'short')
        ]
        
        if not open_positions:
            # Limpa cache se não há posições
            if _positions_cache:
                logger.info("📊 Nenhuma posição aberta. Limpando cache.")
                _positions_cache.clear()
            return
        
        # Detecta novas posições para notificar
        current_symbols = {pos['symbol'] for pos in open_positions}
        new_positions = current_symbols - _positions_cache
        closed_positions = _positions_cache - current_symbols
        
        # Notifica novas posições detectadas
        if new_positions:
            logger.info(f"🆕 Novas posições detectadas: {', '.join(new_positions)}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🆕 Monitor de risco ativado para: {', '.join(new_positions)}"
            )
        
        # Notifica posições fechadas
        if closed_positions:
            logger.info(f"✅ Posições fechadas: {', '.join(closed_positions)}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ Posições fechadas: {', '.join(closed_positions)}"
            )
            
            # Limpa cache de PNL das posições fechadas
            for symbol in closed_positions:
                if symbol in _last_notified_pnl:
                    del _last_notified_pnl[symbol]
                    logger.debug(f"🗑️ Cache de PNL removido para {symbol}")
        
        # Atualiza cache
        _positions_cache.clear()
        _positions_cache.update(current_symbols)
        
        logger.info(f"📊 Monitorando {len(open_positions)} posição(ões) aberta(s)")
        
        # Processa cada posição aberta
        for position in open_positions:
            symbol = position['symbol']
            contracts = position.get('contracts', 0)
            side = position.get('side')
            
            # Calcula PNL atual da posição
            entry_price = float(position.get('entryPrice', 0))
            mark_price = float(position.get('info', {}).get('markPrice', 0))
            unrealized_pnl = float(position.get('info', {}).get('unRealizedProfit', 0))
            
            # Calcula percentual de lucro/prejuízo
            pnl_percentage = 0.0
            if entry_price > 0 and contracts > 0:
                position_value = entry_price * contracts
                if position_value > 0:
                    pnl_percentage = (unrealized_pnl / position_value) * 100
            
            logger.info(f"🔍 Verificando {symbol} | Side: {side} | PNL: {pnl_percentage:.2f}% (${unrealized_pnl:.2f})")
            
            # Notifica mudanças de 0.5% ou mais no PNL
            await _notify_pnl_change(
                symbol=symbol,
                current_pnl_percentage=pnl_percentage,
                unrealized_pnl=unrealized_pnl,
                side=side,
                context=context,
                chat_id=chat_id
            )
            
            # Configurações de risco (podem ser lidas de um config por símbolo)
            # Por enquanto, usa valores padrão
            take_profit = 0.04  # 4%
            stop_loss = 0.02    # 2%
            
            try:
                # Aplica stop dinâmico
                await asyncio.wait_for(
                    gerenciador.stop_dinamico(
                        symbol=symbol,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                        context=context
                    ),
                    timeout=30.0  # Timeout por símbolo
                )
                
            except asyncio.TimeoutError:
                logger.error(f"⏱️ Timeout ao processar stop dinâmico para {symbol}")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Timeout ao processar {symbol}"
                )
                
            except Exception as symbol_error:
                logger.error(f"❌ Erro ao processar {symbol}: {symbol_error}")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Erro ao processar {symbol}: {str(symbol_error)[:100]}"
                )
            
            # Pequena pausa entre símbolos para não sobrecarregar a API
            await asyncio.sleep(1)
        
        logger.info(f"✅ Ciclo de monitoramento concluído - {len(open_positions)} posição(ões) verificada(s)")
    
    except Exception as e:
        error_msg = f"❌ Erro crítico no monitor de risco: {str(e)[:200]}"
        logger.error(error_msg)
        import traceback
        logger.error(traceback.format_exc())
        
        try:
            await context.bot.send_message(
                chat_id=context.job.chat_id if hasattr(context, 'job') else context._chat_id,
                text=error_msg
            )
        except Exception as notify_error:
            logger.error(f"Erro ao notificar erro crítico: {notify_error}")
    
    finally:
        # Fecha recursos
        if gerenciador:
            try:
                await gerenciador.close()
                logger.debug("✅ Gerenciador de risco fechado")
            except Exception as close_error:
                logger.error(f"⚠️ Erro ao fechar gerenciador: {close_error}")
        
        if binance:
            try:
                await binance.close_connection()
                logger.debug("✅ Conexão Binance fechada")
            except Exception as close_error:
                logger.error(f"⚠️ Erro ao fechar conexão: {close_error}")

async def monitor_risk_management_with_config(context: CallbackContext, config_file: str = 'config/risk_config.json') -> None:
    """
    Versão avançada que lê configurações de risco por símbolo de um arquivo JSON.
    
    Exemplo de config/risk_config.json:
    {
        "default": {
            "take_profit": 0.04,
            "stop_loss": 0.02
        },
        "BTC/USDT": {
            "take_profit": 0.06,
            "stop_loss": 0.03
        },
        "ETH/USDT": {
            "take_profit": 0.05,
            "stop_loss": 0.025
        }
    }
    """
    import json
    import os
    
    # Carrega configurações
    config = {"default": {"take_profit": 0.04, "stop_loss": 0.02}}
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"✅ Configurações de risco carregadas de {config_file}")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao carregar {config_file}: {e}. Usando configurações padrão.")
    
    binance = None
    gerenciador = None
    
    try:
        chat_id = context.job.chat_id if hasattr(context, 'job') else context._chat_id
        
        binance = await BinanceHandler.create(testnet=False)
        gerenciador = GerenciamentoRiscoAsync(binance_handler=binance)
        
        all_positions = await asyncio.wait_for(
            binance.client.fetch_positions(),
            timeout=20.0
        )
        
        open_positions = [
            pos for pos in all_positions
            if pos.get('contracts', 0) > 0 and pos.get('side') in ('long', 'short')
        ]
        
        if not open_positions:
            if _positions_cache:
                _positions_cache.clear()
            return
        
        current_symbols = {pos['symbol'] for pos in open_positions}
        new_positions = current_symbols - _positions_cache
        closed_positions = _positions_cache - current_symbols
        
        if new_positions:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🆕 Monitor de risco ativado para: {', '.join(new_positions)}"
            )
        
        if closed_positions:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ Posições fechadas: {', '.join(closed_positions)}"
            )
            
            # Limpa cache de PNL das posições fechadas
            for symbol in closed_positions:
                if symbol in _last_notified_pnl:
                    del _last_notified_pnl[symbol]
        
        _positions_cache.clear()
        _positions_cache.update(current_symbols)
        
        logger.info(f"📊 Monitorando {len(open_positions)} posição(ões) com configurações customizadas")
        
        for position in open_positions:
            symbol = position['symbol']
            contracts = position.get('contracts', 0)
            side = position.get('side')
            
            # Calcula PNL atual da posição
            entry_price = float(position.get('entryPrice', 0))
            mark_price = float(position.get('info', {}).get('markPrice', 0))
            unrealized_pnl = float(position.get('info', {}).get('unRealizedProfit', 0))
            
            # Calcula percentual de lucro/prejuízo
            pnl_percentage = 0.0
            if entry_price > 0 and contracts > 0:
                position_value = entry_price * contracts
                if position_value > 0:
                    pnl_percentage = (unrealized_pnl / position_value) * 100
            
            # Notifica mudanças de 0.5% ou mais no PNL
            await _notify_pnl_change(
                symbol=symbol,
                current_pnl_percentage=pnl_percentage,
                unrealized_pnl=unrealized_pnl,
                side=side,
                context=context,
                chat_id=chat_id
            )
            
            # Busca configuração específica do símbolo ou usa padrão
            symbol_config = config.get(symbol, config.get("default"))
            take_profit = symbol_config.get("take_profit", 0.04)
            stop_loss = symbol_config.get("stop_loss", 0.02)
            
            logger.info(f"🔍 {symbol} | TP: {take_profit*100:.1f}% | SL: {stop_loss*100:.1f}% | PNL: {pnl_percentage:.2f}%")
            
            try:
                await asyncio.wait_for(
                    gerenciador.stop_dinamico(
                        symbol=symbol,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                        context=context
                    ),
                    timeout=30.0
                )
            except Exception as symbol_error:
                logger.error(f"❌ Erro ao processar {symbol}: {symbol_error}")
            
            await asyncio.sleep(1)
    
    except Exception as e:
        logger.error(f"❌ Erro crítico: {e}")
    
    finally:
        if gerenciador:
            await gerenciador.close()
        if binance:
            await binance.close_connection()
