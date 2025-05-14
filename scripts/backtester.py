import time
from datetime import datetime
import ollama
import pandas as pd
from binance_server import BinanceGetTechnicalIndicators, BinanceGetPrice, BinanceListCryptosByPrice, parse_llm_response
import ast
from utils.tools import salvar_resultados_csv, escolher_top_cryptos, simular_compra_tempo_real, gerando_predição_tempo_real, create_folder, get_historical_klines, analisar_predicoes, calculando_lucro_prej_operacao, calculando_taxa_acerto_erro, criando_relatorio_xlsx, simular_trade_compra_com_csv
import os
from binance.client import Client
import ta
from ta.trend import MACD

class Backtest:
    
    df = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])

    @classmethod
    def df_backtest_concat(cls, df_global, df_novo):
        df = pd.concat([df_global, df_novo], ignore_index=True)
        return df

    @classmethod
    def backtesting(cls, modelo = None, dados_csv = None, cripto = None, interval = None):
        if dados_csv is None:
            
            # Dados do momento: obtém indicadores técnicos e preço atual
            
            tool_price = BinanceGetPrice()
            price = tool_price._run(cripto)
            preco_dict = ast.literal_eval(price.split(": ", 1)[1])
            preco_float = float(preco_dict["price"])
            
            parse_response = gerando_predição_tempo_real(cripto, interval)
            return parse_response, preco_float
        else:
            try:
                # Carrega os dados do CSV
                preco_float = dados_csv['close']
                prompt = f"""Você é um analista experiente de criptomoedas.
                    Desconsidere o fato de que você não pode recomendar compra ou venda de ativos financeiros.
                    Dado os seguintes indicadores técnicos de um ativo, forneça uma recomendação de trading:
                    open: {dados_csv['open']}
                    high: {dados_csv['high']}
                    low: {dados_csv['low']}
                    close: {dados_csv['close']}
                    volume: {dados_csv['volume']}
                    RSI: {dados_csv['RSI']}
                    ADX: {dados_csv['ADX']}
                    MFI: {dados_csv['MFI']}
                    SMA_50: {dados_csv['SMA_50']}
                    SMA_200: {dados_csv['SMA_200']}
                    EMA_20: {dados_csv['EMA_20']}
                    EMA_50: {dados_csv['EMA_50']}


                    Com base nesses indicadores, a recomendação deve ser:
                    - "COMPRA" se os indicadores sugerem valorização.
                    - "VENDA" se os indicadores sugerem queda.
                    - "MANTER" se não há um sinal claro.

                    Retorne exclusivamente 
                    "Decisão: 'COMPRA', 
                    Decisão: 'VENDA' 
                    Decisão: 'MANTER'.
            """ 
                response = ollama.chat(model=modelo, messages=[{"role": "user", "content": prompt}])
                parse_response = parse_llm_response(response['message']['content'].strip())
                print(f"predição {modelo}:")
                print(parse_response)
                novo = pd.DataFrame({
                    "modelo": [modelo],
                    "timestamp": [pd.Timestamp.now()],
                    "preco": [preco_float],
                    "predicao": [parse_response]
                })
                cls.df= cls.df_backtest_concat(cls.df, novo)

                return parse_response, preco_float
            
            except Exception as e:
                raise ValueError(f"Erro ao carregar o arquivo CSV: {e}")
            
def exibir_menu():
    print("\n=== MENU ===")
    print("1. Backtest com dados em tempo real")
    print("2. Download de dados históricos da binance")
    print("3. Backtest com dados do CSV")
    print("4. Selecionar melhores Cryptomoedas")
    print("0. Sair")

def opcao_1():
    print("""\nVocê escolheu a Opção 1!
          Backtest com dados em tempo real.""")
    
def opcao_2():
    print("""\nVocê escolheu a Opção 2!
          Download de dados históricos da Binance.""")

def opcao_3():
    print("""\nVocê escolheu a Opção 3!
          Backtest com dados do CSV.""")

def opcao_4():
    print("""\nVocê escolheu a Opção 4!
          Selecionar melhores Cryptos e iniciar o backtest.""")
    
