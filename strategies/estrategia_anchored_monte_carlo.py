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

# async def estrategia_anchored_monte_carlo(binance, 
#                                           symbol, 
#                                           timeframe='5m', 
#                                           anchor_date_str = "2025-06-23 21:00:00", 
#                                           lookback_bars = 60,
#                                           simulation_count = 500, 
#                                           forecast_horizon = 30, 
#                                           randomize_direction = True):
#     try:
#         # Coleta de candles
#         limit = 1500
#         timeframe_in_ms = binance.client.parse_timeframe(timeframe) * 1000
#         now = int(time.time() * 1000)  # timestamp atual em milissegundos
#         since = now - (limit * timeframe_in_ms)

#         bars = await binance.client.fetch_ohlcv (symbol=symbol, since=since, timeframe= timeframe, limit=limit)
#         data = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
#         data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
#         data.set_index('timestamp', inplace=True)
#         close_prices = data['close']
        
#         # --- Definir ponto de ancoragem ---
#         anchor_dt = pd.to_datetime(anchor_date_str)
#         historical_data_for_changes = close_prices.loc[anchor_dt:].iloc[:lookback_bars + 1]


#         if len(historical_data_for_changes) < lookback_bars + 1:
#             print(f"Aviso: Dados insuficientes ({len(historical_data_for_changes)} barras) a partir da data de ancoragem para o lookback ({lookback_bars}). Ajustando lookback.")
#             lookback_bars = len(historical_data_for_changes) - 1
#             if lookback_bars <= 0:
#                 print("Dados insuficientes para a simulação após o ajuste. Encerrando.")
#                 return data
#             historical_data_for_changes = close_prices.loc[anchor_dt:].iloc[:lookback_bars + 1]
        
#         # Calcular as mudanças percentuais (retornos) dentro desta janela histórica
#         # Usamos pct_change para obter as "mudanças de preço" mencionadas na LuxAlgo [1]
#         historical_changes = historical_data_for_changes.pct_change().dropna().values
#         current_price = close_prices.iloc[-1]
#         simulated_paths = np.zeros((forecast_horizon, simulation_count))

#         # # --- Simulação Monte Carlo ---
#         # for i in range(simulation_count):
#         #     changes_for_this_simulation = historical_changes.copy()
#         #     if randomize_direction:
#         #         for j in range(len(changes_for_this_simulation)):
#         #             if j % 2!= 0: # Para cada elemento alternado (e.g., 2º, 4º, etc.)
#         #                 changes_for_this_simulation[j] *= -1

#         for i in range(simulation_count):
#             changes_for_this_simulation = historical_changes.copy()
#             if randomize_direction:
#                 changes_for_this_simulation[1::2] *= -1  # Inverte a direção de cada 2º, 4º, etc.


#             # Embaralhar a ordem das mudanças de preço [1]
#             np.random.shuffle(changes_for_this_simulation)

#             # # Projetar os preços futuros para este caminho de simulação
#             # path = np.empty(forecast_horizon)
#             # path[0] = current_price * (1 + changes_for_this_simulation[0])
#             # for t in range(1, forecast_horizon):
#             #     change = changes_for_this_simulation[t % len(changes_for_this_simulation)]
#             #     path[t] = path[t-1] * (1 + change)

#             path = np.zeros(forecast_horizon)
#             path[0] = current_price * (1 + changes_for_this_simulation[0])
#             for t in range(1, forecast_horizon):
#                 change = changes_for_this_simulation[t % len(changes_for_this_simulation)]
#                 path[t] = path[t - 1] * (1 + change)

#             simulated_paths[:, i] = path

