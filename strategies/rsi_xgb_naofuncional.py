import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import pandas as pd
import ccxt
from ta.momentum import RSIIndicator
import pandas_ta as ta
import xgboost as xgb
from sklearn.preprocessing import MinMaxScaler
import numpy as np
from tqdm import tqdm
import os
import time
from scripts.backtest import calcular_retorno_sinais

def carregar_modelo_xgboost(model_path):
    """
    Carrega o modelo XGBoost a partir do caminho especificado.
    """
    if not os.path.exists(model_path):
        print(f"Erro: O modelo '{model_path}' não foi encontrado.")
        return None
    model = xgb.Booster()
    model.load_model(model_path)
    print("Modelo XGBoost carregado com sucesso.")
    return model

def normalizar_dados(df):
    """
    Normaliza os dados em uma CÓPIA do DataFrame, preservando o original.
    """
    # PASSO 1: Cria uma fotocópia para não modificar o documento original.
    df_copia = df.copy()

    scaler = MinMaxScaler()
    # A lista de colunas deve corresponder exatamente às colunas do seu DataFrame
    colunas_para_normalizar = ['open', 'high', 'low', 'close', 'volume', 'SMA_20', 'EMA_50', 'RSI_14', 'BBL_20_2.0', 'BBM_20_2.0', 'BBU_20_2.0', 'BBB_20_2.0', 'BBP_20_2.0']

    # PASSO 2: A partir de agora, todas as modificações são feitas na cópia,
    # deixando o 'df' original intacto.
    df_copia[colunas_para_normalizar] = scaler.fit_transform(df_copia[colunas_para_normalizar])

    # PASSO 3: Retorna a cópia modificada e os outros objetos.
    return df_copia, scaler, colunas_para_normalizar

