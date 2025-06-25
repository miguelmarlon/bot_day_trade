import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import json
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException
import os
from dotenv import load_dotenv
from praisonai_tools import BaseTool
from langchain.tools import tool
from typing import Any, Optional
from embedchain.models.data_type import DataType
from pydantic import Field
import re
import unicodedata
import pandas as pd
from utils.binance_client import BinanceHandler
import ccxt
import asyncio
import warnings
warnings.filterwarnings("ignore")

class CCXTGetBalance(BaseTool):
    name: str = "ExchangeGetBalance"
    description: str = "Lista o saldo de uma criptomoeda específica na sua conta da corretora."
    
    # O cliente é um atributo, mas não será inicializado aqui
    cliente: Any = Field(None)

    # --- CORREÇÃO 1: __init__ VOLTA A SER SÍNCRONO ---
    # Ele agora é muito simples e apenas recebe o cliente já pronto.
    def __init__(self, client: Any, **kwargs):
        super().__init__(**kwargs)
        self.cliente = client

    # --- CORREÇÃO 2: CRIAMOS UM MÉTODO DE CLASSE "FÁBRICA" ---
    @classmethod
    async def create(cls, **kwargs):
        """
        Método de fábrica assíncrono para criar e inicializar a ferramenta.
        """
        # 1. Faz a conexão assíncrona
        client = await BinanceHandler()
        # 2. Cria a instância da classe, passando o cliente já conectado
        return cls(client=client, **kwargs)

    # O resto do seu código já estava quase perfeito!
    async def get_balance(self, asset: str) -> dict:
        """Obtém o saldo de uma criptomoeda específica."""
        try:
            balance_data = await self.cliente.fetch_balance()
            asset_upper = asset.upper()
            if asset_upper in balance_data:
                return {"success": True, "balance": balance_data[asset_upper]}
            else:
                return {"success": True, "balance": {'asset': asset_upper, 'free': 0.0, 'used': 0.0, 'total': 0.0}}
        except Exception as e: # Use ccxt_pro.ExchangeError se possível
            return {"success": False, "error": str(e)}

    def add(self, *args: Any, **kwargs: Any) -> None:
        kwargs["data_type"] = DataType.TEXT
        super().add(*args, **kwargs)

    async def _run(self, cripto_name: str) -> str:
        """Executa a busca pelo saldo de uma criptomoeda."""
        try:
            content = await self.get_balance(cripto_name)
            
            # Pequeno detalhe: esta linha é um resquício e pode ser removida
            # if isinstance(content, str): 
            #     content = json.loads(content)
            
            if content["success"]:
                balance = content['balance']
                return (f"Saldo para {cripto_name.upper()}: \n"
                        f"  - Total: {balance['total']}\n"
                        f"  - Disponível (free): {balance['free']}\n"
                        f"  - Em uso (em ordens): {balance['used']}")
            else:
                return f"Erro ao buscar saldo para {cripto_name}: {content['error']}"
        except Exception as e:
            return f"Erro ao buscar saldo para {cripto_name}: {str(e)}"
        # finally:
        #     await self.cliente.close()

