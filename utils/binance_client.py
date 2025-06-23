import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import ccxt
import ccxt.pro as ccxt_pro
import pandas as pd
import asyncio
import time
from config.config import BINANCE_API_KEY, BINANCE_SECRET_KEY
from scripts.gerenciamento_risco_assin import GerenciamentoRiscoAsync

class BinanceHandler:
    """
    Uma classe para gerenciar interações com a API da Binance de forma assíncrona.

    Uso recomendado:
    handler = await BinanceHandler.create()
    # ... use os métodos do handler ...
    await handler.close_connection()
    """

    # O __init__ é síncrono e "privado" por convenção.
    # A criação de instâncias deve ser feita pelo método 'create'.
    def __init__(self, client):
        if not client:
            raise ValueError("O cliente CCXT não pode ser nulo.")
        self.client = client
        print("✅ Handler da Binance inicializado com sucesso.")
    
    @classmethod
    async def create(cls):
        """
        Método de fábrica assíncrono para criar e retornar uma instância de BinanceHandler.
        """
        print("🔌 Conectando à Binance...")

        client = ccxt_pro.binance({
            'apiKey': BINANCE_API_KEY,
            'secret': BINANCE_SECRET_KEY,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        # Retorna uma nova instância da classe, passando o cliente conectado.
        return cls(client)
    
    async def close_connection(self):
        """Fecha a conexão com a corretora de forma segura."""
        print("\n🔌 Fechando a conexão com a Binance...")
        await self.client.close()
    
    # async def conectar_binance():
    #     """
    #     Cria e configura um cliente ccxt.pro para os mercados Futuros da Binance.
    #     Esta função é síncrona, pois apenas instancia o objeto.
    #     """
    #     if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
    #         raise ValueError("As chaves de API da Binance não foram configuradas como variáveis de ambiente.")

    #     print("🔧 Configurando cliente para Binance Futures...")
    #     exchange = ccxt_pro.binance({
    #         'enableRateLimit': True,
    #         'apiKey': BINANCE_API_KEY,
    #         'secret': BINANCE_SECRET_KEY,
    #         'options': {'defaultType': 'future'}
    #     })
    #     return exchange

    async def obter_dados_candles(self, symbol: str, timeframe='1h', limit=300):
        """
        Busca os dados de candles para um par de Futuros.
        Agora é um método de instância que usa self.client.
        """

        bars = await self.client.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
        df_candles = pd.DataFrame(bars, columns=['time', 'abertura', 'max', 'min', 'fechamento', 'volume'])
        df_candles['time'] = pd.to_datetime(df_candles['time'], unit='ms', utc=True).map(lambda x: x.tz_convert('America/Sao_Paulo'))
        return df_candles

    async def abrir_short(self, symbol, posicao_max, context):
        async with GerenciamentoRiscoAsync as gr:
            try:
                bid, ask = await gr.livro_ofertas(symbol)
                ask =  self.client.price_to_precision(symbol, ask)
                await self.client.create_order(
                    symbol, 
                    side='sell', 
                    type='LIMIT', 
                    price=ask,
                    amount=posicao_max,
                    params={'hedged': 'true', 'postOnly': True}
                )
                print("***** Executando Ordem de Venda - Short *****")
                msg = (
                    f"✅**Ordem de Venda (Short) Enviada!**\n"
                    f"🔹**Par de Mercado:** {symbol}\n"
                    f"🔹**Tipo de Ordem:** LIMIT\n"
                    f"💲**Preço de Entrada:** {ask}\n"
                    f"📊**Quantidade:** {posicao_max} {symbol.split('/')[0]}"
                )
            except ccxt_pro.ExchangeError as e:
                print(f"**** Problema de comunicação com a corretora! Erro: {e} ****")
                msg = f"❌ Erro da Corretora em {symbol}: {e}"
            except Exception as e:
                print(f"**** Problema ao abrir short! Erro: {e} ****")
                msg = f"❌ Erro ao abrir short em {symbol}: {e}"

            await context.bot.send_message(chat_id=context.job.chat_id, text=msg, parse_mode="Markdown")

    async def abrir_long(self, symbol, posicao_max, context):
        async with GerenciamentoRiscoAsync as gr:
            try:
                bid, ask = await gr.livro_ofertas(symbol)
                bid = self.client.price_to_precision(symbol, bid)
                
                await self.client.create_order(
                    symbol,
                    side='buy',
                    type='LIMIT',
                    amount=posicao_max,
                    price=bid,
                    params={'hedged': 'true', 'postOnly': True}
                )
                
                print("***** Executando Ordem de Compra - Long *****")
                msg = (
                    f"✅**Ordem de Compra (Long) Enviada!**\n"
                    f"🔹**Par de Mercado:** {symbol}\n"
                    f"🔹**Tipo de Ordem:** LIMIT\n"
                    f"💲**Preço de Entrada:** {bid}\n"
                    f"📊**Quantidade:** {posicao_max} {symbol.split('/')[0]}"
                )
            except ccxt_pro.ExchangeError as e:
                # Captura erros específicos da corretora: fundos insuficientes, par inválido, etc.
                print(f"**** Problema de comunicação com a corretora! Erro: {e} ****")
                msg = f"❌ Erro da Corretora em {symbol}: {e}"
            except Exception as e:
                print(f"**** Problema ao abrir long! Erro: {e} ****")
                msg = f"❌ Erro ao abrir long em {symbol}: {e}"

            await context.bot.send_message(chat_id=context.job.chat_id, text=msg, parse_mode="Markdown")

    async def cancelar_todas_as_ordens(self, symbol, context):
        """Cancela todas as ordens abertas para um símbolo."""
        async with GerenciamentoRiscoAsync as gr:
            if await gr.ultima_ordem_aberta(symbol):
                try:
                    response = await self.client.cancel_all_orders(symbol)
                    print("Resposta do cancelamento:", response)
                    await context.bot.send_message(
                        chat_id=context.job.chat_id,
                        text=f"\u26d4 Todas as ordens canceladas para {symbol}.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    await context.bot.send_message(
                        chat_id=context.job.chat_id,
                        text=f"Erro ao cancelar ordens em {symbol}: {e}",
                        parse_mode="Markdown"
                    )
    
    async def get_balance(self, asset: str = 'USDT') -> dict:
        """Busca o saldo da sua conta de Futuros, geralmente em USDT ou BUSD."""
        print(f"\n💰 Buscando saldo de margem em {asset.upper()}...")
        try:
            balance_data = await self.client.fetch_balance()
            # Em futuros, o saldo relevante é o da sua moeda de margem
            if asset.upper() in balance_data:
                return balance_data[asset.upper()]
            else:
                return {'error': f'Moeda de margem {asset.upper()} não encontrada no saldo.'}
        except ccxt_pro.ExchangeError as e:
            print(f"Erro ao buscar saldo: {e}")
            return {"error": str(e)}

    async def get_price(self, symbol: str) -> dict:
        """
        Busca o preço atual de um par de negociação (ex: 'BTC/USDT').
        """
        print(f"\n📈 Buscando preço para {symbol.upper()}...")
        try:
            # fetch_ticker busca os dados das últimas 24h, incluindo o último preço.
            ticker = await self.client.fetch_ticker(symbol.upper())
            return {
                "symbol": symbol.upper(),
                "price": ticker.get('last') # 'last' é o preço da última transação
            }
        except ccxt_pro.ExchangeError as e:
            print(f"Erro ao buscar preço para {symbol.upper()}: {e}")
            return {"error": str(e)}

    async def list_assets_by_price(self, quote_currency: str = 'USDT', top_n: int = 10) -> list:
        """
        Lista os 'top N' ativos por preço em relação a uma moeda base (ex: USDT).
        """
        print(f"\n📊 Buscando e ordenando os top {top_n} ativos por preço em {quote_currency.upper()}...")
        try:
            # fetch_tickers() busca os dados de todos os pares de uma vez.
            all_tickers = await self.client.fetch_tickers()
            
            # Filtra apenas os pares com a moeda base desejada e que tenham preço
            usdt_pairs = []
            for ticker in all_tickers.values():
                if ticker['symbol'].endswith(f'/{quote_currency.upper()}') and ticker.get('last') is not None:
                    usdt_pairs.append({
                        'symbol': ticker['symbol'],
                        'price': ticker['last']
                    })
            
            # Ordena a lista de pares pelo preço, do maior para o menor
            sorted_pairs = sorted(usdt_pairs, key=lambda x: x['price'], reverse=True)
            
            # Retorna apenas os 'top N' resultados
            return sorted_pairs[:top_n]

        except ccxt_pro.ExchangeError as e:
            print(f"Erro ao listar ativos por preço: {e}")
            return [{"error": str(e)}]
    
async def main():
    """
    Função principal assíncrona para demonstrar o uso do BinanceHandler.
    """
    handler = None
    try:
        # 1. Cria a instância da classe usando o método de fábrica assíncrono
        handler = await BinanceHandler.create()

        # # 2. Obter o balanço de um ativo
        # btc_balance = await handler.get_balance('BTC')
        # print(f"Detalhes do Saldo: {btc_balance}")

        # # 3. Obter o preço de um par
        # eth_price = await handler.get_price('ETH/USDT')
        # print(f"Detalhes do Preço: {eth_price}")

        # # 4. Listar os top 10 ativos por preço em USDT
        # top_assets = await handler.list_assets_by_price(quote_currency='USDT', top_n=10)
        # print("\n🏆 Top 10 Ativos por Preço em USDT:")
        # for asset in top_assets:
        #     print(f"   - {asset['symbol']}: ${asset['price']:,.2f}")

        print("\n--- TESTANDO obter_dados_candles ---")
        df = await handler.obter_dados_candles('BTC/USDT', timeframe='15m', limit=5)
        print("Resultado dos Candles (5 últimos):")
        print(df)

    except Exception as e:
        print(f"\n❌ Ocorreu um erro geral no script: {e}")
    finally:
        # 5. Essencial: Sempre fechar a conexão no final
        if handler:
            await handler.close_connection()
            print("✅ Conexão fechada e script finalizado.")

if __name__ == "__main__":
    print("Iniciando script de teste do BinanceHandler...")
    asyncio.run(main())