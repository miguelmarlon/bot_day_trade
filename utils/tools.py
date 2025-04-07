import os
import pandas as pd
from binance.client import Client
import time
from datetime import datetime, timedelta

def create_folder(folder):
    os.makedirs(folder, exist_ok=True)

def calculate_MA(df):
    df['200EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
    return df

def render_result(model, image, result):
    return result.plot()  

def backtest(preds, close, actual, ema):
    return (sum(1 for p, c in zip(preds, actual) if p == 'buy' and c > 0), len(preds))

def append_to_txt(filename, text):
    with open(filename, 'a') as f:
        f.write(text + '\n')

def error_line(e):
    import traceback
    print(f"Erro: {e}")
    traceback.print_exc()

def get_historical_klines(symbol, interval, start_str, end_str=None):
    start_ts = int(pd.to_datetime(start_str).timestamp() * 1000)
    end_ts = int(pd.to_datetime(end_str).timestamp() * 1000) if end_str else int(time.time() * 1000)
    api_key = os.getenv("BINANCE_API_KEY")
    secret_key = os.getenv("BINANCE_SECRET_KEY")
    client = Client(api_key, secret_key)
    all_candles = []

    while start_ts < end_ts:
        candles = client.get_klines(
            symbol=symbol,
            interval=interval,
            startTime=start_ts,
            endTime=end_ts,
            limit=1000
        )

        if not candles:
            break

        all_candles.extend(candles)

        last_time = candles[-1][0]
        start_ts = last_time + 1

        time.sleep(0.5)  # respeita limite da API

    return all_candles