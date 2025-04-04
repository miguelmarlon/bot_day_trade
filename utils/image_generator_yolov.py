import os
import pandas as pd
import numpy as np
import cv2
from utils.tools import create_folder, calculate_MA, backtest, render_result, append_to_txt, error_line

def draw_data(df, images_folder="outputs/images", model=None, device=None, tf=None, symbol=None):
    try:
        height = 500
        width = 500
        bars = 300
        df = calculate_MA(df) 
        # Normalise high and low
        columns_to_normalize = ['High','Low']
        # Min-Max scaling only on selected columns
        df[columns_to_normalize] = (df[columns_to_normalize] - df[columns_to_normalize].min()) / (df[columns_to_normalize].max() - df[columns_to_normalize].min())
        normalized_high_values = df['High'].values
        normalized_low_values = df['Low'].values
        print("Normalized high ", normalized_high_values[0])
        # Calculate scaling factors for the 'High' and 'Low' values
        scaled_high_values = (normalized_high_values * (height-20)).astype(np.float32)
        scaled_low_values = (normalized_low_values * (height-20)).astype(np.float32)
        # Scale the values to fit within the image height
        scaling_factor = 0.9 # Adjust as needed to fit the graph within the image
        scaled_high_values *= scaling_factor
        scaled_low_values *= scaling_factor
        print("Scaled high values ",scaled_high_values[0])
        start_candle, end_candle = 0, bars
        graph = np.zeros((height, width, 3), dtype=np.uint8)
        graph.fill(255)  # Fill with white
        x = 1 # starting x coordinate
        thickness = 3 # thickness of the lines
        candle_width = 2  # Adjust the candlestick width as needed
        
        prediction, pred_close, actual, EMA_values = [], [], [], []

        for chart_counter in range(1, len(df) - bars):
            graph = np.full((height, width, 3), 255, dtype=np.uint8)  # Fundo branco
            x = 1  # Posição inicial x
        # plot each point 
            for i in range(start_candle,end_candle): 
                # Calculate rectangle coordinates for the high and low values
                high_y1 = height - 20 - int(scaled_high_values[i - 1])
                high_y2 = height - 20 - int(scaled_high_values[i])
                low_y1 = height - 20 - int(scaled_low_values[i - 1])
                low_y2 = height - 20 - int(scaled_low_values[i])
                # Determine the minimum and maximum y-coordinates for the rectangle
                y_min = min(high_y1, high_y2, low_y1, low_y2)
                y_max = max(high_y1, high_y2, low_y1, low_y2)
                # Determine if the candlestick is bullish or bearish
                if df['Open'][i] <  df['Close'][i]:
                    color = (0, 0, 255)  # Bullish (red but using blue)
                else:
                    color = (0, 255, 0)  # Bearish (green)
                # Draw rectangle for the candlestick (in red for high values, green for low values)
                cv2.rectangle(graph, (x - candle_width // 2, y_min), (x + candle_width // 2, y_max), color, thickness) 
                x += 1

            results = model.predict(graph, verbose=False, device=device)
            current_preds = []
            for result in results:
                print("********************************")
                for box in result.boxes:
                    print("********************************")
                    class_id = int(box.data[0][-1])
                    print("Class ",model.names[class_id])
                    current_preds.append(model.names[class_id])
            print(f'The current boxes for this chart are {current_preds} with the last prediction being {current_preds[0]}')

            if chart_counter + bars + 1 < len(df) and current_preds:
                prediction.append(current_preds[0])
                pred_close.append(df['Close'][chart_counter + bars])
                actual.append(df['Close'][chart_counter + bars + 1])
                EMA_values.append(df['200EMA'][chart_counter + bars])

            render = render_result(model=model, image=graph, result=results[0])
            render_np = np.array(render)
           
            render_np = cv2.cvtColor(render_np, cv2.COLOR_RGB2BGR)

            filename = "graph"
            output_path = os.path.join(images_folder, f"graph_{filename}.jpg")
            cv2.imwrite(output_path, render_np)
            start_candle, end_candle = start_candle + 1, end_candle + 1

        win_loss = backtest(prediction, pred_close, actual, EMA_values)
        append_to_txt("outputs/backtest.txt", f"{symbol} {tf} {win_loss[0]} {win_loss[1]}")
    except Exception as e:
        error_line(e)
