import time
from datetime import datetime
import ollama
import pandas as pd
from binance_server import BinanceGetTechnicalIndicators, BinanceGetPrice, parse_llm_response
import ast
from utils.tools import create_folder, get_historical_klines
import os
from binance.client import Client

class Backtest:
    df_phi = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])
    df_gemma = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])
    df_deepseek = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])
    df_orca = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])
    df_falcon = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])
    df_mistral = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])
    df_qwen = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])
    df_llama = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])

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
            
        response_llama = ollama.chat(model="llama3.2:3b", messages=[{"role": "user", "content": prompt}])
        parse_response = parse_llm_response(response_llama['message']['content'].strip())
        print("predição llama3.2:3b:")
        print(parse_response)
        
        novo_llama = pd.DataFrame({
            "modelo": ["llama3.2:3b"],
            "timestamp": [pd.Timestamp.now()],
            "preco": [preco_float],
            "predicao": [parse_response]
        })
        cls.df_llama = cls.df_backtest_concat(cls.df_llama, novo_llama)

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

        response_mistral = ollama.chat(model="mistral", messages=[{"role": "user", "content": prompt}])
        parse_response = parse_llm_response(response_mistral['message']['content'].strip())
        print("predição mistral:")
        print(parse_response)

        novo_mistral = pd.DataFrame({
            "modelo": ["mistral"],
            "timestamp": [pd.Timestamp.now()],
            "preco": [preco_float],
            "predicao": [parse_response]
        })
        cls.df_mistral = cls.df_backtest_concat(cls.df_mistral, novo_mistral)

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
        
        response_deepseek = ollama.chat(model="deepseek-r1:8b", messages=[{"role": "user", "content": prompt}])
        parse_response = parse_llm_response(response_deepseek['message']['content'].strip())
        print("predição deepseek-r1:8b:")
        print(parse_response)
        novo_deepseek = pd.DataFrame({
            "modelo": ["deepseek-r1:8b"],
            "timestamp": [pd.Timestamp.now()],
            "preco": [preco_float],
            "predicao": [parse_response]
        })
        cls.df_deepseek = cls.df_backtest_concat(cls.df_deepseek, novo_deepseek)

        response_gemma = ollama.chat(model="gemma3:4b", messages=[{"role": "user", "content": prompt}])
        parse_response = parse_llm_response(response_gemma['message']['content'].strip())
        print("predição gemma3:4b:")
        print(parse_response)
        novo_gemma = pd.DataFrame({
            "modelo": ["gemma3:4b"],
            "timestamp": [pd.Timestamp.now()],
            "preco": [preco_float],
            "predicao": [parse_response]
        })
        cls.df_gemma= cls.df_backtest_concat(cls.df_gemma, novo_gemma)

        response_orca = ollama.chat(model="orca-mini:3b", messages=[{"role": "user", "content": prompt}])
        parse_response = parse_llm_response(response_orca['message']['content'].strip())
        print("predição orca-mini:3b:")
        print(parse_response)
        novo_orca = pd.DataFrame({
            "modelo": ["orca-mini:3b"],
            "timestamp": [pd.Timestamp.now()],
            "preco": [preco_float],
            "predicao": [parse_response]
        })
        cls.df_orca= cls.df_backtest_concat(cls.df_orca, novo_orca)

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
          Download de dados históricos da binance.""")

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
    Backtest.df_deepseek.to_csv(os.path.join(folder, f"backtest_deepseek_{timestamp}.csv"), index=False)
    Backtest.df_gemma.to_csv(os.path.join(folder, f"backtest_gemma_{timestamp}.csv"), index=False)
    Backtest.df_orca.to_csv(os.path.join(folder, f"backtest_orca_{timestamp}.csv"), index=False)
    Backtest.df_falcon.to_csv(os.path.join(folder, f"backtest_falcon_{timestamp}.csv"), index=False)
    Backtest.df_qwen.to_csv(os.path.join(folder, f"backtest_qwen_{timestamp}.csv"), index=False)
    Backtest.df_llama.to_csv(os.path.join(folder, f"backtest_llama_{timestamp}.csv"), index=False)
    Backtest.df_mistral.to_csv(os.path.join(folder, f"backtest_mistral_{timestamp}.csv"), index=False)

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

                Backtest.df_phi.to_csv(os.path.join(folder, f"backtest_phi_{timestamp}.csv"), index=False)
                Backtest.df_deepseek.to_csv(os.path.join(folder, f"backtest_deepseek_{timestamp}.csv"), index=False)
                Backtest.df_gemma.to_csv(os.path.join(folder, f"backtest_gemma_{timestamp}.csv"), index=False)
                Backtest.df_orca.to_csv(os.path.join(folder, f"backtest_orca_{timestamp}.csv"), index=False)
                Backtest.df_falcon.to_csv(os.path.join(folder, f"backtest_falcon_{timestamp}.csv"), index=False)
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
            start_str = "2024-01-01 00:00:00"
            end_str = "2024-03-31 00:00:00"
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
            df = pd.read_csv('outputs/data/candles_com_indicadores_tecnicos.csv')
            executar_backtest_em_batch(df)
            
        elif escolha == 0:
            print("\nSaindo do programa. Até logo!")
            break
        else:
            print("\nOpção inválida! Por favor, escolha uma opção disponível.")

        

