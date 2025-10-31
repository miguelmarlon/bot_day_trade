import sys
from pathlib import Path
from xml.sax import handler
sys.path.append(str(Path(__file__).parent.parent))
import os
import pandas as pd
from scripts.binance_server import BinanceHandler
import asyncio
import ollama
# from .technical_analysis import calcular_indicadores
from utils.binance_client import BinanceHandler
import re
import unicodedata
import time

def parse_llm_score(response):
    """Extrai a nota após o termo 'nota:'."""
    texto = unicodedata.normalize('NFKD', response)
    texto = texto.encode('ASCII', 'ignore').decode('utf-8')

    if not texto.strip():
        return "INDEFINIDO"

    texto = texto.lower()

    # Procura exatamente "nota: <número>"
    match = re.search(r'nota:\s*(\d{1,3}(?:\.\d+)?)', texto)
    if match:
        return float(match.group(1))  # ou int(match.group(1)) se preferir

    return "INDEFINIDO"

async def selecionar_cryptos_sem_notas(limite_moedas=100):
    """
    Coleta dados de volume de criptomoedas sem usar modelos de notas.
    :param limite_moedas: Número máximo de criptomoedas a serem coletadas.
    :return: DataFrame com os dados de volume das criptomoedas."""

    handler = None
    try:
        handler = await BinanceHandler.create()
        
        df_criptos = await handler.get_volume_report(quote_currency='USDT', limit=limite_moedas)
        if df_criptos.empty:
            print("Nenhuma criptomoeda encontrada com o volume especificado.")
            return pd.DataFrame(columns=['symbol', 'volume'])
        else:
            return df_criptos
        
        print(f"Coletadas {len(df_criptos)} criptomoedas com os maiores volumes.")
        
    except Exception as e:
        print(f"Erro ao coletar dados: {e}")
        
    finally:
        if handler:
            await handler.close_connection()
            print("Conexão com o BinanceHandler fechada.")
  
async def calcular_tamanho_operacoes_sem_notas(df_sinais):

    if df_sinais is None or df_sinais.empty:
        print("DataFrame de sinais está vazio ou é nulo. Nenhuma operação será calculada.")
        return pd.DataFrame()
    
    NUMERO_MAX_TENTATIVAS = 3
    
    handler = None
    resultados = []
    try:
        handler = await BinanceHandler.create()

        for index, row in df_sinais.iterrows():
            symbol = row['symbol']
            print(f"--- Processando {symbol} ---")

            preco_final = None
            
            try:
                for tentativa in range(NUMERO_MAX_TENTATIVAS):
                    ticker = await handler.client.fetch_ticker(symbol)
                    preco_candidato = ticker.get('last')
                    if preco_candidato is not None:
                        preco_final = preco_candidato
                        print(f"Preço obtido com sucesso: {preco_final}")
                        break  # Sai do loop se o preço foi obtido com sucesso
                    else:
                        if tentativa < NUMERO_MAX_TENTATIVAS - 1:
                            print("Preço indisponível, esperando para tentar novamente...")
                            await asyncio.sleep(2)

                if preco_final is None:
                    print(f"Não foi possível obter preço para {symbol} após {NUMERO_MAX_TENTATIVAS} tentativas. Pulando.")
                    continue
                else:
                    market_rules = handler.client.markets[symbol]
                    min_cost = market_rules['limits']['cost'].get('min', 0)
                    min_amount = market_rules['limits']['amount'].get('min', 0)
                    float(min_cost)  
                    float(min_amount)  
                    print(f"Regras de mercado para {symbol}: Custo mínimo: {min_cost}, Quantidade mínima: {min_amount}")

                    capital = 0
                    if min_cost < 5:
                        capital = 6
                    elif min_cost < 10:
                        capital = 11
                    elif min_cost > 15:
                        capital = 20
                    else: 
                        capital = min_cost * 1.2

                    if capital > 0:
                        valor_moeda = float(preco_final)
                        quantidade = capital / valor_moeda
                        quantidade_formatada = float(handler.client.amount_to_precision(symbol, quantidade))
                        print(f"Capital a investir: {capital}, Quantidade formatada: {quantidade_formatada}")
                    else:
                        print(f"Não foi possível definir o capital para min_cost = {min_cost}. Verifique as condições.")
                        quantidade_formatada = 0
                    if quantidade_formatada is not None and quantidade_formatada > 0:
                        quantidade_final = quantidade_formatada * 5
                        resultados.append({
                            'symbol': symbol,
                            'tamanho': quantidade_final
                        })
                    else:
                        print(f"Operação para {symbol} não realizada.")

                    await asyncio.sleep(3)
                    
            except Exception as e:
                print(f"Erro ao processar {symbol}: {e}")

        df_resultados = pd.DataFrame(resultados)
        df_resultados.to_csv('config/cripto_tamanho_xgb.csv', index=False)
        df_resultados.to_csv('config/cripto_tamanho_macd.csv', index=False)
        return df_resultados
        
    except Exception as e:
        print(f"Erro ao calcular tamanhos de operações: {e}")
        
    finally:
        if handler:
            await handler.close_connection()
            print("Conexão com o BinanceHandler fechada.")

if __name__ == "__main__":
    print("Iniciando script de teste do BinanceHandler...")
    df = asyncio.run(selecionar_cryptos_sem_notas(limite_moedas=150))
    df_quantidades = asyncio.run(calcular_tamanho_operacoes_sem_notas(df))