#         # --- Cálculo das bandas ---
#         average_line = np.mean(simulated_paths, axis=1)
#         std_dev_at_each_step = np.std(simulated_paths, axis=1)

        # std_dev_multiplier = 1.0 

        # upper_band = average_line + std_dev_multiplier * std_dev_at_each_step
        # lower_band = average_line - std_dev_multiplier * std_dev_at_each_step

    #     upper_band = average_line + std_dev_at_each_step
    #     lower_band = average_line - std_dev_at_each_step

    #     #--- 5. calculando o RSI ---
    #     data['RSI'] = ta.rsi(data['close'], length=14)

    #     # --- Sinal com base no último valor ---
    #     last_rsi = data['RSI'].iloc[-1]
    #     sinal = None

    #     if current_price < lower_band[-1] and 58 <= last_rsi <= 70:
    #             sinal = 1
    #     elif current_price > upper_band[-1] and 30 <= last_rsi <= 42:
    #             sinal = -1

    #         # --- Salvar valores no DataFrame ---
    #     data.loc[data.index[-1], 'upper_band'] = upper_band[-1]
    #     data.loc[data.index[-1], 'lower_band'] = lower_band[-1]
    #     data.loc[data.index[-1], 'sinal'] = sinal if sinal else 0

    #     return data
    # except Exception as e:
    #     print(f"Erro na estratégia Anchored Monte Carlo: {e}")
    #     return None

async def aplicar_monte_carlo_backtest(binance, 
                                          symbol, 
                                          timeframe='5m', 
                                          anchor_date_str = "2025-06-23 21:00:00", 
                                          lookback_bars = 60,
                                          simulation_count = 500, 
                                          forecast_horizon = 30, 
                                          randomize_direction = True):

    # --- 1. Coleta e Preparação de Dados ---
    # Define o limite para a coleta de dados e calcula o 'since' (a partir de quando buscar)
    limit = 1500
    timeframe_in_ms = binance.client.parse_timeframe(timeframe) * 1000
    now = int(time.time() * 1000)  # timestamp atual em milissegundos

    # Ajusta 'since' para garantir que temos dados suficientes para o 'lookback_bars' + 'forecast_horizon'
    # Adicionamos uma margem para ter certeza de que o backtest completo pode ser executado
    required_bars = lookback_bars + forecast_horizon + 100 # Margem extra
    since = now - (required_bars * timeframe_in_ms)

    # Realiza a coleta de candles da Binance
    print(f"Coletando dados para {symbol} no timeframe {timeframe} desde {pd.to_datetime(since, unit='ms')}...")
    bars = await binance.client.fetch_ohlcv(symbol=symbol, since=since, timeframe=timeframe, limit=limit)
    data = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
    data.set_index('timestamp', inplace=True)
    
    # Verifica se há dados suficientes
    if len(data) < lookback_bars + forecast_horizon:
        print(f"Erro: Não há dados suficientes para realizar o backtest. "
              f"Dados coletados: {len(data)}, Mínimo necessário: {lookback_bars + forecast_horizon}")
        return pd.DataFrame() # Retorna um DataFrame vazio se não houver dados suficientes

    # Calcula o RSI
    data['RSI'] = ta.rsi(data['close'], length=14)
    
    # Inicializa colunas para armazenar os resultados do backtest
    data['upper_band_proj'] = np.nan
    data['lower_band_proj'] = np.nan
    data['sinal'] = np.nan

    # --- 2. Loop Principal para Backtest ---
    # Iteramos sobre os dados para aplicar a simulação Monte Carlo em cada ponto
    # Começamos de 'lookback_bars' para garantir que há dados suficientes para a janela
    # e terminamos antes do final para poder projetar 'forecast_horizon' barras no futuro.
    
    # O loop deve ir até 'len(data) - forecast_horizon - 1' para que o último 'i'
    # permita a projeção de 'forecast_horizon' barras à frente.
    
    for i in range(lookback_bars, len(data) - forecast_horizon):
        # Janela de dados históricos para a simulação de Monte Carlo
        # Pegamos 'lookback_bars' de dados ANTES do 'current_price'
        janela = data['close'].iloc[i - lookback_bars : i] # Janela exclui o preço atual
        current_price = data['close'].iloc[i] # O preço a partir do qual a simulação começa

        # Calcula as variações percentuais diárias/do timeframe da janela
        historical_changes = janela.pct_change().dropna().values

        # Verifica se há mudanças históricas para simular
        if len(historical_changes) == 0:
            print(f"Aviso: Não há mudanças históricas suficientes na barra {i}. Pulando esta iteração.")
            continue

        # Array para armazenar os caminhos simulados
        simulated_paths = np.zeros((forecast_horizon, simulation_count))

        # --- 3. Simulação de Monte Carlo ---
        for j in range(simulation_count):
            # Cria uma cópia das mudanças históricas para cada simulação
            changes_for_simulation = historical_changes.copy()
            
            # Embaralha as mudanças para introduzir aleatoriedade
            np.random.shuffle(changes_for_simulation)

            path = np.zeros(forecast_horizon)
            # O primeiro ponto da simulação é baseado no preço atual e na primeira mudança
            path[0] = current_price * (1 + changes_for_simulation[0])
            
            # Gera o restante do caminho simulado
            for t in range(1, forecast_horizon):
                # Aplica as mudanças ciclicamente se 'forecast_horizon' for maior que as 'changes'
                path[t] = path[t - 1] * (1 + changes_for_simulation[t % len(changes_for_simulation)])
            
            simulated_paths[:, j] = path

        # --- 4. Cálculo das Bandas de Projeção e Sinal ---
        # As bandas são calculadas a partir da distribuição dos preços projetados no final do forecast_horizon
        # Isso significa que estamos olhando para o 'forecast_horizon-1' índice (o último ponto no futuro projetado)
        
        # Preços finais de todas as simulações
        final_prices_at_horizon = simulated_paths[forecast_horizon - 1, :] 
        
        # Média e desvio padrão dos preços finais projetados
        avg_final_price = np.mean(final_prices_at_horizon)
        std_final_price = np.std(final_prices_at_horizon)
        
        # Bandas de projeção
        upper_band_proj = avg_final_price + std_final_price
        lower_band_proj = avg_final_price - std_final_price

        # Obtenha o RSI atual para a barra 'i'
        rsi_atual = data['RSI'].iloc[i]
        
        # Lógica para gerar o sinal
        sinal = 0
        # Sinal de compra: preço atual abaixo da banda inferior projetada E RSI em zona de sobrevenda
        if current_price < lower_band_proj: #and 30 <= rsi_atual <= 42: # Condições de RSI ajustadas para compra
            sinal = 1
        # Sinal de venda: preço atual acima da banda superior projetada E RSI em zona de sobrecompra
        elif current_price > upper_band_proj: #and 58 <= rsi_atual <= 70 # Condições de RSI ajustadas para venda
            sinal = -1

        # --- 5. Armazenamento dos Resultados ---
        # Salva os resultados nas colunas correspondentes do DataFrame para a barra 'i'
        data.loc[data.index[i], 'upper_band_proj'] = upper_band_proj
        data.loc[data.index[i], 'lower_band_proj'] = lower_band_proj
        data.loc[data.index[i], 'sinal'] = sinal
        
        # Opcional: imprimir o progresso
        if i % 100 == 0:
            print(f"Processando barra {i}/{len(data) - forecast_horizon - 1}...")

    return data

