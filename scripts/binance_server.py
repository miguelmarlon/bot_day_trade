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
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

class BinanceGetBalance(BaseTool):
    name: str = "BinanceGetBalance"
    description: str = "Lista o saldo de determinada cripto."
    api_key: str = Field(default=None)  # Campo inicializável
    secret_key: str = Field(default=None)  # Campo inicializável
    client: Any = Field(default=None)  # Campo inicializável

    def __init__(self, cripto_name: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.secret_key = os.getenv("BINANCE_SECRET_KEY")
        if not self.api_key or not self.secret_key:
            raise ValueError("As chaves da API da Binance não foram fornecidas.")
        self.client = Client(self.api_key, self.secret_key)

        if cripto_name:
            content = self.get_balance(cripto_name)
            if content["success"]:
                self.add(content)
                self.description = f"Saldo disponível para {cripto_name}"
            else:
                print(f"Erro ao buscar saldo para {cripto_name}: {content['error']}")   
    
    def get_balance(self, asset: str) -> dict:
        """Obtém o saldo de uma criptomoeda específica."""
        try:
            balance = self.client.get_asset_balance(asset=asset)
            return json.dumps({"success": True, "balance": balance})
        except BinanceAPIException as e:
            return json.dumps({"success": False, "error": str(e)})

    def add(self, *args: Any, **kwargs: Any) -> None:
        kwargs["data_type"] = DataType.TEXT
        super().add(*args, **kwargs)

    def _run(self, cripto_name: str) -> str:
        """Executa a busca pelo saldo de uma criptomoeda."""
        content = self.get_balance(cripto_name)
        if isinstance(content, str): 
            content = json.loads(content)
        
        if content["success"]:
            return f"Saldo disponível para {cripto_name}: {content['balance']}"
        else:
            return f"Erro ao buscar saldo para {cripto_name}: {content['error']}"

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

    def get_technical_indicators(self, asset: str, interval: str = "1d", limit: int = 500) -> dict:
        """Obtém o preço de uma criptomoeda específica."""
        valid_intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]
    
        if interval not in valid_intervals:
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
        content, data = self.get_technical_indicators(asset=cripto_name, interval=interval)
        if isinstance(content, str): 
            content = json.loads(content)

        if content["success"]:
            indicators = content["data"]["indicators"]
            return (
                f"Indicadores técnicos para {cripto_name} ({interval}):\n"
                f"- SMA_50: {indicators['sma_50'][-1]:.2f}\n"
                f"- SMA_200: {indicators['sma_200'][-1]:.2f}\n"
                f"- EMA_20: {indicators['ema_20'][-1]:.2f}\n"
                f"- EMA_50: {indicators['ema_50'][-1]:.2f}\n"
                f"- RSI: {indicators['rsi'][-1]:.2f}\n"
                f"- MACD: {indicators['macd']['histogram'][-1]:.2f}\n"
                f"- ADX: {indicators['adx'][-1]:.2f}\n"
                f"- MFI: {indicators['mfi'][-1]:.2f}\n"
                f"- Fibonacci Retracement: {indicators['fibonacci']}"
            ), data
        else:
            return f"Erro ao buscar indicadores para {cripto_name}: {content['error']}"

def parse_llm_response(response):
    decision = re.search(r"Decisão:\s*(.+)", response)
    if decision:
        return decision.group(1).strip()
    return None



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