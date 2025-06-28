import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import os
import pandas as pd
from scripts.binance_server import BinanceHandler
import asyncio
import ollama
from .technical_analysis import calcular_indicadores
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

async def selecionar_cryptos(limite_moedas=100):
    """
    Roda a coleta de indicadores técnicos para todas as criptos em um DataFrame.
    :param df_criptos: DataFrame com uma coluna 'symbol' contendo os nomes das criptos (ex: BTCUSDT).
    :param intervalo: Intervalo das velas.
    :param limite: Número de candles.
    :return: Dicionário com dados históricos e indicadores para cada cripto.
    """
    handler = None
    try:
        handler = await BinanceHandler.create()
        modelos_ollama = ['falcon3:3b', 'falcon3:7b']
        df_criptos = await handler.get_volume_report(quote_currency='USDT', limit=limite_moedas)

        resultados_finais_notas = []
        for index, row in df_criptos.iterrows():
            symbol = row['symbol']
            try:
            
                df_candles = await handler.obter_dados_candles(symbol=symbol, timeframe='1d', limit=500)
                print(f"Coletando dados para {symbol}...")
                #print(df_candles.tail())
                df_indicadores = calcular_indicadores(df_candles)
                # print(df_indicadores.tail())
                if not df_indicadores.empty:
                    
                    prompt = f"""
                    O ativo {symbol} apresentou os seguintes dados no antepenúltimo candlestick:
                    Abertura: {df_indicadores['abertura'].iloc[-3]}
                    Fechamento: {df_indicadores['fechamento'].iloc[-3]}
                    Máximo: {df_indicadores['max'].iloc[-3]}
                    Mínimo: {df_indicadores['min'].iloc[-3]}
                    Volume: {df_indicadores['volume'].iloc[-3]}

                    Penúltimo candlestick:
                    Abertura: {df_indicadores['abertura'].iloc[-2]}
                    Fechamento: {df_indicadores['fechamento'].iloc[-2]}
                    Máximo: {df_indicadores['max'].iloc[-2]}
                    Mínimo: {df_indicadores['min'].iloc[-2]}
                    Volume: {df_indicadores['volume'].iloc[-2]}

                    Último candlestick:
                    Abertura: {df_indicadores['abertura'].iloc[-1]}
                    Fechamento: {df_indicadores['fechamento'].iloc[-1]}
                    Máximo: {df_indicadores['max'].iloc[-1]}
                    Mínimo: {df_indicadores['min'].iloc[-1]}
                    Volume: {df_indicadores['volume'].iloc[-1]}

                    Apresentou os seguintes indicadores:
                    - RSI: {df_indicadores['RSI'].iloc[-1]}
                    - MACD: {df_indicadores['MACD_12_26_9'].iloc[-1]}
                    - MACD Histórico: {df_indicadores['MACDh_12_26_9'].iloc[-1]}
                    - MACD Signal: {df_indicadores['MACDs_12_26_9'].iloc[-1]}
                    - EMA_20: {df_indicadores['EMA_20'].iloc[-1]}
                    - EMA_50: {df_indicadores['EMA_50'].iloc[-1]}
                    - SMA_50: {df_indicadores['SMA_50'].iloc[-1]}
                    - SMA_200: {df_indicadores['SMA_200'].iloc[-1]}
                    - MFI: {df_indicadores['MFI_14'].iloc[-1]}
                    - ATR: {df_indicadores['ATR'].iloc[-1]}
                    - CCI: {df_indicadores['CCI'].iloc[-1]}
                    - WILLIAMS_R: {df_indicadores['WILLIAMS_R'].iloc[-1]}
                    - Momentum: {df_indicadores['Momentum'].iloc[-1]}
                    - Bollinger Upper: {df_indicadores['BBU'].iloc[-1]}
                    - Bollinger Middle: {df_indicadores['BBM'].iloc[-1]}
                    - Bollinger Lower: {df_indicadores['BBL'].iloc[-1]}
                    - Pivot: {df_indicadores['PP'].iloc[-1]}
                    - Pivot R1: {df_indicadores['R1'].iloc[-1]}
                    - Pivot S1: {df_indicadores['S1'].iloc[-1]}
                    - Pivot R2: {df_indicadores['R2'].iloc[-1]}
                    - Pivot S2: {df_indicadores['S2'].iloc[-1]}
                    - Pivot R3: {df_indicadores['R3'].iloc[-1]}
                    - Pivot S3: {df_indicadores['S3'].iloc[-1]}
                    - Stochastic K: {df_indicadores['STOCHk_14_3_3'].iloc[-1]}
                    - Stochastic D: {df_indicadores['STOCHd_14_3_3'].iloc[-1]}

                    Com base nesses indicadores e no comportamento histórico recente, 
                    avalie a probabilidade de um movimento de alta para o ativo 
                    {symbol} em uma escala de 0 (probabilidade muito baixa) a 100 (probabilidade muito alta).

                    Responda somente e exclusivamente dessa forma:
                    "nota: SUA NOTA"
                    """
                    notas_modelos = {'symbol': symbol}

                    for modelo in modelos_ollama:
                        #"role": "user", 
                        relatorio = ollama.chat(model=modelo, messages=[{"role": "user", "content": prompt}])
                        conteudo = relatorio['message']['content'] 
                        #if isinstance(relatorio, dict) else str(relatorio)
                        
                        print(f'Predicao {modelo} para o ativo: {symbol}')
                        print(f'Conteudo: {conteudo}')
                        

                        nota = parse_llm_score(conteudo)
                        try:
                            nota = float(nota)  # transforma para número, se possível
                        except ValueError:
                            nota = None  # se não for número, guarda como None

                        notas_modelos[modelo] = nota
                        
                        await asyncio.sleep(3)
                    print('#' * 50)
                    notas_validas = [v for k, v in notas_modelos.items() if k != 'symbol' and isinstance(v, (int, float))]
                    notas_modelos['media'] = sum(notas_validas) / len(notas_validas) if notas_validas else None
                    resultados_finais_notas.append(notas_modelos)
            except Exception as e:
                # Se qualquer erro ocorrer para este símbolo, ele será capturado aqui
                print(f"!!!!!!!!!! FALHA AO PROCESSAR O SÍMBOLO {symbol}: {e} !!!!!!!!!!")
                # O 'continue' garante que o loop pulará para o próximo símbolo
                continue
            
        if not resultados_finais_notas:
            print("Nenhum resultado foi gerado.")
            return pd.DataFrame(columns=['symbol'] + modelos_ollama + ['media'])

        df_resultados = pd.DataFrame(resultados_finais_notas)
        
        return df_resultados
    
    except Exception as e:

        print(f"Erro ao coletar dados: {e}")
        
    finally:
        if handler:
            await handler.close_connection()
            print("Conexão com o BinanceHandler fechada.")