def gerar_dataframe_predicoes_DIAGNOSTICO(df, modelo, scaler, colunas_features, janela=60):

    # Contador para imprimir o diagnóstico apenas na primeira vez que encontrar um sinal
    diagnostico_impresso = False

    df['sinal'] = np.nan
    # ---------------------------

    predicoes = []

    # Verifica se a coluna 'close' existe para evitar erros
    try:
        indice_close = colunas_features.index('close')
    except ValueError:
        print("ERRO CRÍTICO: A coluna 'close' não foi encontrada na lista 'colunas_features'!")
        print("A lista recebida foi:", colunas_features)
        return pd.DataFrame() # Retorna um DataFrame vazio se houver erro

    # Loop principal
    for i in tqdm(range(janela - 1, len(df)), desc="Gerando Predições com Diagnóstico"):
        sinal_rsi = df.loc[i, 'sinal_rsi'] # Renomeado para 'sinal_rsi' para clareza

        # A lógica de diagnóstico só será executada UMA VEZ, no primeiro sinal encontrado
        if sinal_rsi in [1, -1] and not diagnostico_impresso:

            # Etapas normais para predição
            janela_dados = df.loc[i - janela + 1:i, colunas_features]
            entrada = janela_dados.values.flatten().reshape(1, -1)
            dmatrix = xgb.DMatrix(entrada)
            pred_norm = modelo.predict(dmatrix)[0]

            # --- PONTO CRÍTICO: A DESNORMALIZAÇÃO ---
            matriz_pred = np.zeros((1, len(colunas_features)))
            matriz_pred[0, indice_close] = pred_norm

            try:
                # Tentativa de reverter a escala
                pred_desnormalizada_matriz = scaler.inverse_transform(matriz_pred)
                predicao_em_escala_real = pred_desnormalizada_matriz[0, indice_close]

                # Verificando o preço real também
                preco_real_normalizado = df.loc[i, 'close']
                matriz_real = np.zeros((1, len(colunas_features)))
                matriz_real[0, indice_close] = preco_real_normalizado
                preco_real_em_escala_real = scaler.inverse_transform(matriz_real)[0, indice_close]

                # Preço de referência para a predição
                preco_referencia = preco_real_em_escala_real

                print("-" * 50)
                print(f"DIAGNÓSTICO no índice {i} (sinal_rsi: {sinal_rsi}):")
                print(f"Preço real no momento do sinal: {preco_referencia:.2f}")
                print(f"Predição do modelo (escala real): {predicao_em_escala_real:.2f}")

                # Lógica para determinar a 'direção' da predição
                direcao_modelo = 0
                if predicao_em_escala_real > preco_referencia:
                    direcao_modelo = 1 # Modelo prevê alta
                    print("Modelo prevê: ALTA")
                elif predicao_em_escala_real < preco_referencia:
                    direcao_modelo = -1 # Modelo prevê baixa
                    print("Modelo prevê: BAIXA")
                else:
                    print("Modelo prevê: ESTABILIDADE")

                # Comparação com o sinal_rsi
                sinal_final_diagnostico = 0
                if direcao_modelo == sinal_rsi:
                    sinal_final_diagnostico = sinal_rsi
                    print(f"Concordância! Novo sinal atribuído: {sinal_final_diagnostico}")
                else:
                    print("Discordância. Nenhum sinal atribuído.")

                print("-" * 50)

            except Exception as e:
                print(f"\n!!! OCORREU UM ERRO DURANTE O 'inverse_transform' NO DIAGNÓSTICO: {e} !!!\n")

            diagnostico_impresso = True # Garante que o diagnóstico não se repita

        # O resto do código continua funcionando normalmente para gerar a lista completa
        # Apenas processa se houver um sinal na coluna 'sinal_rsi'
        if sinal_rsi in [1, -1]:
            janela_dados = df.loc[i - janela + 1:i, colunas_features]
            if janela_dados.isnull().values.any():
                continue # Pula se houver valores nulos na janela

            entrada = janela_dados.values.flatten().reshape(1, -1)
            dmatrix = xgb.DMatrix(entrada)
            pred_norm = modelo.predict(dmatrix)[0]

            matriz_pred = np.zeros((1, len(colunas_features)))
            matriz_pred[0, indice_close] = pred_norm

            try:
                pred_desnormalizada_matriz = scaler.inverse_transform(matriz_pred)
                predicao_em_escala_real = pred_desnormalizada_matriz[0, indice_close]

                preco_real_normalizado = df.loc[i, 'close']
                matriz_real = np.zeros((1, len(colunas_features)))
                matriz_real[0, indice_close] = preco_real_normalizado
                preco_real_em_escala_real = scaler.inverse_transform(matriz_real)[0, indice_close]

                # --- LÓGICA DE GERAÇÃO DE SINAL ---
                preco_referencia = preco_real_em_escala_real

                direcao_modelo = 0
                if predicao_em_escala_real > preco_referencia:
                    direcao_modelo = 1
                elif predicao_em_escala_real < preco_referencia:
                    direcao_modelo = -1

                sinal_final = np.nan # Padrão para não-sinal. Use 0 se preferir um número.
                if direcao_modelo == sinal_rsi:
                    sinal_final = sinal_rsi
                # ----------------------------------

            except Exception as e:
                print(f"\n!!! OCORREU UM ERRO DURANTE O 'inverse_transform' NA GERAÇÃO DE PREDIÇÕES: {e} !!!\n")
                predicao_em_escala_real = np.nan
                preco_real_em_escala_real = np.nan
                sinal_final = np.nan # Em caso de erro, o sinal também é NaN

            # --- NOVA ALTERAÇÃO AQUI ---
            # 2. Atribui o sinal_final diretamente à coluna 'sinal' no DataFrame original (df)
            df.loc[i, 'sinal'] = sinal_final
            # ---------------------------

            # Continua adicionando ao DataFrame de predições (o retorno da função)
            # Isso é útil para ter um resumo das predições feitas, mas o DF original já terá o 'sinal'
            predicoes.append({
                'indice': i,
                'timestamp': df.loc[i, 'timestamp'],
                'sinal_rsi': sinal_rsi,
                'preco_real': preco_real_em_escala_real,
                'predicao_original': float(predicao_em_escala_real),
                'sinal': sinal_final # Mantém no DataFrame de retorno também, para consistência
            })
    # df = df.dropna()
    return pd.DataFrame(predicoes), df

