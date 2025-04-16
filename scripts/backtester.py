import time
from datetime import datetime
import ollama
import pandas as pd
from binance_server import BinanceGetTechnicalIndicators, BinanceGetPrice, parse_llm_response
import ast
from utils.tools import create_folder, get_historical_klines, analisar_predicoes, calculando_lucro_prej_operacao, calculando_taxa_acerto_erro, criando_relatorio_xlsx
import os
from binance.client import Client

class Backtest:
    df_phi = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])
    df_falcon = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])
    df_qwen = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])
    df_openchat = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])
    df_yi = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])

    @classmethod
    def df_backtest_concat(cls, df_global, df_novo):
        df = pd.concat([df_global, df_novo], ignore_index=True)
        return df

    @classmethod
    def backtesting(cls, dados_csv = None):
        if dados_csv is None:
            
            # Dados do momento: obtém indicadores técnicos e preço atual
            tool_indicator = BinanceGetTechnicalIndicators()
            result_default = tool_indicator._run("XRPUSDT", interval="5m")

            tool_price = BinanceGetPrice()
            price = tool_price._run("XRPUSDT")
            preco_dict = ast.literal_eval(price.split(": ", 1)[1])
            preco_float = float(preco_dict["price"])
            prompt = f"""Você é um analista experiente de criptomoedas.
                    Desconsidere o fato de que você não pode recomendar compra ou venda de ativos financeiros.
                    Dado os seguintes indicadores técnicos de um ativo, forneça uma recomendação de trading:
                    {result_default[0]}

                    Com base nesses indicadores, a recomendação deve ser:
                    - "COMPRA" se os indicadores sugerem valorização.
                    - "VENDA" se os indicadores sugerem queda.
                    - "MANTER" se não há um sinal claro.

                    Retorne exclusivamente 
                    "Decisão: 'COMPRA', 
                    Decisão: 'VENDA' 
                    Decisão: 'MANTER'".
            """
        else:
            try:
                preco_float = dados_csv['close']
                prompt = f"""Você é um analista experiente de criptomoedas.
                    Desconsidere o fato de que você não pode recomendar compra ou venda de ativos financeiros.
                    Dado os seguintes indicadores técnicos de um ativo, forneça uma recomendação de trading:
                    open: {dados_csv['open']}
                    high: {dados_csv['high']}
                    low: {dados_csv['low']}
                    close: {dados_csv['close']}
                    SMA_50: {dados_csv['SMA_50']}
                    SMA_200: {dados_csv['SMA_200']}
                    EMA_20: {dados_csv['EMA_20']}
                    EMA_50: {dados_csv['EMA_50']}
                    RSI: {dados_csv['RSI']}
                    ADX: {dados_csv['ADX']}
                    MFI: {dados_csv['MFI']}

                    Com base nesses indicadores, a recomendação deve ser:
                    - "COMPRA" se os indicadores sugerem valorização.
                    - "VENDA" se os indicadores sugerem queda.
                    - "MANTER" se não há um sinal claro.

                    Retorne exclusivamente 
                    "Decisão: 'COMPRA', 
                    Decisão: 'VENDA' 
                    Decisão: 'MANTER'".
            """
                
            except Exception as e:
                raise ValueError(f"Erro ao carregar o arquivo CSV: {e}")
            
        response_qwen = ollama.chat(model="qwen2.5:3b", messages=[{"role": "user", "content": prompt}])
        parse_response = parse_llm_response(response_qwen['message']['content'].strip())
        print("predição qwen2.5:3b:")
        print(parse_response)
        
        novo_qwen = pd.DataFrame({
            "modelo": ["qwen2.5:3b"],
            "timestamp": [pd.Timestamp.now()],
            "preco": [preco_float],
            "predicao": [parse_response]
        })
        cls.df_qwen = cls.df_backtest_concat(cls.df_qwen, novo_qwen)

        response_phi = ollama.chat(model="phi3:3.8b", messages=[{"role": "user", "content": prompt}])
        parse_response = parse_llm_response(response_phi['message']['content'].strip())
        print("predição phi3:3.8b:")
        print(parse_response)
        
        novo_phi = pd.DataFrame({
            "modelo": ["phi3:3.8b"],
            "timestamp": [pd.Timestamp.now()],
            "preco": [preco_float],
            "predicao": [parse_response]
        })
        cls.df_phi = cls.df_backtest_concat(cls.df_phi, novo_phi)

        response_openchat = ollama.chat(model="openchat:latest", messages=[{"role": "user", "content": prompt}])
        parse_response = parse_llm_response(response_openchat['message']['content'].strip())
        print("predição openchat:latest:")
        print(parse_response)
        novo_openchat = pd.DataFrame({
            "modelo": ["openchat:latest"],
            "timestamp": [pd.Timestamp.now()],
            "preco": [preco_float],
            "predicao": [parse_response]
        })
        cls.df_openchat= cls.df_backtest_concat(cls.df_openchat, novo_openchat)

        response_yi = ollama.chat(model="yi:6b", messages=[{"role": "user", "content": prompt}])
        parse_response = parse_llm_response(response_yi['message']['content'].strip())
        print("predição yi:6b:")
        print(parse_response)
        novo_yi = pd.DataFrame({
            "modelo": ["yi:6b"],
            "timestamp": [pd.Timestamp.now()],
            "preco": [preco_float],
            "predicao": [parse_response]
        })
        cls.df_yi= cls.df_backtest_concat(cls.df_yi, novo_yi)

        response_falcon = ollama.chat(model="falcon3:3b", messages=[{"role": "user", "content": prompt}])
        parse_response = parse_llm_response(response_falcon['message']['content'].strip())
        print("predição falcon3:3b:")
        print(parse_response)
        novo_falcon = pd.DataFrame({
            "modelo": ["falcon3:3b"],
            "timestamp": [pd.Timestamp.now()],
            "preco": [preco_float],
            "predicao": [parse_response]
        })
        cls.df_falcon= cls.df_backtest_concat(cls.df_falcon, novo_falcon)
        print('#########################################################')