async def estrategia_anchored_monte_carlo(binance,
                                          symbol, 
                                          timeframe='5m', 
                                          lookback_bars = 60,
                                          simulation_count = 500, 
                                          forecast_horizon = 30, 
                                          randomize_direction = True,
                                          csv = False,): # Este parâmetro será utilizado
    try:
        if csv == True:
            # Primeiro, conta o número total de linhas (inclui o cabeçalho)
            with open('./outputs/btcusd_1min_data.csv') as f:
                total_linhas = sum(1 for _ in f)

            # Calcula quantas linhas pular (menos o cabeçalho)
            linhas_a_pular = total_linhas - 100000
            if linhas_a_pular <= 0:
                linhas_a_pular = 0  # Garante que não pula linhas a mais do que o arquivo tem

            # Lê apenas as últimas 100000 linhas
            data = pd.read_csv('./outputs/btcusd_1min_data.csv', skiprows=range(1, linhas_a_pular))
            data.rename(columns={
                            'Timestamp': 'timestamp',
                            'Open': 'open',
                            'High': 'high',
                            'Low': 'low',
                            'Close': 'close',
                            'Volume': 'volume'
                        }, inplace=True)
        else:
            # --- 1. Coleta e Preparação de Dados ---
            # Define o limite para a coleta de dados e calcula o 'since'
            limit = 1500 # Pode aumentar para ter mais dados para o backtest
            timeframe_in_ms = binance.client.parse_timeframe(timeframe) * 1000
            now = int(time.time() * 1000)  # timestamp atual em milissegundos

            # Ajusta 'since' para garantir dados suficientes para o backtest completo
            required_bars = lookback_bars + forecast_horizon + 100 # Margem extra
            since = now - (required_bars * timeframe_in_ms)

            print(f"Coletando dados para {symbol} no timeframe {timeframe} desde {pd.to_datetime(since, unit='ms')}...")
            bars = await binance.client.fetch_ohlcv(symbol=symbol, since=since, timeframe=timeframe, limit=limit)
            data = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
        data.set_index('timestamp', inplace=True)
        
        # Verifica se há dados suficientes
        if len(data) < lookback_bars + forecast_horizon:
            print(f"Erro: Não há dados suficientes para realizar o backtest. "
                  f"Dados coletados: {len(data)}, Mínimo necessário: {lookback_bars + forecast_horizon}")
            return pd.DataFrame() # Retorna um DataFrame vazio se não houver dados suficientes

        # Calcula o RSI uma única vez para todo o DataFrame
        data['RSI'] = ta.rsi(data['close'], length=14)
        
        # Inicializa colunas para armazenar os resultados do backtest
        data['upper_band_proj'] = np.nan
        data['lower_band_proj'] = np.nan
        data['sinal'] = np.nan
        
        print("Dados coletados e preparados:")
        print(data.tail()) # Mostra as últimas linhas para verificar
        print(f"Total de {len(data)} barras coletadas.")

        # --- 2. Loop Principal para Backtest e Simulação Monte Carlo ---
        # Iteramos sobre os dados para aplicar a simulação Monte Carlo em cada ponto
        # Começamos de 'lookback_bars' para garantir que há dados suficientes para a janela
        # e terminamos antes do final para poder projetar 'forecast_horizon' barras no futuro.
        
        for i in range(lookback_bars, len(data) - forecast_horizon):
            # A "ancoragem" aqui se torna dinâmica, pegando a janela de dados
            # que precede a barra 'i' (o preço atual).
            # historical_data_for_changes é a janela de lookback
            janela_lookback = data['close'].iloc[i - lookback_bars : i] 
            current_price = data['close'].iloc[i] # O preço a partir do qual a simulação começa

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
            rsi_atual = data['RSI'].iloc[i]
            
            # Lógica para gerar o sinal
            sinal = 0 # 0 para neutro
            # Sinal de compra: preço atual abaixo da banda inferior projetada E RSI em zona de sobrevenda
            if current_price < lower_band_proj and 30 <= rsi_atual <= 42:
                sinal = 1 # Compra
            # Sinal de venda: preço atual acima da banda superior projetada E RSI em zona de sobrecompra
            elif current_price > upper_band_proj and 58 <= rsi_atual <= 70:
                sinal = -1 # Venda

            # --- 3. Armazenamento dos Resultados ---
            # Salva os resultados nas colunas correspondentes do DataFrame para a barra 'i'
            data.loc[data.index[i], 'upper_band_proj'] = upper_band_proj
            data.loc[data.index[i], 'lower_band_proj'] = lower_band_proj
            data.loc[data.index[i], 'sinal'] = sinal
            
            # Opcional: imprimir o progresso
            if i % 100 == 0:
                print(f"Processando barra {i}/{len(data) - forecast_horizon - 1}...")

        return data

    except Exception as e:
        print(f"Erro na estratégia Anchored Monte Carlo: {e}")
        return pd.DataFrame() # Retorna um DataFrame vazio em caso de erro

async def main():
    try:
        binance = await BinanceHandler.create()
        df = await estrategia_anchored_monte_carlo(binance=binance, symbol='BTC/USDT', csv=True)
        print(df.tail(20))  # Exibe as últimas linhas do DataFrame para verificar os resultados
        df.to_csv(f'outputs/sinais_monte_carlo.csv', index=False)
        
        if df is not None:
            retorno = calcular_retorno_sinais(df, horizontes=[5, 10, 20, 30])
            retorno.to_csv(f'outputs/calculo_retorno_monte_carlo.csv', index=False)
        else:
            print("Nenhum dado retornado da estratégia Anchored Monte Carlo.")
    except Exception as e:
        print(f"Erro na estratégia Anchored Monte Carlo: {e}")
    finally:
        await binance.close_connection()

if __name__ == "__main__":
    asyncio.run(main())