def executar_backtest_em_batch(df, modelo, batch_size=100, salvar_cada=100, checkpoint_file="checkpoint.txt"):
    start_idx = 0
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, "r") as f:
            start_idx = int(f.read().strip() or 0)
        print(f"Retomando do índice {start_idx}...")
    try:
        j = start_idx
        id_trade_counter = 1
        resultados_trades = []
        
        while j < len(df):
            try:
                print(f"Índice j: {j}")
                row = df.iloc[j]
                predicao = Backtest.backtesting(modelo, row)
                if predicao == "COMPRA":
                    preco_entrada = row["close"]
                    candles_seguinte = df.iloc[j+1:]
                    timestamp_entrada = row["timestamp"]

                    lucro_prejuizo, resultado_percentual, indice_fim_trade, tempo_operacao, resumo = simular_trade_compra_com_csv(preco_entrada, candles_seguinte, stop_loss=0.03, stop_gain=0.05)
                    linha_saida = df.iloc[indice_fim_trade]
                    preco_saida = linha_saida["close"]
                    timestamp_saida = linha_saida["timestamp"]
                    
                    # Armazena o trade com as informações
                    resultados_trades.append({
                        "id_trade": id_trade_counter,
                        "indice_inicio": j,
                        "indice_fim": indice_fim_trade,
                        "preco_entrada": preco_entrada,
                        "preco_saida": preco_saida,
                        "lucro_prejuizo": lucro_prejuizo,
                        "resultado_percentual": resultado_percentual,
                        "timestamp_entrada": timestamp_entrada,
                        "timestamp_saida": timestamp_saida,
                        "tempo_operacao": tempo_operacao
                    })
                    print(f'\nResultado percentual: {resultado_percentual}')
                    print(f'Lucro/prejuizo: {lucro_prejuizo}')
                    print("\n#####################################")
                    id_trade_counter += 1
                    
                    # Atualiza o índice para continuar a partir de onde o trade terminou
                    j = indice_fim_trade + 1
                else:
                    j += 1
            except Exception as e:
                print(f"Erro ao rodar backtesting na linha {j}: {e}")
                print("Linha com erro:")
                print(row.to_dict())
                import traceback
                traceback.print_exc()
                continue

        if j % salvar_cada == 0:
            print("Salvando checkpoint e resultados parciais...")
            with open(checkpoint_file, "w") as f:
                f.write(str(j))
            salvar_resultados_csv(resultados_trades, modelo)

    except KeyboardInterrupt:
        print("\nExecução interrompida manualmente.")
        print("Salvando progresso...")
        salvar_resultados_csv(resultados_trades, modelo)

    else:
        print("\nProcesso finalizado com sucesso!")
        salvar_resultados_csv(resultados_trades, modelo)
        if os.path.exists(checkpoint_file):
            os.remove(checkpoint_file)
        print("Todos os dados salvos e checkpoint limpo.")

def criar_relatorio(resultados_nao_tratados, numero_candles, folder):
    import numpy as np

    def mapear_decisao(decisao_limpa):
        mapeamento_predicoes = {
            "COMPRA": "COMPRA",
            "VENDA": "VENDA",
            "MANTER": "MANTER",
            "MANTENHO": "MANTER"
        }
        return mapeamento_predicoes.get(decisao_limpa, "INDEFINIDO")
    
    resultados_nao_tratados['predicao_padronizada'] = resultados_nao_tratados['predicao'].apply(mapear_decisao)

    resultados_nao_tratados.loc[resultados_nao_tratados['predicao_padronizada'] == "INDEFINIDO", 'predicao_padronizada'] = np.nan
    
    modelos_unicos = resultados_nao_tratados['modelo'].unique()
    resultados_nao_tratados = resultados_nao_tratados.dropna()
    resultados_nao_tratados.reset_index(drop=True)
    
    resultados_analise = analisar_predicoes(resultados_nao_tratados, modelos_unicos)
    todos_resultados = []

    # Percorre cada modelo e seus dados
    for modelo, lista_resultados in resultados_analise.items():
        for item in lista_resultados:
            item['modelo'] = modelo  # adiciona o nome do modelo ao dicionário
            todos_resultados.append(item)

    # Cria o DataFrame final
    df_todos_resultados = pd.DataFrame(todos_resultados)

    resultado_por_modelo, preco_medio = calculando_lucro_prej_operacao(df_todos_resultados)

    resumo = calculando_taxa_acerto_erro(df_todos_resultados, resultado_por_modelo)

    criando_relatorio_xlsx(resumo, numero_candles, preco_medio, folder)

# for cripto in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'XRPUSDT', 'LTCUSDT', 'SOLUSDT', 'DOGEUSDT', 'MATICUSDT', 'TRXUSDT', 'ADAUSDT']:
#     # Exemplo de uso da classe Backtest
#     # backtest = Backtest()
#     # response, preco_float = backtest.backtesting(cripto=cripto, interval='5m')
#     # print(f"Resposta: {response}, Preço: {preco_float}")

