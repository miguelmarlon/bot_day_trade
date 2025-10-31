import pandas as pd
import numpy as np
import pandas_ta as ta
from ta.momentum import RSIIndicator
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
        
        high_anterior = last_period_data['high']
        low_anterior = last_period_data['low']
        close_anterior = last_period_data['close']

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

    bollinger_bands = ta.bbands(data['close'], length=length, std=std)
    bollinger_bands = bollinger_bands.iloc[:,[0,1,2]]
    bollinger_bands.columns = ['BBL', 'BBM', 'BBU']
    bollinger_bands['largura'] = (bollinger_bands['BBU'] - bollinger_bands['BBL'] / bollinger_bands['BBM'])

    data = pd.concat([data, bollinger_bands], axis=1)

    return data

def calcular_indicadores(df_candles):
    """
    Calcula os indicadores técnicos de forma robusta para o DataFrame de candles,
    incluindo tratamento de erros e validações.
    Retorna o DataFrame com os indicadores ou None em caso de erro.
    """
    
    if df_candles is None or df_candles.empty:
        logging.warning("Input para 'calcular_indicadores' é nulo ou vazio.")
        return None

    required_cols = ['high', 'low', 'close', 'volume']
    if not all(col in df_candles.columns for col in required_cols):
        logging.error(f"Input não contém as colunas necessárias: {required_cols}")
        return None
    
    # O indicador com maior período é 200, então precisamos de pelo menos 200 linhas.
    LONGEST_PERIOD = 200
    if len(df_candles) < LONGEST_PERIOD:
        logging.warning(f"Dados insuficientes. Necessário: {LONGEST_PERIOD} períodos, "
                        f"Disponível: {len(df_candles)}.")
        return None
    
    try: 
        df = df_candles.copy()
        rsi = RSIIndicator(df_candles['close'], window=14)
        df['RSI'] = rsi.rsi()

        macd = df.ta.macd(close='close', fast=12, slow=26, signal=9, append=True)
        
        df['EMA_20'] = ta.ema(df['close'], length=20)
        
        df['EMA_50'] = ta.ema(df['close'], length=50)
        
        df['EMA_200'] = ta.ema(df['close'], length=200)
        
        df['SMA_50'] = ta.sma(df['close'], length=50)

        df['SMA_200'] = ta.sma(df['close'], length=200)
        
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        df['CCI'] = ta.cci(df['high'], df['low'], df['close'], length=20)
        
        df['WILLIAMS_R'] = ta.willr(df['high'], df['low'], df['close'], length=14)
        
        df['Momentum'] = ta.mom(df['close'], length=10)
        
        df.ta.stoch(high=df['high'], low=df['low'], close=df['close'], append=True)

        pivot_levels_df = calculate_period_pivot_points(df)
        for col in pivot_levels_df.columns:
            df[col] = pivot_levels_df[col].iloc[0]

        df.ta.mfi(high=df['high'], low=df['low'], close=df['close'], volume=df['volume'], append=True)

        df = calculate_bollinger_bands(df)

        df.bfill(inplace=True)
        df.ffill(inplace=True) 
        df.dropna(inplace=True)
        if df.empty:
            logging.warning("DataFrame ficou vazio após o cálculo e limpeza dos indicadores.")
            return None
        
        return df
    except Exception as e:
        
        logging.error(f"Falha inesperada ao calcular indicadores: {e}", exc_info=True)
        
        return None
    
def verificar_long(df_candles):
    """Verifica as condições para abrir uma posição LONG"""
    if df_candles.iloc[-1]['RSI'] > 40 and df_candles.iloc[-1]['RSI'] < 75 and df_candles.iloc[-1]['EMA_20'] >= df_candles.iloc[-1]['close']:
        if df_candles.iloc[-1]['MACD_12_26_9'] >= df_candles.iloc[-1]['MACDs_12_26_9'] and df_candles.iloc[-2]['MACD_12_26_9'] <= df_candles.iloc[-2]['MACDs_12_26_9']:
            return True   
    return False
        
def verificar_short(df_candles):
    """Verifica as condições para abrir uma posição SHORT"""
    if df_candles.iloc[-1]['RSI'] < 60 and df_candles.iloc[-1]['RSI'] > 30 and df_candles.iloc[-1]['EMA_20'] <= df_candles.iloc[-1]['close']:
        if df_candles.iloc[-1]['MACD_12_26_9'] <= df_candles.iloc[-1]['MACDs_12_26_9'] and df_candles.iloc[-2]['MACD_12_26_9'] >= df_candles.iloc[-2]['MACDs_12_26_9']:
            return True   
    return False