import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import ccxt
import ccxt.pro as ccxt_pro
# FORMA ANTIGA E INCORRETA
from ccxt import ExchangeError, AuthenticationError, NetworkError, RequestTimeout
import pandas as pd
import asyncio
import time
from config.config import BINANCE_API_KEY, BINANCE_SECRET_KEY
import logging
import warnings
# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Ignorar avisos de depreciação do Pandas
warnings.filterwarnings("ignore", category=DeprecationWarning)


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
        self.markets = None

    @classmethod
    async def create(cls):
        """
        Método de fábrica assíncrono para criar e retornar uma instância de BinanceHandler.
        """

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
        
        await self.client.close()
    
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

        from scripts.gerenciamento_risco_assin import GerenciamentoRiscoAsync

        gerenciador_risco = GerenciamentoRiscoAsync(binance_handler=self)
        async with gerenciador_risco as gr:
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

        from scripts.gerenciamento_risco_assin import GerenciamentoRiscoAsync

        gerenciador_risco = GerenciamentoRiscoAsync(binance_handler=self)
        async with gerenciador_risco as gr:
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
                
                msg = (
                    f"✅**Ordem de Compra (Long) Enviada!**\n"
                    f"🔹**Par de Mercado:** {symbol}\n"
                    f"🔹**Tipo de Ordem:** LIMIT\n"
                    f"💲**Preço de Entrada:** {bid}\n"
                    f"📊**Quantidade:** {posicao_max} {symbol.split('/')[0]}"
                )
                print(msg)
            except AuthenticationError as e:
                msg = f"❌ ERRO DE AUTENTICAÇÃO: Verifique suas chaves de API e permissões. Detalhes: {e}"
                print(msg)
            except NetworkError as e:
                msg = f"⚠️ ERRO DE REDE: Não foi possível conectar à Binance. Tentando de novo no próximo ciclo. Detalhes: {e}"
                print(msg)
            except RequestTimeout as e:
                msg = f"⏳ ERRO DE TIMEOUT: A resposta da Binance demorou muito. Tentando novamente no próximo ciclo. Detalhes: {e}#"
                print(msg)
            except ExchangeError as e:
                msg = f"❌ Erro da Corretora em {symbol}: {e}"
                print(msg)
            except Exception as e:
                msg = f"❌ Erro ao abrir long em {symbol}: {e}"
                print(msg)

            await context.bot.send_message(chat_id=context.job.chat_id, text=msg, parse_mode="Markdown")

    async def cancelar_todas_as_ordens(self, symbol, context):
        """Cancela todas as ordens abertas para um símbolo."""

        from scripts.gerenciamento_risco_assin import GerenciamentoRiscoAsync

        gerenciador_risco = GerenciamentoRiscoAsync(binance_handler=self)
        async with gerenciador_risco as gr:
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
        except AuthenticationError as e:
            msg = f"❌ ERRO DE AUTENTICAÇÃO: Verifique suas chaves de API e permissões. Detalhes: {e}"
            print(msg)
        except NetworkError as e:
            msg = f"⚠️ ERRO DE REDE: Não foi possível conectar à Binance. Tentando de novo no próximo ciclo. Detalhes: {e}"
            print(msg)
        except RequestTimeout as e:
            msg = f"⏳ ERRO DE TIMEOUT: A resposta da Binance demorou muito. Tentando novamente no próximo ciclo. Detalhes: {e}#"
            print(msg)
        except ExchangeError as e:
            msg = f"❌ Erro da Corretora: {e}"
            print(msg)
        except Exception as e:
            msg = f"❌ Erro na função get_balance: {e}"
            print(msg)

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
        except AuthenticationError as e:
            msg = f"❌ ERRO DE AUTENTICAÇÃO: Verifique suas chaves de API e permissões. Detalhes: {e}"
            print(msg)
        except NetworkError as e:
            msg = f"⚠️ ERRO DE REDE: Não foi possível conectar à Binance. Tentando de novo no próximo ciclo. Detalhes: {e}"
            print(msg)
        except RequestTimeout as e:
            msg = f"⏳ ERRO DE TIMEOUT: A resposta da Binance demorou muito. Tentando novamente no próximo ciclo. Detalhes: {e}#"
            print(msg)
        except ExchangeError as e:
            print(f"Erro ao buscar preço para {symbol.upper()}: {e}")
            return {"error": str(e)}
        except Exception as e:
            msg = f"❌ Erro ao abrir long em {symbol}: {e}"
            print(msg)
        
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

        except AuthenticationError as e:
            msg = f"❌ ERRO DE AUTENTICAÇÃO: Verifique suas chaves de API e permissões. Detalhes: {e}"
            print(msg)
        except NetworkError as e:
            msg = f"⚠️ ERRO DE REDE: Não foi possível conectar à Binance. Tentando de novo no próximo ciclo. Detalhes: {e}"
            print(msg)
        except RequestTimeout as e:
            msg = f"⏳ ERRO DE TIMEOUT: A resposta da Binance demorou muito. Tentando novamente no próximo ciclo. Detalhes: {e}#"
            print(msg)
        except ExchangeError as e:
            print(f"Erro ao buscar preço para:: {e}")
            return {"error": str(e)}
        except Exception as e:
            msg = f"❌ Erro na função list_assets_by_price: {e}"
            print(msg)

    async def get_volume_report(self, quote_currency='USDT', limit=100):
        """
        Busca e retorna as moedas com o maior volume de negociação para uma
        determinada moeda de cotação nas últimas 24 horas.

        :param quote_currency: A moeda de cotação para filtrar (ex: 'USDT', 'BUSD').
        :param limit: O número de moedas do topo do ranking a serem retornadas.
        :return: Um DataFrame do Pandas com os resultados ordenados, ou None se ocorrer um erro.
        """
        try:
            # Usa a conexão existente do cliente da classe
            all_tickers = await self.client.fetch_tickers()
            
            # print(all_tickers)
            volume_data = []
            for symbol, ticker in all_tickers.items():
                # Filtra pela moeda de cotação desejada
                if symbol.endswith(f':{quote_currency}') and ticker.get('quoteVolume') is not None:
                    volume_data.append({
                        'symbol': symbol.split(':')[0],
                        'quote_volume': ticker['quoteVolume'],
                        'price_change_percent': ticker.get('percentage')
                    })
            
            # Ordena a lista pelo volume em ordem decrescente
            volume_data.sort(key=lambda x: x['quote_volume'], reverse=True)
            
            df = pd.DataFrame(volume_data)
            # print(df)
            if self.markets is None:
                print("Carregando dados de todos os mercados (chamada única de API)...")
                self.markets = await self.client.load_markets()

            df['status'] = df['symbol'].apply(lambda x: self.markets[x]['active'] if x in self.markets else 'Unknown')

            df = df[df['status'] == True]
            df['quote_volume'] = df['quote_volume'].apply(lambda x: f"${x:,.2f}")
            df['price_change_percent'] = df['price_change_percent'].apply(lambda x: f"{x:.2f}%" if x is not None else "N/A")
            df.index = df.index + 1

            return df.head(limit)

        except AuthenticationError as e:
            msg = f"❌ ERRO DE AUTENTICAÇÃO: Verifique suas chaves de API e permissões. Detalhes: {e}"
            print(msg)
        except NetworkError as e:
            msg = f"⚠️ ERRO DE REDE: Não foi possível conectar à Binance. Tentando de novo no próximo ciclo. Detalhes: {e}"
            print(msg)
        except RequestTimeout as e:
            msg = f"⏳ ERRO DE TIMEOUT: A resposta da Binance demorou muito. Tentando novamente no próximo ciclo. Detalhes: {e}#"
            print(msg)
        except ExchangeError as e:
            print(f"Erro ao buscar preço para:: {e}")
            return {"error": str(e)}
        except Exception as e:
            msg = f"❌ Erro na função get_volume_report: {e}"
            print(msg)
        finally:
            await self.close_connection()