def obter_candles(df_candles):
    df_candles.rename(columns={
                            'Timestamp': 'timestamp',
                            'Open': 'open',
                            'High': 'high',
                            'Low': 'low',
                            'Close': 'close',
                            'Volume': 'volume'
                        }, inplace=True)

    rsi = RSIIndicator(df_candles['close'], window=5)

    df_candles['RSI_5'] = rsi.rsi()

    rsi = RSIIndicator(df_candles['close'], window=21)
    df_candles['RSI_21'] = rsi.rsi()

    # Preenche os valores NaN iniciais para evitar erros
    df_candles.fillna(0, inplace=True)

    df_candles.ta.sma(length=20, append=True) # Média Móvel Simples
    df_candles.ta.ema(length=50, append=True) # Média Móvel Exponencial
    df_candles.ta.rsi(length=14, append=True) # Índice de Força Relativa (RSI)
    df_candles.ta.bbands(length=20, append=True) # Bandas de Bollinger

    # 3. Lógica da Estratégia
    # Identificar o cruzamento e as condições de tendência.
    sinal = []
    for i in range(1, len(df_candles)):
        # Condições para SINAL DE COMPRA
        condicao_compra_1 = df_candles['RSI_5'][i-1] < df_candles['RSI_21'][i-1] # RSI_5 estava abaixo
        condicao_compra_2 = df_candles['RSI_5'][i] > df_candles['RSI_21'][i]    # RSI_5 cruzou para cima
        condicao_compra_3 = df_candles['RSI_5'][i] > 50 and df_candles['RSI_21'][i] > 50 # Ambos acima de 50

        # Condições para SINAL DE VENDA
        condicao_venda_1 = df_candles['RSI_5'][i-1] > df_candles['RSI_21'][i-1] # RSI_5 estava acima
        condicao_venda_2 = df_candles['RSI_5'][i] < df_candles['RSI_21'][i]    # RSI_5 cruzou para baixo
        condicao_venda_3 = df_candles['RSI_5'][i] < 50 and df_candles['RSI_21'][i] < 50 # Ambos abaixo de 50

        if condicao_compra_1 and condicao_compra_2 and condicao_compra_3:
            sinal.append(1)
        elif condicao_venda_1 and condicao_venda_2 and condicao_venda_3:
            sinal.append(-1)
        else:
            sinal.append(0)

    # Adiciona a primeira posição como "AGUARDAR"
    sinal.insert(0, 'AGUARDAR')
    df_candles['sinal_rsi'] = sinal
    df_candles.dropna(inplace=True)

    return df_candles

def main():
    times = ['1min', '5min', '15min', '30min', '60min']
    
    try:
        for t in times:

            with open(f'./outputs/btc_{t}.csv') as f:
                total_linhas = sum(1 for _ in f)

            # Calcula quantas linhas pular (menos o cabeçalho)
            linhas_a_pular = total_linhas - 200000
            if linhas_a_pular <= 0:
                linhas_a_pular = 0

            data = pd.read_csv(f'./outputs/btc_{t}.csv', skiprows=range(1, linhas_a_pular))
            df_candles = obter_candles(data)

            df_normalizado, scaler, colunas_para_normalizar = normalizar_dados(df_candles)
            model = carregar_modelo_xgboost('./config/modelo_xgboost.json')

            df_predicoes, df_sinais = gerar_dataframe_predicoes_DIAGNOSTICO(df_normalizado, model, scaler, colunas_para_normalizar)

            df_sinais.to_csv(f'outputs/data/analise_rsi_xgb/rsixgb_{t}.csv', index=False)
            
            if df_sinais is not None:
                retorno = calcular_retorno_sinais(df_sinais, horizontes=[5, 10, 20, 30, 60, 120])
                retorno.to_csv(f'outputs/data/analise_rsi_xgb/calculo_retorno_rsixgb_{t}.csv', index=False)

    except Exception as e:
        print(f"Erro na estratégia RSI XGB: {e}")
    

if __name__ == "__main__":
    main()