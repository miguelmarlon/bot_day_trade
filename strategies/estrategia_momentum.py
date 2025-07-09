import pandas as pd
import numpy as np
from datetime import timedelta

# --- 1. Funções para Cálculo dos Indicadores (Mantêm-se as mesmas) ---

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

# --- 2. Lógica da Estratégia (Mantém-se a mesma) ---

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

# --- 3. Função Principal de Teste (COM AS MUDANÇAS) ---

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

    # Removendo linhas com valores NaN resultantes dos cálculos dos indicadores
    data.dropna(inplace=True)
    if data.empty:
        print("Dados insuficientes após o cálculo dos indicadores. O período dos indicadores pode ser muito longo para os dados disponíveis.")
        return

    print(f"Dados prontos para o backtest. {len(data)} linhas após remoção de NaNs.")

    signals = []
    trades = []
    in_trade = False
    entry_price = 0
    signal_date = None

    print("Iniciando simulação de trades...")
    # Iterar sobre os dados para verificar os sinais
    for i in range(1, len(data)): # Começamos de 1 para ter prev_data_row
        current_row = data.iloc[i]
        previous_row = data.iloc[i-1]

        signal = check_signals(current_row, previous_row, macd_params, rsi_params, bb_params)
        signals.append({'Date': current_row.name, 'Signal': signal})

        # Lógica simples de simulação de trade (sem stop-loss/take-profit por enquanto, apenas entrada/saída)
        if signal == 'BUY' and not in_trade:
            in_trade = True
            entry_price = current_row['Close']
            signal_date = current_row.name
            print(f"Sinal de COMPRA em {signal_date.strftime('%Y-%m-%d %H:%M:%S')} @ {entry_price:.2f}")
            trades.append({'Type': 'BUY', 'Entry_Date': signal_date, 'Entry_Price': entry_price, 'Exit_Date': None, 'Exit_Price': None, 'Profit': None})
        elif signal == 'SELL' and in_trade: # Se estamos em trade de compra e aparece um sinal de venda, fechamos
            in_trade = False
            exit_price = current_row['Close']
            profit = exit_price - entry_price
            print(f"Sinal de VENDA (fechando compra) em {current_row.name.strftime('%Y-%m-%d %H:%M:%S')} @ {exit_price:.2f}. Lucro: {profit:.2f}")
            # Atualiza o último trade aberto
            if trades and trades[-1]['Exit_Date'] is None:
                trades[-1]['Exit_Date'] = current_row.name
                trades[-1]['Exit_Price'] = exit_price
                trades[-1]['Profit'] = profit
            elif trades: # Caso especial: se não há trade aberto mas sinal de venda, pode ser um sinal de short.
                # Aqui simplificamos, apenas fechando long. Para short, precisaríamos de mais lógica.
                pass


    print("\n--- Resultados da Simulação ---")
    trades_df = pd.DataFrame(trades)
    print(trades_df.to_string())

    total_profit = trades_df['Profit'].sum()
    num_trades = len(trades_df)
    winning_trades = trades_df[trades_df['Profit'] > 0]
    num_winning_trades = len(winning_trades)
    if num_trades > 0:
        win_rate = (num_winning_trades / num_trades) * 100
        print(f"\nTotal de Trades: {num_trades}")
        print(f"Trades Vencedores: {num_winning_trades} ({win_rate:.2f}%)")
        print(f"Lucro Total (em pontos/preço): {total_profit:.2f}")
    else:
        print("Nenhum trade executado com base nos sinais gerados.")

    # Opcional: Salvar os dados com os indicadores e sinais para análise posterior
    # data.to_csv('data_with_indicators_and_signals.csv')
    # print("\nDados com indicadores salvos em 'data_with_indicators_and_signals.csv'")


# --- Configurações e Execução ---
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

    # Agora, você só precisa passar o caminho para o seu arquivo CSV de 1 minuto
    # A análise de timeframes múltiplos será feita *dentro* deste mesmo DataFrame.
    CSV_FILE_PATH_1MIN = 'outputs/btc_1min.csv' # Certifique-se de que este é o caminho correto!

    run_backtest(CSV_FILE_PATH_1MIN, MACD_PARAMS, RSI_PARAMS, BB_PARAMS)