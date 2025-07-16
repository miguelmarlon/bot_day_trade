import pandas as pd
import numpy as np

# def calcular_retorno_sinais(df: pd.DataFrame, horizontes: list = [5, 10, 20, 30, 50, 60]) -> pd.DataFrame:
#     """
#     Calcula os retornos futuros para cada sinal (1=compra, -1=short) em múltiplos horizontes.
    
#     Parâmetros:
#     -----------
#     df : pd.DataFrame
#         DataFrame com colunas: ['close', 'sinal'] (assumindo timestamp como índice)
#     horizontes : list
#         Lista de horizontes (em candles) para os quais calcular o retorno futuro.
    
#     Retorno:
#     --------
#     pd.DataFrame com novas colunas 'return_N' contendo os retornos futuros para cada N em horizontes.
#     """
#     try:
#         df_result = df.copy()

#         df_result['sinal'] = pd.to_numeric(df_result['sinal'], errors='coerce').fillna(0)

#         for h in horizontes:
#             col_name = f'return_{h}'
            
#             preco_futuro = df_result['close'].shift(-h)
            
#             retorno_bruto = (preco_futuro - df_result['close']) / df_result['close']
            
#             retornos_finais = np.where(
#                 df_result['sinal'] == 1,
#                 retorno_bruto,     
#                 np.where(
#                     df_result['sinal'] == -1, 
#                     -retorno_bruto,          
#                     np.nan                   
#                 )
#             )
            
#             df_result[col_name] = retornos_finais 

#         return df_result
    
#     except KeyError as ke:
#         print(f"Erro: Coluna essencial faltando no DataFrame. Certifique-se de que 'close' e 'sinal' existam. Detalhes: {ke}")
#         return pd.DataFrame()
#     except Exception as e:
#         print(f"Erro inesperado na função calcular_retorno_sinais: {e}")
#         return pd.DataFrame()

def calcular_retorno_sinais_base_minuto(
    df_sinais: pd.DataFrame,
    df_base: pd.DataFrame,
    horizontes_minutos: list = [5, 10, 15, 30, 60]
) -> pd.DataFrame:
    """
    Calcula os retornos futuros dos sinais com base em candles de 1 minuto.

    Parâmetros:
    -----------
    df_sinais : pd.DataFrame
        DataFrame com os sinais gerados (1=compra, -1=short), com coluna 'sinal' e 'close'.
    df_base : pd.DataFrame
        DataFrame de candles de 1 minuto, contendo colunas ['Timestamp', 'close'].
    horizontes_minutos : list
        Lista de horizontes de tempo (em minutos) para calcular o retorno futuro.

    Retorno:
    --------
    DataFrame df_sinais com colunas adicionais return_X, onde X é o número de minutos.
    """

    df_result = df_sinais.copy()
    df_base = df_base.copy()
    df_result['sinal'] = pd.to_numeric(df_result['sinal'], errors='coerce').fillna(0)
    df_base['Close'] = pd.to_numeric(df_base['Close'], errors='coerce').fillna(0)

    if 'Timestamp' in df_base.columns:
        df_base.set_index('Timestamp', inplace=True)

    if 'Timestamp' in df_result.columns:
        df_result.set_index('Timestamp', inplace=True)

    df_base.sort_index(inplace=True)
    df_result.sort_index(inplace=True)

    for h in horizontes_minutos:
        retorno = []
        for ts, row in df_result.iterrows():
            try:
                preco_atual = row['Close']
                preco_futuro = df_base.loc[ts + pd.Timedelta(minutes=h) :].iloc[0]['Close']

                bruto = (preco_futuro - preco_atual) / preco_atual

                if row['sinal'] == 1:
                    retorno.append(bruto)
                elif row['sinal'] == -1:
                    retorno.append(-bruto)
                else:
                    retorno.append(np.nan)
            except Exception:
                retorno.append(np.nan)

        df_result[f'return_{h}'] = retorno

        long_ops = df_result[df_result['sinal'] == 1]
        short_ops = df_result[df_result['sinal'] == -1]
        
        retorno_long = long_ops[f'return_{h}'].sum()
        retorno_short = short_ops[f'return_{h}'].sum()
        retorno_total = retorno_long + retorno_short
        
        total_long = len(long_ops)
        total_short = len(short_ops)
        total = total_long + total_short

        long_acertos = long_ops[long_ops[f'return_{h}'] > 0]
        short_acertos = short_ops[short_ops[f'return_{h}'] < 0]
        acertos_long = len(long_acertos)
        acertos_short = len(short_acertos)
        total_acertos = acertos_long + acertos_short

        pct_acerto_long = (acertos_long / total_long * 100) if total_long > 0 else 0.0
        pct_acerto_short = (acertos_short / total_short * 100) if total_short > 0 else 0.0
        pct_acerto_total = (total_acertos / total * 100) if total > 0 else 0.0

        print(f"[{f'return_{h}'}] Estatísticas de Retorno:")
        print(f"→ Long  (compra): {acertos_long}/{total_long} acertos ({pct_acerto_long:.2f}%)")
        print(f"→ Short (venda): {acertos_short}/{total_short} acertos ({pct_acerto_short:.2f}%)")
        print(f"→ Total           {total_acertos}/{total} acertos ({pct_acerto_total:.2f}%)")
        
        print("-" * 60)
        
    return df_result.reset_index()