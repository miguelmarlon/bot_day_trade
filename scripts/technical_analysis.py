import pandas as pd
import numpy as np
import pandas_ta as ta
from ta.momentum import RSIIndicator

def calcular_indicadores(df_candles):
    rsi = RSIIndicator(df_candles['fechamento'], window=14)
    df_candles['RSI'] = rsi.rsi()
    macd = df_candles.ta.macd(close='fechamento', fast=12, slow=26, signal=9, append=True)
    df_candles['EMA_20'] = ta.ema(df_candles['fechamento'], length=20)
    df_candles['EMA_50'] = ta.ema(df_candles['fechamento'], length=50)
    df_candles['EMA_200'] = ta.ema(df_candles['fechamento'], length=200)
    df_candles['ATR'] = ta.atr(df_candles['max'], df_candles['min'], df_candles['fechamento'], length=14)
    df_candles['CCI'] = ta.cci(df_candles['max'], df_candles['min'], df_candles['fechamento'], length=20)
    df_candles['WILLIAMS_R'] = ta.willr(df_candles['max'], df_candles['min'], df_candles['fechamento'], length=14)
    df_candles['Momentum'] = ta.mom(df_candles['fechamento'], length=10)
    df_candles.bfill(inplace=True)  
    df_candles.ffill(inplace=True) 
    df_candles.dropna(inplace=True)
    return df_candles

def verificar_long_btc_1m(df_candles):
    rsi = df_candles['RSI'].iloc[-1]
    candle_alta = df_candles['fechamento'].iloc[-1] > df_candles['abertura'].iloc[-1]
    return rsi <= 15 and candle_alta

def verificar_short_btc_1m(df):
    rsi = df['RSI'].iloc[-1]
    candle_baixa = df['fechamento'].iloc[-1] < df['abertura'].iloc[-1]
    return rsi >= 85 and candle_baixa

def verificar_long(df_candles):
    """Verifica as condições para abrir uma posição LONG"""
    if df_candles.iloc[-1]['RSI'] > 40 and df_candles.iloc[-1]['RSI'] < 75 and df_candles.iloc[-1]['EMA_20'] >= df_candles.iloc[-1]['fechamento']:
        if df_candles.iloc[-1]['MACD_12_26_9'] >= df_candles.iloc[-1]['MACDs_12_26_9'] and df_candles.iloc[-2]['MACD_12_26_9'] <= df_candles.iloc[-2]['MACDs_12_26_9']:
            return True   
    return False
        
def verificar_short(df_candles):
    """Verifica as condições para abrir uma posição SHORT"""
    if df_candles.iloc[-1]['RSI'] < 60 and df_candles.iloc[-1]['RSI'] > 30 and df_candles.iloc[-1]['EMA_20'] <= df_candles.iloc[-1]['fechamento']:
        if df_candles.iloc[-1]['MACD_12_26_9'] <= df_candles.iloc[-1]['MACDs_12_26_9'] and df_candles.iloc[-2]['MACD_12_26_9'] >= df_candles.iloc[-2]['MACDs_12_26_9']:
            return True   
    return False    