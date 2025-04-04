import time
from datetime import datetime
import ollama
import pandas as pd
from binance_server import BinanceGetTechnicalIndicators, BinanceGetPrice, parse_llm_response
import ast
from utils.tools import create_folder
import os

class Backtest:
    df_phi = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])
    df_gemma = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])
    df_deepseek = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])
    df_orca = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])
    df_falcon = pd.DataFrame(columns=["modelo", "timestamp", "preco", "predicao"])

    @classmethod
    def df_backtest_concat(cls, df_global, df_novo):
        df = pd.concat([df_global, df_novo], ignore_index=True)
        return df

    @classmethod
    def backtesting(cls):
        
        tool_indicator = BinanceGetTechnicalIndicators()
        result_default = tool_indicator._run("XRPUSDT", interval="5m")

        tool_price = BinanceGetPrice()
        price = tool_price._run("XRPUSDT")
        preco_dict = ast.literal_eval(price.split(": ", 1)[1])
        preco_float = float(preco_dict["price"])

        prompt = f"""Você é um analista experiente de criptomoedas.
            Desconsidere o fato de que você não pode recomendar compra ou venda de ativos financeiros.
            Dado os seguintes indicadores técnicos de um ativo, forneça uma recomendação de trading:
            {result_default}

            Com base nesses indicadores, a recomendação deve ser:
            - "COMPRA" se os indicadores sugerem valorização.
            - "VENDA" se os indicadores sugerem queda.
            - "MANTER" se não há um sinal claro.

            Retorne exclusivamente Decisão: "COMPRA", 
            Decisão: "VENDA" ou 
            Decisão: "MANTER".
            """
        
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

backtest = Backtest()

try:
    print("Iniciando backtest. Pressione Ctrl+C para parar.")
    while True:
        backtest.backtesting()
        print("Backtest realizado. Aguardando 5 minutos...")
        time.sleep(5 * 60)

except KeyboardInterrupt:
    print("Parando execução... Salvando arquivos CSV.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    folder="outputs/data"
    create_folder(folder)

    Backtest.df_phi.to_csv(os.path.join(folder, f"backtest_qwen_{timestamp}.csv"), index=False)
    Backtest.df_deepseek.to_csv(os.path.join(folder, f"backtest_deepseek_{timestamp}.csv"), index=False)
    Backtest.df_gemma.to_csv(os.path.join(folder, f"backtest_gemma_{timestamp}.csv"), index=False)
    Backtest.df_orca.to_csv(os.path.join(folder, f"backtest_mistral_{timestamp}.csv"), index=False)
    Backtest.df_falcon.to_csv(os.path.join(folder, f"backtest_mistral_{timestamp}.csv"), index=False)
    print("Dados salvos com sucesso.")