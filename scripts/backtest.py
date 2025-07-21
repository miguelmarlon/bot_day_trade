import pandas as pd
import numpy as np
import vectorbt as vbt
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

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

# BACKTEST COM VECTORBT
def run_backtest(file_path, macd_params, rsi_params, bb_params):
    print(f"Carregando dados de: {file_path}")
    try:
        with open(file_path, 'r') as f:
            total_linhas = sum(1 for _ in f)

        linhas_a_pular = total_linhas - 200000
        if linhas_a_pular <= 0:
            linhas_a_pular = 0
        else:
            linhas_a_pular += 1

        data = pd.read_csv(file_path, parse_dates=['Timestamp'], skiprows=range(1, linhas_a_pular))

        if linhas_a_pular > 0 and len(data.columns) != 6:
            data.columns = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']

        data['Timestamp'] = pd.to_datetime(data['Timestamp'], unit='s')
        data.set_index('Timestamp', inplace=True)

        required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in data.columns for col in required_columns):
            raise KeyError(f"Uma ou mais das colunas essenciais ({', '.join(required_columns)}) estão faltando no CSV.")
        
        print("Dados carregados com sucesso!")
        print(f"Total de {len(data)} linhas de dados.")

    except FileNotFoundError:
        print(f"Erro: O arquivo '{file_path}' não foi encontrado. Verifique o caminho.")
        return
    except KeyError as e:
        print(f"Erro: {e}. Verifique se 'Timestamp', 'Open', 'High', 'Low', 'Close' e 'Volume' estão presentes e com o nome correto.")
        return
    except Exception as e:
        print(f"Ocorreu um erro ao ler o CSV: {e}")
        return