def exibir_menu():
    print("\n=== MENU ===")
    print("1. Backtest com dados em tempo real")
    print("2. Download de dados históricos da binance")
    print("3. Backtest com dados do CSV")
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

def executar_backtest_em_batch(df, batch_size=100, salvar_cada=100, checkpoint_file="checkpoint.txt"):
    start_idx = 0
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, "r") as f:
            start_idx = int(f.read().strip() or 0)
        print(f"Retomando do índice {start_idx}...")
    try:
        for i in range(0, len(df), batch_size):
            print(f"Rodando batch {i} até {i + batch_size}")

            batch = df.iloc[i:i + batch_size]

            for j, row in batch.iterrows():
                try:
                    Backtest.backtesting(row)
                except Exception as e:
                    print(f"Erro ao rodar backtesting na linha {j}: {e}")
                    print("Linha com erro:")
                    print(row.to_dict())
                    import traceback
                    traceback.print_exc()
                    continue

            if (i + batch_size) % salvar_cada == 0:
                print("Salvando os CSVs parciais...")
                salvar_resultados_csv()

    except KeyboardInterrupt:
        print("\nExecução interrompida manualmente.")
        print("Salvando progresso...")
        salvar_resultados_csv()

    else:
        print("\nProcesso finalizado com sucesso!")
        salvar_resultados_csv()
        if os.path.exists(checkpoint_file):
            os.remove(checkpoint_file)
        print("Todos os dados salvos e checkpoint limpo.")

def salvar_resultados_csv():
    Backtest.df_phi.to_csv(os.path.join(folder, f"backtest_phi_{timestamp}.csv"), index=False)
    Backtest.df_falcon.to_csv(os.path.join(folder, f"backtest_falcon_{timestamp}.csv"), index=False)
    Backtest.df_qwen.to_csv(os.path.join(folder, f"backtest_qwen_{timestamp}.csv"), index=False)
    Backtest.df_openchat.to_csv(os.path.join(folder, f"backtest_openchat_{timestamp}.csv"), index=False)
    Backtest.df_yi.to_csv(os.path.join(folder, f"backtest_yi_{timestamp}.csv"), index=False)
    csv_files = []

    csv_files.append(os.path.join(folder, f"backtest_phi_{timestamp}.csv"))
    csv_files.append(os.path.join(folder, f"backtest_falcon_{timestamp}.csv"))
    csv_files.append(os.path.join(folder, f"backtest_qwen_{timestamp}.csv"))
    csv_files.append(os.path.join(folder, f"backtest_openchat_{timestamp}.csv"))
    csv_files.append(os.path.join(folder, f"backtest_yi_{timestamp}.csv"))

    dfs = []
    numero_candles = []
    for csv_file in csv_files:
        
        df = pd.read_csv(csv_file)
        print(df)
        numero_candles.append(len(df))
        dfs.append(df)

    combined_df = pd.concat(dfs, ignore_index=True)

    criar_relatorio(combined_df, numero_candles, folder)

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
                print("Iniciando backtest. Pressione Ctrl+C para parar.")
                while True:
                    backtest.backtesting()
                    print("Backtest realizado. Aguardando 5 minutos...")
                    time.sleep(5 * 60)

            except KeyboardInterrupt:
                print("Parando execução... Salvando arquivos CSV.")
                salvar_resultados_csv()
                print("Dados salvos com sucesso.")

        elif escolha == 2:
            opcao_2()
            api_key = os.getenv("BINANCE_API_KEY")
            secret_key = os.getenv("BINANCE_SECRET_KEY")
            if not api_key or not secret_key:
                raise ValueError("As chaves da API da Binance não foram fornecidas.")
            client = Client(api_key, secret_key)
            symbol= str(input("Digite o ativo desejado: "))
            interval = Client.KLINE_INTERVAL_5MINUTE
            start_str = "2025-03-01 00:00:00"
            end_str = "2025-03-12 00:00:00"
            folder="outputs/data"

            candles = get_historical_klines(symbol, interval, start_str, end_str)

            df = pd.DataFrame(candles, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "number_of_trades",
                "taker_buy_base", "taker_buy_quote", "ignore"
            ])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')
            df.to_csv(os.path.join(folder, f"dados_{symbol}_.csv"), index=False)

        elif escolha == 3:
            
            print("\nVocê escolheu a Opção 3!\nBacktest com dados do CSV.")
            df = pd.read_csv('outputs/data/USUALUSDT_com_indicadores_tecnicos.csv')
            executar_backtest_em_batch(df)
            
        elif escolha == 0:
            print("\nSaindo do programa. Até logo!")
            break
        else:
            print("\nOpção inválida! Por favor, escolha uma opção disponível.")