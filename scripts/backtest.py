import pandas as pd
import numpy as np

def calcular_retorno_sinais(df: pd.DataFrame, horizontes: list = [5, 10, 20, 30, 50, 60]) -> pd.DataFrame:
    """
    Calcula os retornos futuros para cada sinal (1=compra, -1=short) em múltiplos horizontes.
    
    Parâmetros:
    -----------
    df : pd.DataFrame
        DataFrame com colunas: ['close', 'sinal'] (assumindo timestamp como índice)
    horizontes : list
        Lista de horizontes (em candles) para os quais calcular o retorno futuro.
    
    Retorno:
    --------
    pd.DataFrame com novas colunas 'return_N' contendo os retornos futuros para cada N em horizontes.
    """
    try:
        # Crie uma cópia para evitar modificar o DataFrame original
        df_result = df.copy()
        
        # Garante que 'sinal' é numérico e lida com NaNs (0 para NaNs ou outros valores)
        df_result['sinal'] = pd.to_numeric(df_result['sinal'], errors='coerce').fillna(0)

        for h in horizontes:
            col_name = f'return_{h}'
            
            # Use shift para obter o preço futuro
            # O .shift(-h) desloca os valores 'h' posições para cima,
            # fazendo com que o preço futuro esteja na mesma linha do preço atual.
            preco_futuro = df_result['close'].shift(-h)
            
            # Calcule o retorno percentual
            retorno_bruto = (preco_futuro - df_result['close']) / df_result['close']
            
            # Aplique o sinal:
            # - Se sinal == 1, retorno_final = retorno_bruto
            # - Se sinal == -1, retorno_final = -retorno_bruto
            # - Se sinal == 0 (ou NaN), retorno_final = NaN
            
            # Crie uma série de retornos, aplicando o ajuste para shorts
            retornos_finais = np.where(
                df_result['sinal'] == 1,    # Condição para compra
                retorno_bruto,              # Se compra, use o retorno bruto
                np.where(
                    df_result['sinal'] == -1, # Condição para short
                    -retorno_bruto,           # Se short, inverta o retorno bruto
                    np.nan                    # Se sinal for 0 ou outro valor, use NaN
                )
            )
            
            # Atribua os retornos calculados à nova coluna
            df_result[col_name] = retornos_finais 
            
            # Opcional: Se quiser, pode limpar os retornos onde o sinal não é 1 ou -1
            # (embora o np.where já faça isso ao atribuir NaN para sinal=0)
            # df_result.loc[df_result['sinal'] == 0, col_name] = np.nan

        return df_result
    
    except KeyError as ke:
        print(f"Erro: Coluna essencial faltando no DataFrame. Certifique-se de que 'close' e 'sinal' existam. Detalhes: {ke}")
        return pd.DataFrame() # Retorna um DataFrame vazio em caso de erro de coluna
    except Exception as e:
        print(f"Erro inesperado na função calcular_retorno_sinais: {e}")
        return pd.DataFrame() # Retorna um DataFrame vazio em caso de erro