from xgboost import XGBRegressor
from sklearn.preprocessing import StandardScaler
import numpy as np

def treina_modelo(df_candles):
    df_candles['indice'] = np.arange(len(df_candles))
    features = ['indice', 'RSI', 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9', 'EMA_50', 'EMA_200', 'ATR', 'CCI', 'WILLIAMS_R', 'Momentum']
    x = df_candles[features].values[:-1]
    y = df_candles['close'].values[1:]

    scaler = StandardScaler()
    x_norm = scaler.fit_transform(x)
    model = XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42)
    model.fit(x_norm, y)
    return model, scaler

def predict(df_candles, model, scaler):
    df_candles['indice'] = np.arange(len(df_candles))
    features = ['indice', 'RSI', 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9', 'EMA_50', 'EMA_200', 'ATR', 'CCI', 'WILLIAMS_R', 'Momentum']
    ultimo_candle = df_candles[features].iloc[-1].values.reshape(1, -1)
    ultimo_candle_norm = scaler.transform(ultimo_candle)
    preco_futuro = model.predict(ultimo_candle_norm)[0]
    return preco_futuro