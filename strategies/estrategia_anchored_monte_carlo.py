import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import numpy as np
import pandas as pd
from utils.binance_client import BinanceHandler
import time
import pandas_ta as ta
import asyncio
from scripts.backtest import calcular_retorno_sinais
from scripts.technical_analysis import calcular_indicadores
from scripts.prediction_model import treina_modelo, predict

async def estrategia_anchored_monte_carlo(binance,
                                          symbol, 
                                          timeframe='15min', 
                                          lookback_bars = 60,
                                          simulation_count = 500, 
                                          forecast_horizon = 30, 
                                          randomize_direction = True,
                                          csv = False): # Este parâmetro será utilizado
    try:
        model = None
        scaler = None

        if csv == True:
            # Primeiro, conta o número total de linhas (inclui o cabeçalho)
            with open(f'./outputs/btc_{timeframe}.csv') as f:
                total_linhas = sum(1 for _ in f)

            # Calcula quantas linhas pular (menos o cabeçalho)
            linhas_a_pular = total_linhas - 200000
            if linhas_a_pular <= 0:
                linhas_a_pular = 0

            data = pd.read_csv(f'./outputs/btc_{timeframe}.csv', skiprows=range(1, linhas_a_pular))
            
            data.rename(columns={
                            'Timestamp': 'timestamp',
                            'Open': 'open',
                            'High': 'high',
                            'Low': 'low',
                            'Close': 'close',
                            'Volume': 'volume'
                        }, inplace=True)
            print(data.head())
        else:
            # --- 1. Coleta e Preparação de Dados ---
            # Define o limite para a coleta de dados e calcula o 'since'
            limit = 1500
            timeframe_in_ms = binance.client.parse_timeframe(timeframe) * 1000
            now = int(time.time() * 1000)  # timestamp atual em milissegundos

            # Ajusta 'since' para garantir dados suficientes para o backtest completo
            required_bars = lookback_bars + forecast_horizon + 100 # Margem extra
            since = now - (required_bars * timeframe_in_ms)

            print(f"Coletando dados para {symbol} no timeframe {timeframe} desde {pd.to_datetime(since, unit='ms')}...")
            bars = await binance.client.fetch_ohlcv(symbol=symbol, since=since, timeframe=timeframe, limit=limit)
            data = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        # Verifica se há dados suficientes
        if len(data) < lookback_bars + forecast_horizon:
            print(f"Erro: Não há dados suficientes para realizar o backtest. "
                  f"Dados coletados: {len(data)}, Mínimo necessário: {lookback_bars + forecast_horizon}")
                  
            return pd.DataFrame()

        # Calcula o RSI uma única vez para todo o DataFrame
        # data['RSI'] = ta.rsi(data['close'], length=14)
        
        data = calcular_indicadores(data)

        train_size = int(len(data) * 0.2) 
        train_data = data.iloc[:train_size].copy()
        backtest_data = data.iloc[train_size:].copy()

        if len(backtest_data) < forecast_horizon + lookback_bars:
            print("Erro: Dados de backtest insuficientes após a divisão para treinamento. Aumente o limite de dados ou ajuste o train_size.")
            return pd.DataFrame()
        
        if model is None or scaler is None:
            print("Treinando o modelo de predição com os dados iniciais...")
            model, scaler = treina_modelo(train_data)

        # Inicializa colunas para armazenar os resultados do backtest
        backtest_data['upper_band_proj'] = np.nan
        backtest_data['lower_band_proj'] = np.nan
        backtest_data['sinal'] = np.nan
        
        if model is None or scaler is None:
            print("Treinando o modelo de predição com os dados iniciais...")
            model, scaler = treina_modelo(train_data)

        for i in range(lookback_bars, len(backtest_data) - forecast_horizon):
            # A "ancoragem" aqui se torna dinâmica, pegando a janela de dados
            # que precede a barra 'i' (o preço atual).
            # historical_data_for_changes é a janela de lookback
            janela_lookback = backtest_data['close'].iloc[i - lookback_bars : i] 
            current_price = backtest_data['close'].iloc[i] # O preço a partir do qual a simulação começa

            # Calcular as mudanças percentuais (retornos) dentro desta janela histórica
            historical_changes = janela_lookback.pct_change().dropna().values

            if len(historical_changes) == 0:
                print(f"Aviso: Não há mudanças históricas suficientes na barra {i} para gerar mudanças. Pulando esta iteração.")
                continue
            
            simulated_paths = np.zeros((forecast_horizon, simulation_count))

            # --- Simulação Monte Carlo ---
            for j in range(simulation_count):
                changes_for_this_simulation = historical_changes.copy()
                
                # Aplica a randomização de direção se o parâmetro for True
                if randomize_direction:
                    # Inverte a direção de cada 2º, 4º, etc., mudança
                    changes_for_this_simulation[1::2] *= -1 
                
                # Embaralhar a ordem das mudanças de preço
                np.random.shuffle(changes_for_this_simulation)

                # Projetar os preços futuros para este caminho de simulação
                path = np.zeros(forecast_horizon)
                if len(changes_for_this_simulation) > 0:
                    # O primeiro ponto da simulação é baseado no preço atual e na primeira mudança aleatória
                    path[0] = current_price * (1 + changes_for_this_simulation[0])
                else:
                    # Se não houver mudanças, o preço se mantém
                    path[0] = current_price

                for t in range(1, forecast_horizon):
                    # Aplica as mudanças ciclicamente
                    change = changes_for_this_simulation[t % len(changes_for_this_simulation)] if len(changes_for_this_simulation) > 0 else 0
                    path[t] = path[t-1] * (1 + change)

                simulated_paths[:, j] = path

            # --- Cálculo das Bandas de Projeção e Sinal ---
            # As bandas são calculadas a partir da distribuição dos preços projetados no final do forecast_horizon
            final_prices_at_horizon = simulated_paths[forecast_horizon - 1, :] 
            
            avg_final_price = np.mean(final_prices_at_horizon)
            std_final_price = np.std(final_prices_at_horizon)
            
            # Bandas de projeção
            upper_band_proj = avg_final_price + std_final_price # Média + 1 desvio padrão
            lower_band_proj = avg_final_price - std_final_price # Média - 1 desvio padrão

            # Obtenha o RSI atual para a barra 'i'
            rsi_atual = backtest_data['RSI'].iloc[i]
            
            data_para_predicao = backtest_data.iloc[[i]].copy()

            sinal = 0 # 0 para neutro
            # Sinal de compra: preço atual abaixo da banda inferior projetada E RSI em zona de sobrevenda
            if current_price < lower_band_proj and 30 <= rsi_atual <= 42:
                preco_predito = predict(data_para_predicao, model=model, scaler=scaler)
                if preco_predito - current_price > 0:
                    sinal = 1 
            # Sinal de venda: preço atual acima da banda superior projetada E RSI em zona de sobrecompra
            elif current_price > upper_band_proj and 58 <= rsi_atual <= 70:
                preco_predito = predict(data_para_predicao, model=model, scaler=scaler)
                if preco_predito - current_price < 0:
                    sinal = -1

            # --- 3. Armazenamento dos Resultados ---
            # Salva os resultados nas colunas correspondentes do DataFrame para a barra 'i'
            backtest_data.loc[backtest_data.index[i], 'upper_band_proj'] = upper_band_proj
            backtest_data.loc[backtest_data.index[i], 'lower_band_proj'] = lower_band_proj
            backtest_data.loc[backtest_data.index[i], 'sinal'] = sinal
            
            # Opcional: imprimir o progresso
            if i % 100 == 0:
                print(f"Processando barra {i}/{len(backtest_data) - forecast_horizon - 1}...")

        return backtest_data

    except Exception as e:
        print(f"Erro na estratégia Anchored Monte Carlo: {e}")
        return pd.DataFrame() # Retorna um DataFrame vazio em caso de erro

async def main():
    timeframe = '30min'
    try:
        binance = await BinanceHandler.create()
        df = await estrategia_anchored_monte_carlo(binance=binance, timeframe=timeframe, symbol='BTC/USDT', csv=True)
        # print(df.tail(20)) 
        df.to_csv(f'outputs/sinais_monte_carlo_{timeframe}_xgb.csv', index=False)
        
        if df is not None:
            retorno = calcular_retorno_sinais(df, horizontes=[5, 10, 20, 30, 60, 120, 240])
            retorno.to_csv(f'outputs/calculo_retorno_monte_carlo_{timeframe}_xgb.csv', index=False)
        else:
            print("Nenhum dado retornado da estratégia Anchored Monte Carlo.")
    except Exception as e:
        print(f"Erro na estratégia Anchored Monte Carlo: {e}")
    finally:
        await binance.close_connection()

if __name__ == "__main__":
    asyncio.run(main())