class BinanceGetPrice(BaseTool):
    name: str = "BinanceGetPrice"
    description: str = "Lista o preço de determinada cripto."
    api_key: str = Field(default=None)
    secret_key: str = Field(default=None)  
    client: Any = Field(default=None)  

    def __init__(self, cripto_name: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.secret_key = os.getenv("BINANCE_SECRET_KEY")
        if not self.api_key or not self.secret_key:
            raise ValueError("As chaves da API da Binance não foram fornecidas.")
        self.client = Client(self.api_key, self.secret_key)

        if cripto_name:
            content = self.get_price(cripto_name)
            if content["success"]:
                self.add(content)
                self.description = f"Preço da {cripto_name}"
            else:
                print(f"Erro ao buscar preço para {cripto_name}: {content['error']}") 

    def get_price(self, asset: str) -> dict:
        """Obtém o preço de uma criptomoeda específica."""
        try:
            price = self.client.get_symbol_ticker(symbol=asset)
            return json.dumps({"success": True, "price": price})
        except BinanceAPIException as e:
            return json.dumps({"success": False, "error": str(e)})

    def add(self, *args: Any, **kwargs: Any) -> None:
        kwargs["data_type"] = DataType.TEXT
        super().add(*args, **kwargs)

    def _run(self, cripto_name: str) -> str:
        """Executa a busca pelo preço de uma criptomoeda."""
        content = self.get_price(cripto_name)
        if isinstance(content, str): 
            content = json.loads(content)
        "saldo"
        if content["success"]:
            return f"Preço da {cripto_name}: {content['price']}"
        else:
            return f"Erro ao buscar preço para {cripto_name}: {content['error']}"

class BinanceGetTechnicalIndicators(BaseTool):
    name: str = "BinanceGetTechnicalIndicators"
    description: str = "Calcula os indicadores técnicos de determinada cripto."
    api_key: str = Field(default=None)
    secret_key: str = Field(default=None)  
    client: Any = Field(default=None)  

    def __init__(self, cripto_name: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.secret_key = os.getenv("BINANCE_SECRET_KEY")
        if not self.api_key or not self.secret_key:
            raise ValueError("As chaves da API da Binance não foram fornecidas.")
        self.client = Client(self.api_key, self.secret_key)

        if cripto_name:
            content = self.get_technical_indicators(cripto_name)
            if content["success"]:
                self.add(content)
                self.description = f"Indicadores técnicos para {cripto_name}"
            else:
                print(f"Erro ao buscar indicadores para {cripto_name}: {content['error']}")

    def get_historical_data(
        self, symbol: str, interval: str = "1d", limit: int = 500
    ) -> pd.DataFrame:
        """
        Obtém dados históricos de uma criptomoeda.
        :param symbol: Par de negociação (ex.: BTCUSDT).
        :param interval: Intervalo das velas (ex.: 1m, 1h, 1d).
        :param limit: Número máximo de velas retornadas.
        :return: DataFrame com os dados históricos.
        """
        
        try:
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
            columns = [
                "Open time",
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
                "Close time",
                "Quote asset volume",
                "Number of trades",
                "Taker buy base asset volume",
                "Taker buy quote asset volume",
                "Ignore",
            ]
            df = pd.DataFrame(klines, columns=columns)
            # Converte colunas numéricas para float
            df["Open"] = df["Open"].astype(float)
            df["High"] = df["High"].astype(float)
            df["Low"] = df["Low"].astype(float)
            df["Close"] = df["Close"].astype(float)
            df["Volume"] = df["Volume"].astype(float)
            
            return df
        except BinanceAPIException as e:
            print(f"Erro ao buscar dados históricos para {symbol}: {e}")
            return pd.DataFrame()

    def calculate_rsi(self, data: pd.DataFrame, window: int = 14) -> list:
        """Calcula o RSI."""
        delta = data["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.tolist()
    
    def calculate_macd(self, data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
        """Calcula o MACD."""
        ema_fast = data["Close"].ewm(span=fast, adjust=False).mean()
        ema_slow = data["Close"].ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return {
            "macd_line": macd_line.tolist(),
            "signal_line": signal_line.tolist(),
            "histogram": histogram.tolist(),
        }
    
    def calculate_adx(self, data: pd.DataFrame, window: int = 14) -> list:
        """Calcula o ADX."""
        high = data["High"]
        low = data["Low"]
        close = data["Close"]
        plus_dm = high.diff().clip(lower=0)
        minus_dm = low.diff().clip(upper=0)
        tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
        atr = tr.rolling(window=window).mean()
        plus_di = 100 * (plus_dm.rolling(window=window).sum() / atr)
        minus_di = 100 * (minus_dm.rolling(window=window).sum() / atr)
        dx = 100 * abs((plus_di - minus_di) / (plus_di + minus_di))
        adx = dx.rolling(window=window).mean()
        return adx.tolist()

    def calculate_sma(self, data: pd.DataFrame, window: int) -> list:
        """Calcula a SMA."""
        return data["Close"].rolling(window=window).mean().tolist()
    
    def calculate_ema(self, data: pd.DataFrame, window: int) -> list:
        """Calcula a EMA."""
        return data["Close"].ewm(span=window, adjust=False).mean().tolist()

    def calculate_bollinger_bands(
        self, data: pd.DataFrame, window: int = 20, num_std: int = 2
    ) -> dict:
        """
        Calcula as Bandas de Bollinger.
        :param data: DataFrame com os dados históricos.
        :param window: Janela para o cálculo das bandas.
        :param num_std: Número de desvios padrão.
        :return: Dicionário com as listas das bandas superior, média e inferior.
        """
        sma = data["Close"].rolling(window=window).mean()
        std = data["Close"].rolling(window=window).std()
        upper_band = sma + (std * num_std)
        lower_band = sma - (std * num_std)
        return {
            "upper_band": upper_band.tolist(),
            "middle_band": sma.tolist(),
            "lower_band": lower_band.tolist(),
        }

    def calculate_fibonacci_retracement(self, data: pd.DataFrame) -> dict:
        """Calcula os níveis de Fibonacci Retracement."""
        high = data["High"].max()
        low = data["Low"].min()
        diff = high - low
        levels = {
            "0%": round(high),
            "23.6%": round(high - 0.236 * diff),
            "38.2%": round(high - 0.382 * diff),
            "50%": round(high - 0.5 * diff),
            "61.8%": round(high - 0.618 * diff),
            "100%": round(low),
        }
        return levels
    
    def calculate_mfi(self, data: pd.DataFrame, window: int = 14) -> list:
        """Calcula o Índice de Fluxo de Dinheiro (MFI)."""
        typical_price = (data["High"] + data["Low"] + data["Close"]) / 3
        money_flow = typical_price * data["Volume"]
        positive_flow = money_flow.where(typical_price > typical_price.shift(), 0).rolling(window=window).sum()
        negative_flow = money_flow.where(typical_price < typical_price.shift(), 0).rolling(window=window).sum()
        mfi = 100 - (100 / (1 + (positive_flow / negative_flow)))
        return mfi.tolist()

    def calculate_stochastic(self, data: pd.DataFrame, k_period=14, d_period=3):
        """
        Calcula o Oscilador Estocástico (%K e %D).

        Parâmetros:
            df (DataFrame): deve conter as colunas 'high', 'low', 'close'
            k_period (int): período para cálculo de %K (default: 14)
            d_period (int): período da média móvel de %K para obter %D (default: 3)

        Retorna:
            DataFrame com colunas 'stochastic_k' e 'stochastic_d'
        """
         # Garantir que o período de cálculo seja válido
        if k_period < 1 or d_period < 1:
            raise ValueError("Os períodos k_period e d_period devem ser maiores que 0.")
        
        # Calculando o menor low e o maior high para o período K
        lowest_low = data['Low'].rolling(window=k_period).min()
        highest_high = data['High'].rolling(window=k_period).max()

        # Prevenindo divisão por zero ao calcular %K
        stochastic_k = 100 * ((data['Close'] - lowest_low) / (highest_high - lowest_low))

        # Tratamento para evitar divisão por zero gerando NaN
        stochastic_k = stochastic_k.fillna(0)

        # Calculando %D (média móvel de %K)
        stochastic_d = stochastic_k.rolling(window=d_period).mean()

        # Adicionando as colunas calculadas ao DataFrame
        data['stochastic_k'] = stochastic_k
        data['stochastic_d'] = stochastic_d
        
        return data[['stochastic_k', 'stochastic_d']]

    def calcular_pivot_points_em_coluna(self, data: pd.DataFrame):
        """
        Calcula os Pivot Points e salva em uma única coluna chamada 'pivot'.
        
        Parâmetros:
            df (DataFrame): deve conter as colunas 'high', 'low', 'close'

        Retorna:
            DataFrame com uma coluna 'pivot' contendo os valores calculados em formato de dicionário.
        """
        pivot = (data['High'] + data['Low'] + data['Close']) / 3
        data['pivot'] = pivot
        data['r1'] = (2 * pivot) - data['Low']
        data['s1'] = (2 * pivot) - data['High']
        data['r2'] = pivot + (data['High'] - data['Low'])
        data['s2'] = pivot - (data['High'] - data['Low'])
        data['r3'] = data['High'] + 2 * (pivot - data['Low'])
        data['s3'] = data['Low'] - 2 * (data['High'] - pivot)
        
        # Salvando todos os valores em uma coluna chamada 'pivot' como um dicionário
        data['pivot_points'] = data.apply(lambda row: {
            'pivot': row['pivot'],
            'r1': row['r1'],
            's1': row['s1'],
            'r2': row['r2'],
            's2': row['s2'],
            'r3': row['r3'],
            's3': row['s3']
        }, axis=1)
        return data
    
    def get_technical_indicators(self, asset: str, interval: str = "1d", limit: int = 70) -> dict:
        """Obtém o preço de uma criptomoeda específica."""
        valid_intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]
    
        if interval not in valid_intervals:
            print(f"Intervalo inválido. Escolha entre: {', '.join(valid_intervals)}")
            return {"success": False, "error": f"Intervalo inválido. Escolha entre: {', '.join(valid_intervals)}"}
        
        try:
            data = self.get_historical_data(asset, interval, limit)
            
            if data.empty:
                return {"success": False, "error": f"Dados históricos para {asset} não encontrados."}
            
            sma_50 = self.calculate_sma(data, window=50)
            sma_200 = self.calculate_sma(data, window=200)
            ema_20 = self.calculate_ema(data, window=20)
            ema_50 = self.calculate_ema(data, window=50)
            rsi = self.calculate_rsi(data)
            macd = self.calculate_macd(data)
            adx = self.calculate_adx(data)
            mfi = self.calculate_mfi(data)
            fibonacci = self.calculate_fibonacci_retracement(data)
            bollinger_bands = self.calculate_bollinger_bands(data)
            stochastic = self.calculate_stochastic(data)
            pivot_points = self.calcular_pivot_points_em_coluna(data)

            result = {
            "success": True,
            "data": {
                "historical_data": data.to_dict(orient="records"),
                "indicators": {
                    "sma_50": sma_50,
                    "sma_200": sma_200,
                    "ema_20": ema_20,
                    "ema_50": ema_50,
                    "rsi": rsi,
                    "macd": macd,
                    "adx": adx,
                    "mfi": mfi,
                    "fibonacci": fibonacci,
                    "bollinger_bands": bollinger_bands,
                    "fibonacci_retracement": fibonacci,
                    "stochastic": stochastic,
                    "pivot_points": pivot_points
                    },
                },
            }
            return result, data
        
        except BinanceAPIException as e:
            return json.dumps({"success": False, "error": str(e)})

    def _run(self, cripto_name: str, interval: str = "1d") -> str:
        """
        Executa a busca pelos indicadores técnicos de uma criptomoeda.
        :param cripto_name: Nome da criptomoeda (ex.: BTCUSDT).
        :param interval: Intervalo das velas (ex.: 1m, 1h, 1d).
        :return: String com os resultados ou mensagem de erro.
        """
        valid_intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]
        if interval not in valid_intervals:
            return f"Intervalo inválido. Escolha entre: {', '.join(valid_intervals)}"
        else:
            content, _ = self.get_technical_indicators(asset=cripto_name, interval=interval)
            if not content["success"]:
                return f"Erro: {content['error']}"
            
            indicators = content["data"]["indicators"]
            response = f"Indicadores técnicos para {cripto_name}:\n"
            for key, value in indicators.items():
                if isinstance(value, dict):
                    response += f"\n{key}:\n"
                    for subkey, subvalue in value.items():
                        if isinstance(subvalue, list):
                            response += f"  {subkey}: {subvalue[-1] if subvalue else 'N/A'}\n"
                        else:
                            response += f"  {subkey}: {subvalue if subvalue is not None else 'N/A'}\n"
                else:
                    if isinstance(value, pd.DataFrame):
                        response += f"{key}: {value.iloc[-1].to_dict() if not value.empty else 'N/A'}\n"
                    else:
                        response += f"{key}: {value if value is not None else 'N/A'}\n"
            print(response)
            return response
    
class BinanceListCryptosByPrice(BaseTool):
    name: str = "BinanceListCryptosByPrice"
    description: str = "Lista todas as criptomoedas com par USDT abaixo de um valor específico."
    api_key: str = Field(default=None)
    secret_key: str = Field(default=None)
    client: Any = Field(default=None)
    max_price: float = Field(default=2.0)

    def __init__(self, max_price: float = 2.0, **kwargs):
        super().__init__(**kwargs)

        self.api_key = os.getenv("BINANCE_API_KEY")
        self.secret_key = os.getenv("BINANCE_SECRET_KEY")
        if not self.api_key or not self.secret_key:
            raise ValueError("As chaves da API da Binance não foram fornecidas.")
        self.client = Client(self.api_key, self.secret_key)

        self.max_price = max_price
        content = self.get_cryptos_by_price()
        self.add(content)

    def get_cryptos_by_price(self) -> dict:
        """Retorna uma lista de criptos negociadas em USDT com preço abaixo do limite especificado."""
        try:
            # 1. Obtem todos os pares de negociação ativos
            exchange_info = self.client.get_exchange_info()
            symbols_ativos = [s['symbol'] for s in exchange_info['symbols'] 
                              if s['status'] == 'TRADING' and s['symbol'].endswith('USDT')]
            # 2. Obtem todos os preços de uma só vez
            todos_precos = self.client.get_all_tickers()
            filtered = []

            print(f"Buscando criptomoedas com par USDT abaixo de ${self.max_price}...")
            for item in todos_precos:
                symbol = item['symbol']
                if symbol in symbols_ativos:
                    try:
                        price = float(item['price'])
                        if price <= self.max_price:
                            print(f"Encontrado: {symbol} - ${price}")
                            filtered.append({"symbol": symbol, "price": price})
                    except ValueError:
                        continue
            return pd.DataFrame(filtered)
            # for ticker in tickers:
            #     print('Buscando:', ticker)
            #     symbol = ticker
            #     if symbol.endswith("USDT"):
            #         try:
            #             tool = BinanceGetPrice()
            #             preco = tool.get_price(symbol)
            #             price_dict = json.loads(preco)
            #             price = float(price_dict['price']['price'])
            #             if price <= self.max_price:
            #                 filtered.append({"symbol": symbol, "price": price})
                
            #         except ValueError:
            #             continue
            #     print(f'Busca {ticker} concluída.')

            # return pd.DataFrame(filtered)
        except BinanceAPIException as e:
            return {"success": False, "error": str(e)}

    def add(self, content: dict) -> None:
        """Adiciona os dados ao sistema."""
        if isinstance(content, pd.DataFrame):
            df = content
        elif isinstance(content, dict) and content.get("success"):
            df = pd.DataFrame(content["cryptos"])
        else:
            print("Erro: dados inválidos ou vazios.")
            return

        if df.empty:
            print(f"Nenhuma cripto encontrada abaixo de ${self.max_price}")
        
    def _run(self, max_price: Optional[float] = None) -> str:
        """Executa a listagem das criptomoedas abaixo do valor máximo especificado."""
        if max_price is not None:
            self.max_price = max_price
        df = self.get_cryptos_by_price()
        return df

def parse_llm_response(texto):
    """
    Tenta extrair a decisão de trading da LLM com uma abordagem principal.
    Se falhar, usa uma estratégia alternativa.
    """
    # Estratégia principal: buscar 'Decisão: ...'
    padrao_principal = r"decis[aã]o:\s*(COMPRA|VENDA|MANTER|MANTENER)"
    match_principal = re.findall(padrao_principal, texto, flags=re.IGNORECASE)
    
    if match_principal:
        return match_principal[-1].upper()

    # Estratégia alternativa: procurar palavras-chave isoladas no fim do texto
    padrao_alternativo = r"\b(COMPRA|VENDA|MANTER|MANTENER)\b"
    match_alternativa = re.findall(padrao_alternativo, texto[-200:], flags=re.IGNORECASE)  # Olha só o final do texto

    if match_alternativa:
        return match_alternativa[-1].upper()

    return "N/A"

# async def main():
#     tool = await CCXTGetBalance.create()
    
#     result = await tool._run("BTC") 
#     print(result) 
    
# if __name__ == '__main__':
#     asyncio.run(main())

############################################################################################
## tentando conectar o mcp com praisonai
# agent_yaml = """
# framework: "crewai"
# topic: "Análise Automatizada de Criptomoedas e Recomendação de Investimento"
# roles:
#   crypto_analyst:
#     role: "O Melhor Analista de Criptomoedas"
#     backstory: |
#       Um analista de criptomoedas altamente qualificado com expertise em tecnologia blockchain, tendências de mercado
#       e análise técnica. Reconhecido por fornecer insights precisos para orientar decisões de investimento.
#     goal: "Fornecer uma análise detalhada do desempenho e posição de mercado de uma criptomoeda."
#     tasks:
#       technical_analysis:
#         description: |
#           Realizar uma análise técnica detalhada da criptomoeda selecionada (ex.: BTCUSDT).
#           Analisar indicadores-chave como RSI, MACD, SMA, EMA, Bandas de Bollinger e Nuvem de Ichimoku.
#           Avaliar movimentos de preço históricos, volumes de negociação e volatilidade.
#         expected_output: |
#           Um relatório abrangente detalhando os indicadores técnicos, tendências de preço e possíveis pontos de entrada/saída.
#           Incluir visualizações, se possível. Usar os dados mais recentes disponíveis da Binance.
#     tools:
#       - "BinanceGetPrice"
#       - "BinanceGetTechnicalIndicators"
      
# dependencies: []
# """

# class PraisonAIOllama(PraisonAI):
#     def __init__(self, *args, ollama=None, **kwargs):
#         super().__init__(*args, **kwargs)
#         if ollama:
#             self.config_list = [
#                 {
#                     'model': ollama,
#                     'base_url': "http://localhost:11434/v1",
#                     'api_key': None
#                 }
#             ]

# # Create a PraisonAI instance with the agent_yaml content
# praisonai = PraisonAIOllama(
#     agent_yaml=agent_yaml,
#     tools=[BinanceGetPrice, BinanceGetTechnicalIndicators],
#     ollama="llama3.1:8b"
# )
# praisonai.run()

##############################################################################################
#testes das tools
###############################################################################################
# tool = BinanceListCryptosByPrice(max_price=0.3)
# result = tool._run()
# print(result)

# tool = BinanceGetBalance()
# result = tool._run("XRP")
# print(result)

# tool = BinanceGetPrice()
# result2 = tool._run("BTCUSDT")
# print(result2)

# tool = BinanceGetTechnicalIndicators()
# result_default, data = tool._run("BTCUSDT", interval="5m")
# print(data)

# result_custom = tool._run("EOSUSDT", interval="15m")
# print(result_custom)


#############################################################################################
# class ExtendedServer(Server):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.tools = {}  # Dicionário para armazenar as ferramentas registradas

#     def register_tool(self, name: str, func):
#         """Registra uma ferramenta com um nome específico."""
#         self.tools[name] = func
#         logger.debug(f"Ferramenta registrada: {name}")

#     async def call_tool(self, tool_name: str, arguments: dict):
#         """Chama uma ferramenta registrada pelo nome."""
#         if tool_name not in self.tools:
#             return {"success": False, "error": f"Ferramenta '{tool_name}' não encontrada."}
#         try:
#             result = await self.tools[tool_name](**arguments)
#             return {"success": True, "result": result}
#         except Exception as e:
#             return {"success": False, "error": str(e)}

#     async def serve_stdio(self):
#         """Lê entradas do console e processa chamadas de ferramentas."""
#         logger.info("Servidor iniciado. Aguardando entradas...")
#         loop = asyncio.get_event_loop()
#         while True:
#             try:
#                 # Ler entrada do console
#                 line = await loop.run_in_executor(None, sys.stdin.readline)
#                 if not line:
#                     break

#                 # Decodificar a entrada JSON
#                 request = json.loads(line.strip())
#                 tool_name = request.get("tool")
#                 arguments = request.get("arguments", {})

#                 # Chamar a ferramenta registrada
#                 response = await self.call_tool(tool_name, arguments)

#                 # Enviar a resposta de volta ao cliente
#                 print(json.dumps(response), flush=True)
#             except Exception as e:
#                 logger.error(f"Erro ao processar solicitação: {e}")
#                 print(json.dumps({"success": False, "error": str(e)}), flush=True)

# # Inicializar cliente Binance
# client = Client(api_key, secret_key)

# # Criar o servidor MCP
# server = ExtendedServer(name="Binance_MCP_Server")

# # Função para obter saldo
# async def get_balance(asset):
#     try:
#         balance = client.get_asset_balance(asset=asset)
#         return json.dumps({"success": True, "balance": balance})
#     except BinanceAPIException as e:
#         return json.dumps({"success": False, "error": str(e)})

# # Função para obter preço atual de um par de trading
# async def get_price(symbol):
#     try:
#         ticker = client.get_symbol_ticker(symbol=symbol)
#         return json.dumps({"success": True, "price": ticker})
#     except BinanceAPIException as e:
#         return json.dumps({"success": False, "error": str(e)})

# # Função para criar uma ordem de compra
# async def place_order(symbol, quantity, order_type="MARKET"):
#     try:
#         order = client.order_market_buy(symbol=symbol, quantity=quantity)
#         return json.dumps({"success": True, "order": order})
#     except BinanceAPIException as e:
#         return json.dumps({"success": False, "error": str(e)})

# # Função para obter dados históricos e calcular indicadores técnicos
# async def get_technical_indicators(symbol, interval="1h", limit=100):
#     try:
#         klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
#         df = pd.DataFrame(klines, columns=["time", "open", "high", "low", "close", "volume", "close_time", "quote_asset_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"])
#         df["close"] = df["close"].astype(float)

#         # Cálculo dos indicadores técnicos
#         df["rsi"] = RSIIndicator(df["close"], window=14).rsi()
#         df["macd"] = MACD(df["close"], window_slow=26, window_fast=12, window_sign=9).macd()
#         df["adx"] = ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()
#         df["bollinger_high"] = BollingerBands(df["close"], window=20, window_dev=2).bollinger_hband()
#         df["bollinger_low"] = BollingerBands(df["close"], window=20, window_dev=2).bollinger_lband()
#         df["sma_50"] = SMAIndicator(df["close"], window=50).sma_indicator()
#         df["sma_200"] = SMAIndicator(df["close"], window=200).sma_indicator()
#         df["ema_20"] = EMAIndicator(df["close"], window=20).ema_indicator()
#         df["ema_50"] = EMAIndicator(df["close"], window=50).ema_indicator()

#         latest_data = df.iloc[-1][["rsi", "macd", "adx", "bollinger_high", "bollinger_low", "sma_50", "sma_200", "ema_20", "ema_50"]].to_dict()
#         return json.dumps({"success": True, "indicators": latest_data})
#     except Exception as e:
#         return json.dumps({"success": False, "error": str(e)})

# # Registrar as ferramentas no servidor MCP

# server.register_tool("get_balance", get_balance)
# server.register_tool("get_price", get_price)
# server.register_tool("place_order", place_order)
# server.register_tool("get_technical_indicators", get_technical_indicators)

# # Iniciar o servidor
# if __name__ == "__main__":
#     print("Iniciando servidor MCP para Binance...")
#     asyncio.run(server.serve_stdio())