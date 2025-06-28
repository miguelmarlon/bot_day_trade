import pandas as pd
import numpy as np
import pandas_ta as ta
from ta.momentum import RSIIndicator

def calculate_period_pivot_points(df: pd.DataFrame):
        """
        Calcula os Pivot Points Clássicos usando os dados do último período (última linha do DataFrame).
        Esta é a abordagem comum para projetar os níveis para o próximo período de negociação.

        Parâmetros:
            df (pd.DataFrame): DataFrame que deve conter as colunas 'High', 'Low', 'Close'.
                               Espera-se que a última linha do DF represente o período a ser usado.

        Retorna:
            dataframe: Um dicionário contendo os valores calculados de PP, R1, R2, R3, S1, S2, S3.
        """
        # Pega os dados do último período (última linha)
        last_period_data = df.iloc[-1]
        
        high_anterior = last_period_data['max']
        low_anterior = last_period_data['min']
        close_anterior = last_period_data['fechamento']

        # Calcula o Ponto Pivô Central
        pp = (high_anterior + low_anterior + close_anterior) / 3

        # Calcula Resistências
        r1 = (2 * pp) - low_anterior
        r2 = pp + (high_anterior - low_anterior)
        r3 = high_anterior + 2 * (pp - low_anterior)

        # Calcula Suportes
        s1 = (2 * pp) - high_anterior
        s2 = pp - (high_anterior - low_anterior)
        s3 = low_anterior - 2 * (high_anterior - pp)
        
        pivot_data = {
            'PP': [pp],
            'R1': [r1],
            'R2': [r2],
            'R3': [r3],
            'S1': [s1],
            'S2': [s2],
            'S3': [s3]
        }
        pivot_df = pd.DataFrame(pivot_data)
        return pivot_df

def calculate_bollinger_bands(data: pd.DataFrame, length=20, std=2)-> pd.DataFrame:
    """Calcula as Bandas de Bollingers."""

    bollinger_bands = ta.bbands(data['fechamento'], length=length, std=std)
    bollinger_bands = bollinger_bands.iloc[:,[0,1,2]]
    bollinger_bands.columns = ['BBL', 'BBM', 'BBU']
    bollinger_bands['largura'] = (bollinger_bands['BBU'] - bollinger_bands['BBL'] / bollinger_bands['BBM'])

    data = pd.concat([data, bollinger_bands], axis=1)

    return data

def calcular_indicadores(df_candles):
    rsi = RSIIndicator(df_candles['fechamento'], window=14)
    df_candles['RSI'] = rsi.rsi()

    macd = df_candles.ta.macd(close='fechamento', fast=12, slow=26, signal=9, append=True)
    
    df_candles['EMA_20'] = ta.ema(df_candles['fechamento'], length=20)
    
    df_candles['EMA_50'] = ta.ema(df_candles['fechamento'], length=50)
    
    df_candles['EMA_200'] = ta.ema(df_candles['fechamento'], length=200)
    
    df_candles['SMA_50'] = ta.sma(df_candles['fechamento'], length=50)

    df_candles['SMA_200'] = ta.sma(df_candles['fechamento'], length=200)
    
    df_candles['ATR'] = ta.atr(df_candles['max'], df_candles['min'], df_candles['fechamento'], length=14)
    
    df_candles['CCI'] = ta.cci(df_candles['max'], df_candles['min'], df_candles['fechamento'], length=20)
    
    df_candles['WILLIAMS_R'] = ta.willr(df_candles['max'], df_candles['min'], df_candles['fechamento'], length=14)
    
    df_candles['Momentum'] = ta.mom(df_candles['fechamento'], length=10)
    
    df_candles.ta.stoch(high=df_candles['max'], low=df_candles['min'], close=df_candles['fechamento'], append=True)
    # df_candles = pd.concat([df_candles, stoch])
    #print(df_candles)

    pivot_levels_df = calculate_period_pivot_points(df_candles)
    for col in pivot_levels_df.columns:
        df_candles[col] = pivot_levels_df[col].iloc[0]
    
    df_candles.ta.mfi(high=df_candles['max'], low=df_candles['min'], close=df_candles['fechamento'], volume=df_candles['volume'], append=True)

    df_candles = calculate_bollinger_bands(df_candles)

    df_candles.bfill(inplace=True)
    df_candles.ffill(inplace=True) 
    df_candles.dropna(inplace=True)
    
    return df_candles

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