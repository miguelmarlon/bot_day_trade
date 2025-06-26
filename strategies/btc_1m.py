import pandas as pd

def verificar_long_btc_1m(df_candles):
    rsi = df_candles['RSI'].iloc[-1]
    candle_alta = df_candles['fechamento'].iloc[-1] > df_candles['abertura'].iloc[-1]
    return rsi <= 15 and candle_alta

def verificar_short_btc_1m(df):
    rsi = df['RSI'].iloc[-1]
    candle_baixa = df['fechamento'].iloc[-1] < df['abertura'].iloc[-1]
    return rsi >= 85 and candle_baixa