import pandas as pd

def verificar_long_btc_1m(df_candles):
    rsi = df_candles['RSI'].iloc[-1]
    candle_alta = df_candles['close'].iloc[-1] > df_candles['open'].iloc[-1]
    return rsi <= 17 and candle_alta

def verificar_short_btc_1m(df):
    rsi = df['RSI'].iloc[-1]
    candle_baixa = df['close'].iloc[-1] < df['open'].iloc[-1]
    return rsi >= 82 and candle_baixa