async def main():
    """
    Função principal assíncrona para demonstrar o uso do BinanceHandler.
    """
    handler = None
    try:
        handler = await BinanceHandler.create()
        
        print("\nBuscando as 10 moedas com maior volume em USDT...")
        
        # 2. Chama o novo método da classe
        top_10_usdt = await handler.get_volume_report(quote_currency='USDT', limit=50)
        print(top_10_usdt)
        # 3. Processa o resultado retornado pelo método
        
        print("\n" + "="*50 + "\n")

    except Exception as e:
        print(f"Ocorreu um erro no programa principal: {e}")
    finally:
        # 4. Garante que a conexão seja fechada
        if handler:
            await handler.close_connection()
            print("\nConexão com a Binance fechada com sucesso.")

#         # 1. Cria a instância da classe usando o método de fábrica assíncrono
#         handler = await BinanceHandler.create()

#         # # 2. Obter o balanço de um ativo
#         # btc_balance = await handler.get_balance('BTC')
#         # print(f"Detalhes do Saldo: {btc_balance}")

#         # # 3. Obter o preço de um par
#         # eth_price = await handler.get_price('ETH/USDT')
#         # print(f"Detalhes do Preço: {eth_price}")

#         # # 4. Listar os top 10 ativos por preço em USDT
#         # top_assets = await handler.list_assets_by_price(quote_currency='USDT', top_n=10)
#         # print("\n🏆 Top 10 Ativos por Preço em USDT:")
#         # for asset in top_assets:
#         #     print(f"   - {asset['symbol']}: ${asset['price']:,.2f}")

#         print("\n--- TESTANDO obter_dados_candles ---")
#         df = await handler.obter_dados_candles('BTC/USDT', timeframe='15m', limit=5)
#         print("Resultado dos Candles (5 últimos):")
#         print(df)

#     except Exception as e:
#         print(f"\n❌ Ocorreu um erro geral no script: {e}")
#     finally:
#         # 5. Essencial: Sempre fechar a conexão no final
#         if handler:
#             await handler.close_connection()
#             print("✅ Conexão fechada e script finalizado.")

if __name__ == "__main__":
    print("Iniciando script de teste do BinanceHandler...")
    asyncio.run(main())