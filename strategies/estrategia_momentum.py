import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import pandas as pd
import numpy as np
from datetime import timedelta
from scripts.backtest import calcular_retorno_sinais_base_minuto

def calculate_macd(data, fast_period=12, slow_period=26, signal_period=9):
    exp1 = data['Close'].ewm(span=fast_period, adjust=False).mean()
    exp2 = data['Close'].ewm(span=slow_period, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_bollinger_bands(data, period=20, std_dev=2):
    middle_band = data['Close'].rolling(window=period).mean()
    std_dev_val = data['Close'].rolling(window=period).std()
    upper_band = middle_band + (std_dev_val * std_dev)
    lower_band = middle_band - (std_dev_val * std_dev)
    return upper_band, middle_band, lower_band

def check_signals(data_row, prev_data_row, macd_params, rsi_params, bb_params):
    if pd.isna(data_row['MACD_Line']) or prev_data_row is None:
        return 'HOLD'

    macd_buy_signal = (
        data_row['MACD_Line'] > data_row['MACD_Signal'] and
        prev_data_row['MACD_Line'] <= prev_data_row['MACD_Signal'] and
        data_row['MACD_Histogram'] > 0 and
        data_row['MACD_Histogram'] > prev_data_row['MACD_Histogram']
    )
    macd_sell_signal = (
        data_row['MACD_Line'] < data_row['MACD_Signal'] and
        prev_data_row['MACD_Line'] >= prev_data_row['MACD_Signal'] and
        data_row['MACD_Histogram'] < 0 and
        data_row['MACD_Histogram'] < prev_data_row['MACD_Histogram']
    )

    rsi_confirm_buy = (data_row['RSI'] > rsi_params['mid_level'] and data_row['RSI'] < rsi_params['overbought_level'])
    rsi_confirm_sell = (data_row['RSI'] < rsi_params['mid_level'] and data_row['RSI'] > rsi_params['oversold_level'])

    bb_confirm_buy = (
        data_row['Close'] <= data_row['BB_Middle'] or
        (not pd.isna(prev_data_row['BB_Lower']) and prev_data_row['Close'] <= prev_data_row['BB_Lower'] and data_row['Close'] > prev_data_row['BB_Lower'])
    )
    bb_confirm_sell = (
        data_row['Close'] >= data_row['BB_Middle'] or
        (not pd.isna(prev_data_row['BB_Upper']) and prev_data_row['Close'] >= prev_data_row['BB_Upper'] and data_row['Close'] < prev_data_row['BB_Upper'])
    )

    if macd_buy_signal and rsi_confirm_buy and bb_confirm_buy:
        return 'BUY'
    elif macd_sell_signal and rsi_confirm_sell and bb_confirm_sell:
        return 'SELL'
    else:
        return 'HOLD'

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

    # Calculando Indicadores
    print("Calculando indicadores...")
    data['MACD_Line'], data['MACD_Signal'], data['MACD_Histogram'] = calculate_macd(
        data, macd_params['fast_period'], macd_params['slow_period'], macd_params['signal_period']
    )
    data['RSI'] = calculate_rsi(data, rsi_params['period'])
    data['BB_Upper'], data['BB_Middle'], data['BB_Lower'] = calculate_bollinger_bands(
        data, bb_params['period'], bb_params['std_dev']
    )

    # Remove linhas com NaN
    data.dropna(inplace=True)
    if data.empty:
        print("Dados insuficientes após o cálculo dos indicadores.")
        return

    print(f"Dados prontos. {len(data)} linhas após remoção de NaNs.")
    print("Iniciando geração de sinais...")

    sinais = [0]  # primeiro índice não tem dado anterior, assume HOLD
    for i in range(1, len(data)):
        current_row = data.iloc[i]
        previous_row = data.iloc[i - 1]
        signal = check_signals(current_row, previous_row, macd_params, rsi_params, bb_params)

        if signal == 'BUY':
            sinais.append(1)
        elif signal == 'SELL':
            sinais.append(-1)
        else:
            sinais.append(0)

    data['sinal'] = sinais
    df = data[data['sinal'] != 0]
    return df

if __name__ == "__main__":
    MACD_PARAMS = {
        'fast_period': 12, 'slow_period': 26, 'signal_period': 9
    }
    RSI_PARAMS = {
        'period': 14, 'overbought_level': 70, 'oversold_level': 30, 'mid_level': 50
    }
    BB_PARAMS = {
        'period': 20, 'std_dev': 2
    }
    CSV_FILE_PATH_1MIN = 'outputs/btc_1min.csv'
    TIMEFRAMES = ['1min', '5min', '15min', '30min', '60min']

    with open(CSV_FILE_PATH_1MIN, 'r') as f:
        total_linhas = sum(1 for _ in f)

    linhas_a_pular = total_linhas - 300000
    if linhas_a_pular <= 0:
        linhas_a_pular = 0
    else:
        linhas_a_pular += 1

    df_base = pd.read_csv(CSV_FILE_PATH_1MIN, parse_dates=['Timestamp'], skiprows=range(1, linhas_a_pular))
    df_base['Timestamp'] = pd.to_datetime(df_base['Timestamp'], unit='s')
    df_base.set_index('Timestamp', inplace=True)

    for t in TIMEFRAMES:
        csv_path = f'outputs/btc_{t}.csv'
        df_sinais = run_backtest(csv_path, MACD_PARAMS, RSI_PARAMS, BB_PARAMS)

        df_resultado = calcular_retorno_sinais_base_minuto(
            df_sinais=df_sinais,
            df_base=df_base,
            horizontes_minutos=[5, 10, 30, 60, 120, 240]
        )
        if df_resultado is not None:
            output_path = f'outputs/data/analise_momentum/sinais_momentum_{t}.csv'
            df_resultado.to_csv(output_path, index=False)
            print(f"Sinais salvos em: {output_path}")
        else:
            print(f"Nenhum sinal gerado para o timeframe {t}.")
    
    