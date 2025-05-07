import time
from datetime import datetime
import ollama
import pandas as pd
from binance_server import BinanceGetTechnicalIndicators, BinanceGetPrice, BinanceListCryptosByPrice, parse_llm_response
import ast
from utils.tools import gerar_indicadores_para_criptos, simular_compra_tempo_real, gerando_predição_tempo_real, create_folder, get_historical_klines, analisar_predicoes, calculando_lucro_prej_operacao, calculando_taxa_acerto_erro, criando_relatorio_xlsx, simular_trade_compra_com_csv
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
            tool_indicator = BinanceGetTechnicalIndicators()
            result_default = tool_indicator._run(cripto, interval)

            tool_price = BinanceGetPrice()
            price = tool_price._run(cripto)
            preco_dict = ast.literal_eval(price.split(": ", 1)[1])
            preco_float = float(preco_dict["price"])
            
            parse_response = gerando_predição_tempo_real(result_default[0])
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
          Selecionar melhores Cryptos.""")
    
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

def salvar_resultados_csv(resultados_trades, nome_arquivo):
    
    if resultados_trades:
        df_resultados = pd.DataFrame(resultados_trades)
        if os.path.exists(nome_arquivo):
            df_existente = pd.read_csv(nome_arquivo)
            df_resultados = pd.concat([df_existente, df_resultados], ignore_index=True)
        df_resultados = df_resultados.drop_duplicates(subset=['id_trade', 'indice_inicio', 'indice_fim', 'preco_entrada', 'preco_saida', 'timestamp_entrada', 'timestamp_saida'])
        modelo = nome_arquivo.replace(':', '').replace('.', '').replace('-', '')
        
        df_resultados.to_csv(f'outputs/data/resultados_trades_{modelo}.csv', index=False)
        print(f"Resultados salvos em outputs/data/resultados_trades_{modelo}.csv")

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
            tool = BinanceListCryptosByPrice(max_price=0.0001)
            result = tool._run()
            print(result.shape[0])
            resultados = gerar_indicadores_para_criptos(result)
            def acertar_linhas(linhas):
                if isinstance(linhas, (pd.Series, list)):
                    linhas = [x for x in linhas if x is not None and not pd.isna(x)]
                    ultima_linha = linhas[-1] if linhas else 'N/A'
                else:
                    ultima_linha = sma_50 if pd.notna(linhas) else 'N/A'
                return ultima_linha
            
            for symbol, data in resultados.items():
                # Pegando o último candle
                
                ultimo_candle = data['historical_data'].iloc[-2]
                open_ = ultimo_candle['Open']
                high = ultimo_candle['High']
                low = ultimo_candle['Low']
                close = ultimo_candle['Close']
                volume = ultimo_candle['Volume']

                # Pegando os indicadores
                rsi = data['indicators'].get('rsi', 'N/A')
                if rsi is not None:
                    ultimo_valor_rsi = acertar_linhas(rsi)
                else:
                    ultimo_valor_rsi = 'N/A'

                sma_50 = data['indicators'].get('sma_50', 'N/A')
                if sma_50 is not None:
                    ultimo_valor_sma_50 = acertar_linhas(sma_50)
                else:
                    ultimo_valor_sma_50 = 'N/A'

                sma_200 = data['indicators'].get('sma_200', 'N/A')
                if sma_200 is not None:
                    ultimo_valor_sma_200 = acertar_linhas(sma_200)
                else:
                    ultimo_valor_sma_200 = 'N/A'

                ema_20 = data['indicators'].get('ema_20', 'N/A')
                if ema_20 is not None:
                    ultimo_valor_ema_20 = acertar_linhas(ema_20)
                else:
                    ultimo_valor_ema_20 = 'N/A'

                ema_50 = data['indicators'].get('ema_50', 'N/A')
                if ema_50 is not None:
                    ultimo_valor_ema_50 = acertar_linhas(ema_50)
                else:
                    ultimo_valor_ema_50 = 'N/A'

                adx = data['indicators'].get('adx', 'N/A')
                if adx is not None:
                    ultimo_valor_adx = acertar_linhas(adx)
                else:   
                    ultimo_valor_adx = 'N/A'

                mfi = data['indicators'].get('mfi', 'N/A')
                if mfi is not None:
                    ultimo_valor_mfi = acertar_linhas(mfi)
                else:
                    ultimo_valor_mfi = 'N/A'

                macd = data['indicators'].get('macd', 'N/A')
                if macd is not None:
                    ultimo_valor_macd_line = acertar_linhas(macd['macd_line'])
                    ultimo_valor_macd_signal = acertar_linhas(macd['signal_line'])
                    ultimo_valor_macd_histogram = acertar_linhas(macd['histogram'])
                else:
                    ultimo_valor_macd_line = 'N/A'
                    ultimo_valor_macd_signal = 'N/A'
                    ultimo_valor_macd_histogram = 'N/A'

                bollinger = data['indicators'].get('bollinger_bands', 'N/A')
                if bollinger is not None:
                    ultimo_valor_bollinger_upper = acertar_linhas(bollinger['upper_band'])
                    ultimo_valor_bollinger_middle = acertar_linhas(bollinger['middle_band'])
                    ultimo_valor_bollinger_lower = acertar_linhas(bollinger['lower_band'])
                else:
                    ultimo_valor_bollinger_upper = 'N/A'
                    ultimo_valor_bollinger_middle = 'N/A'
                    ultimo_valor_bollinger_lower = 'N/A'

                
                pivot = data['indicators'].get('pivot_points', 'N/A')
                if pivot is not None:
                    ultimo_valor_pivot = acertar_linhas(pivot['pivot'])
                    ultimo_valor_pivot_r1 = acertar_linhas(pivot['r1'])
                    ultimo_valor_pivot_s1 = acertar_linhas(pivot['s1'])
                    ultimo_valor_pivot_r2 = acertar_linhas(pivot['r2'])
                    ultimo_valor_pivot_s2 = acertar_linhas(pivot['s2'])
                    ultimo_valor_pivot_r3 = acertar_linhas(pivot['r3'])
                    ultimo_valor_pivot_s3 = acertar_linhas(pivot['s3'])
                else:
                    ultimo_valor_pivot = 'N/A'
                    ultimo_valor_pivot_r1 = 'N/A'
                    ultimo_valor_pivot_s1 = 'N/A'
                    ultimo_valor_pivot_r2 = 'N/A'
                    ultimo_valor_pivot_s2 = 'N/A'
                    ultimo_valor_pivot_r3 = 'N/A'
                    ultimo_valor_pivot_s3 = 'N/A'
                
                stochastic = data['indicators'].get('stochastic', 'N/A')
                if stochastic is not None:
                    ultimo_valor_stochastic_k = acertar_linhas(stochastic['stochastic_k'])
                    ultimo_valor_stochastic_d = acertar_linhas(stochastic['stochastic_d'])
                else:
                    ultimo_valor_stochastic_k = 'N/A'
                    ultimo_valor_stochastic_d = 'N/A'

                prompt = f"""
                O ativo {symbol} apresentou os seguintes dados no último candle:
                - Abertura: {open_}
                - Máxima: {high}
                - Mínima: {low}
                - Fechamento: {close}
                - Volume: {volume}
                - SMA(50): {ultimo_valor_sma_50}
                - SMA(200): {ultimo_valor_sma_50}
                - EMA(20): {ultimo_valor_ema_20}
                - EMA(50): {ultimo_valor_ema_50}
                - ADX: {ultimo_valor_adx}
                - MFI: {ultimo_valor_mfi}
                - RSI: {ultimo_valor_rsi}
                - MACD: {ultimo_valor_macd_line}
                - MACD Signal: {ultimo_valor_macd_signal} 
                - MACD Histogram: {ultimo_valor_macd_histogram}
                - Bollinger Upper: {ultimo_valor_bollinger_upper}
                - Bollinger Middle: {ultimo_valor_bollinger_middle}
                - Bollinger Lower: {ultimo_valor_bollinger_lower}
                - Pivot: {ultimo_valor_pivot}
                - Pivot R1: {ultimo_valor_pivot_r1}
                - Pivot S1: {ultimo_valor_pivot_s1}
                - Pivot R2: {ultimo_valor_pivot_r2}
                - Pivot S2: {ultimo_valor_pivot_s2}
                - Pivot R3: {ultimo_valor_pivot_r3}
                - Pivot S3: {ultimo_valor_pivot_s3}
                - Stochastic K: {ultimo_valor_stochastic_k}
                - Stochastic D: {ultimo_valor_stochastic_d}
                 
                Com base nesses indicadores e no comportamento histórico recente, qual a sua previsão para o próximo movimento do ativo ({symbol})? Alta, queda ou estabilidade? Justifique com base nos dados.
                """
                print(prompt)

        elif escolha == 0:

            print("\nSaindo do programa. Até logo!")
            break

        else:
            print("\nOpção inválida! Por favor, escolha uma opção disponível.")