async def calcular_tamanho_operacoes(df_sinais, margem_usd, limiar_compra, limiar_venda):
    """
    Calcula o tamanho das operações de compra ou venda para uma lista de ativos.

    :param df_sinais: DataFrame com colunas 'symbol' e 'media'.
    :param exchange: Objeto da corretora CCXT já instanciado.
    :param capital_total_usdt: Seu saldo total em USDT disponível para trading.
    :param percentual_capital_por_operacao: Fração do capital a ser usada em CADA operação de compra (ex: 0.10 para 10%).
    :param limiar_compra: Nota média acima da qual uma compra é considerada.
    :param limiar_venda: Nota média abaixo da qual uma venda é considerada.
    :return: Um DataFrame com os resultados calculados.
    """
    if df_sinais is None or df_sinais.empty:
        print("DataFrame de sinais está vazio ou é nulo. Nenhuma operação será calculada.")
        return pd.DataFrame()
    
    NUMERO_MAX_TENTATIVAS = 3
    
    handler = await BinanceHandler.create()
    resultados = []
    try:

        for index, row in df_sinais.iterrows():
            symbol = row['symbol']
            media = row['media']
            acao = "MANTER"
            quantidade_calculada = 0.0

            print(f"--- Processando {symbol} (Média: {media}) ---")

            if media >= limiar_compra:
                acao = "LONG"
            elif media <= limiar_venda:
                acao = "SHORT"
                
            if acao != "MANTER":
                preco_final = None
                try:
                    for tentativa in range(NUMERO_MAX_TENTATIVAS):
                        ticker = await handler.client.fetch_ticker(symbol)
                        preco_candidato = ticker['ask'] if acao == "LONG" else ticker['bid']
                        if preco_candidato is None:
                            preco_candidato = ticker.get('last')

                        if preco_candidato is not None:
                            preco_final = preco_candidato
                            print(f"Preço obtido com sucesso: {preco_final}")
                            break 
                        
                        # Se falhou, espera antes da próxima tentativa
                        if tentativa < NUMERO_MAX_TENTATIVAS - 1:
                            print("Preço indisponível, esperando para tentar novamente...")
                            await asyncio.sleep(1)

                    if preco_final is None:
                        print(f"Não foi possível obter preço para {symbol} após {NUMERO_MAX_TENTATIVAS} tentativas. Pulando.")
                        acao = "ERRO_PRECO"

                    else:

                        market_rules = handler.client.markets[symbol]
                        min_cost = market_rules['limits']['cost'].get('min', 0)
                        min_amount = market_rules['limits']['amount'].get('min', 0)
                        float(min_cost)  # Garantindo que min_cost seja um float
                        float(min_amount)  # Garantindo que min_amount seja um float
                        print(f"Regras de mercado para {symbol}: Custo mínimo: {min_cost}, Quantidade mínima: {min_amount}")

                        quantidade_calculada = margem_usd / preco_final
                        valor_total = quantidade_calculada * preco_final
                        
                        # Verificações antes de continuar
                        if quantidade_calculada < min_amount:
                            print(f"Quantidade {quantidade_calculada:.8f} menor que mínimo permitido ({min_amount}) para {symbol}. Pulando.")
                            acao = "MARGEM_INSUFICIENTE"
                            quantidade_formatada = None

                        elif valor_total < min_cost:
                            print(f"Valor da ordem ${valor_total:.2f} menor que custo mínimo (${min_cost}) para {symbol}. Pulando.")
                            acao = "MARGEM_INSUFICIENTE"
                            quantidade_formatada = None

                        else:
                            quantidade_formatada = handler.client.amount_to_precision(symbol, quantidade_calculada)
                          
                        if acao in ["LONG", "SHORT"]:
                            resultados.append({
                                'symbol': symbol,
                                'media': media,
                                'acao': acao,
                                'tamanho': float(quantidade_formatada) # Agora é seguro converter para float
                            })
                            print(f"Resultado para {symbol}: Ação={acao}, Tamanho={quantidade_formatada}")
                        else:
                            # Adiciona um registro de falha para análise posterior (opcional, mas recomendado)
                            resultados.append({
                                'symbol': symbol,
                                'media': media,
                                'acao': acao, # Vai registrar "MARGEM_INSUFICIENTE" ou "ERRO_PRECO"
                                'tamanho': 0.0
                            })
                            print(f"Operação para {symbol} não realizada. Motivo: {acao}")
                        
                        await asyncio.sleep(3) 
                
                except Exception as e:
                    print(f"Erro ao calcular tamanho da operação para {symbol}: {e}")
        a=1
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
    

# if __name__ == "__main__":
#     print("Iniciando script de teste do BinanceHandler...")
#     df = asyncio.run(selecionar_cryptos(limite_moedas=150))
#     df_quantidades = asyncio.run(calcular_tamanho_operacoes(df, margem_usd=10, limiar_compra=60, limiar_venda= 40))
#     df_quantidades.to_csv('config/cripto_tamanho_xgb.csv', index=False)
#     df_quantidades.to_csv('config/cripto_tamanho_macd.csv', index=False)