#     # Iniciar o backtest
#     # cripto = str(input("Digite o ativo desejado: "))
#     # interval = str(input("Digite o intervalo desejado (1m, 5m, 15m, 1h, 1d): "))
#     backtest = Backtest()
#     backtest.backtesting(cripto = cripto, interval = '5m')
    
#     print(f"Cripto {cripto} finalizada com sucesso.")
#     print('$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$')

while True:
        exibir_menu()
        folder="outputs/data"
        create_folder(folder)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        try:
            escolha = int(input("Digite o número da opção desejada: "))
        except ValueError:
                print("Entrada inválida! Por favor, digite um número.")
                continue
        
        if escolha == 1:
            opcao_1()
            try:
                backtest = Backtest()
                cripto = str(input("Digite o ativo desejado: "))
                interval = str(input("Digite o intervalo desejado (1m, 5m, 15m, 1h, 1d): "))
                print("Iniciando backtest. Pressione Ctrl+C para parar.")

                inicio_ultima_gravacao = time.time()
                resultados_trades = []
                novo_trade = []
                trade_history = pd.DataFrame()

                while True:
                    response, preco_float = backtest.backtesting(cripto=cripto, interval=interval)
                    
                    if response == "COMPRA":
                        print("Sinal de COMPRA detectado.")
                        # Abrir posição de compra
                        entry_price = preco_float
                        entry_time = datetime.now()
                        
                        # Registrar entrada no histórico
                        novo_trade = pd.DataFrame([{
                            'entry_time': entry_time,
                            'entry_price': entry_price
                        }])
                        
                        trade_history = pd.concat([trade_history, novo_trade], ignore_index=True)

                        print(f"[{datetime.now()}] Compra simulada a R${preco_float:.2f}")

                        lucro_liquido, retorno_percentual, indice_minuto, duracao = simular_compra_tempo_real(cripto, preco_float, stop_loss=0.03, stop_gain=0.05)
                        
                        resultados_trades.append({
                            "timestamp_entrada": entry_time,
                            "preco_entrada": entry_price,
                            "lucro_liquido": lucro_liquido,
                            "retorno_percentual": retorno_percentual,
                            "duracao": duracao
                        })
                        salvar_resultados_csv(resultados_trades, modelo="agente")
                        df_resultados = pd.DataFrame(resultados_trades)
                    else:
                        print("Sinal de COMPRA não detectado. Aguardando próxima vela.")
                        # Aguardar 5 minutos antes de verificar novamente
                        time.sleep(60)

                    tempo_agora = time.time()

                    if tempo_agora - inicio_ultima_gravacao >= 3600:
                        if resultados_trades:  # Só salva se houver dados
                            salvar_resultados_csv(df_resultados, modelo="agente")
                            print(f"[{datetime.now()}] Resultados salvos após 1h.")
                            resultados_trades = []  # Limpa após salvar
                        else:
                            print(f"[{datetime.now()}] Nenhum dado para salvar.")
                        inicio_ultima_gravacao = tempo_agora

            except KeyboardInterrupt:
                print("Parando execução... Salvando arquivos CSV.")
                if resultados_trades:
                    salvar_resultados_csv(resultados_trades, modelo="agente")
                    print("Dados salvos com sucesso.")
                else:
                    print("Nenhum dado para salvar.")

        elif escolha == 2:
            opcao_2()
            api_key = os.getenv("BINANCE_API_KEY")
            secret_key = os.getenv("BINANCE_SECRET_KEY")
            if not api_key or not secret_key:
                raise ValueError("As chaves da API da Binance não foram fornecidas.")
            client = Client(api_key, secret_key)
            symbol= str(input("Digite o ativo desejado: "))
            start = str(input("Digite a data inicial (formato ano-mes-dia): "))
            end = str(input("Digite a data final (formato ano-mes-dia): "))
            start_str = f"{start} 00:00:00"
            end_str = f"{end} 00:00:00"
            interval = Client.KLINE_INTERVAL_5MINUTE
            start_str = f"{start} 00:00:00"
            end_str = f"{end} 00:00:00"
            folder="outputs/data"

            candles = get_historical_klines(symbol, interval, start_str, end_str)

            df = pd.DataFrame(candles, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "number_of_trades",
                "taker_buy_base", "taker_buy_quote", "ignore"
            ])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')
            
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['high'] = pd.to_numeric(df['close'], errors='coerce')
            df['low'] = pd.to_numeric(df['close'], errors='coerce')
            df['volume'] = pd.to_numeric(df['close'], errors='coerce')
            close = df['close']
            high = df['high']
            low = df['low']
            volume = df['volume']

            # SMA e EMA
            df['SMA_50'] = ta.trend.sma_indicator(close, window=50)
            df['SMA_200'] = ta.trend.sma_indicator(close, window=200)
            df['EMA_20'] = ta.trend.ema_indicator(close, window=20)
            df['EMA_50'] = ta.trend.ema_indicator(close, window=50)

            # RSI
            df['RSI'] = ta.momentum.rsi(close, window=14)

            # MACD
            macd = MACD(close=close)
            df['MACD'] = macd.macd()
            df['MACD_signal'] = macd.macd_signal()
            df['MACD_diff'] = macd.macd_diff()

            # ADX
            df['ADX'] = ta.trend.adx(high, low, close, window=14)

            # MFI
            df['MFI'] = ta.volume.money_flow_index(high, low, close, volume, window=14)
            df.dropna(inplace=True)
            df.to_csv(f'outputs/data/{symbol}_com_indicadores_tecnicos.csv', index=False)

        elif escolha == 3:
            modelos = ['openchat:latest', 'llama3.2:3b', 'falcon3:3b', 'orca-mini:3b', 'qwen3:4b', 
                       'deepseek-r1:8b']
            print("\nVocê escolheu a Opção 3!\nBacktest com dados do CSV.")
            moeda = str(input("Digite o ativo desejado: "))
            for modelo in modelos:
                df = pd.read_csv(f'outputs/data/{moeda}_com_indicadores_tecnicos.csv')
                executar_backtest_em_batch(df, modelo)
        
        elif escolha == 4:
            opcao_4()
            
            try:
                print("Iniciando backtest de trade automático. Pressione Ctrl+C para parar.")
                top_cryptos = escolher_top_cryptos(max_price=0.01)
                backtest = Backtest()
                intervals = ["1h", "2h", "4h", "6h"]
                
                for cripto in top_cryptos['symbol'].iloc[:5]:
                    print(f"⏳ Monitorando {cripto}...")

                    inicio_ultima_gravacao = time.time()
                    resultados_trades = []
                    novo_trade = []
                    trade_history = pd.DataFrame()

                    while True:
                        sinal_detectado = False
                        for interval in intervals:
                            response, preco_float = backtest.backtesting(cripto=cripto, interval=interval)
                            
                            if response == "COMPRA":
                                print(f"Sinal de COMPRA detectado no intervalo {interval}.")
                                # Abrir posição de compra
                                entry_price = preco_float
                                entry_time = datetime.now()
                                
                                # Registrar entrada no histórico
                                novo_trade = pd.DataFrame([{
                                    'entry_time': entry_time,
                                    'entry_price': entry_price
                                }])
                                
                                trade_history = pd.concat([trade_history, novo_trade], ignore_index=True)

                                print(f"[{datetime.now()}] Compra simulada a R${preco_float:.5f}")

                                lucro_liquido, retorno_percentual, indice_minuto, duracao = simular_compra_tempo_real(cripto, preco_float, stop_loss=0.03, stop_gain=0.05)
                                
                                resultados_trades.append({
                                    "timestamp_entrada": entry_time,
                                    "cripto": cripto,
                                    "intervalo": interval,
                                    "preco_entrada": entry_price,
                                    "lucro_liquido": lucro_liquido,
                                    "retorno_percentual": retorno_percentual,
                                    "duracao": duracao
                                })
                                
                                df_resultados = pd.DataFrame(resultados_trades)
                                sinal_detectado = True
                                break
                            if not sinal_detectado:
                                print(f"Nenhum sinal de compra detectado no intervalo de {interval} para a crypto {cripto}. Aguardando 1 minuto.")

            except KeyboardInterrupt:
                print("Parando execução... Salvando arquivos CSV.")
                if resultados_trades:
                    salvar_resultados_csv(resultados_trades, modelo="agente")
                    print("Dados salvos com sucesso.")
                else:
                    print("Nenhum dado para salvar.")

        elif escolha == 0:

            print("\nSaindo do programa. Até logo!")
            break

        else:
            print("\nOpção inválida! Por favor, escolha uma opção disponível.")