import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import os
from utils import draw_data
from binance_server import BinanceGetTechnicalIndicators
from models.yolo_loader import load_model
import pandas as pd

def run_prediction_binance(symbol=None, interval=None, timeframe_name=None):
    
    fetcher = BinanceGetTechnicalIndicators()
    df = fetcher.get_historical_data(symbol, interval)
    
    if df.empty:
        print(f"Erro func run_prediction_binance: DataFrame vazio!")
        return

    model, device = load_model('./models/best.pt')
    
    draw_data(
        df,
        images_folder="outputs/images",
        model=model,
        device=device,
        tf=timeframe_name,
        symbol=symbol
    )

run_prediction_binance(symbol="BTCUSDT", interval="5m", timeframe_name= "5 minute")

