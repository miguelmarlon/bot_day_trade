import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import os
import pandas as pd
from binance.client import Client
import time
import ast
from datetime import datetime, timedelta
import datetime
import ollama
import re
import unicodedata
import json
import ast
from scripts.binance_server import parse_llm_response, BinanceGetPrice, BinanceGetTechnicalIndicators, BinanceListCryptosByPrice
import pandas as pd

# Quando for criada a classe esse código deve ser inserido dentro dela
LOGS_FOLDER = "logs"
OUTPUTS_FOLDER = "outputs/data/relatorios_rec_com_trades"

# Garante que as pastas existam ao iniciar o script
os.makedirs(LOGS_FOLDER, exist_ok=True)
os.makedirs(OUTPUTS_FOLDER, exist_ok=True)

def create_folder(folder):
    os.makedirs(folder, exist_ok=True)

def calculate_MA(df):
    df['200EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
    return df

def render_result(model, image, result):
    return result.plot()  

def backtest(preds, close, actual, ema):
    return (sum(1 for p, c in zip(preds, actual) if p == 'buy' and c > 0), len(preds))

def append_to_txt(filename, text):
    with open(filename, 'a') as f:
        f.write(text + '\n')

def error_line(e):
    import traceback
    print(f"Erro: {e}")
    traceback.print_exc()

def get_historical_klines(symbol, interval, start_str, end_str=None):
    start_ts = int(pd.to_datetime(start_str).timestamp() * 1000)
    end_ts = int(pd.to_datetime(end_str).timestamp() * 1000) if end_str else int(time.time() * 1000)
    api_key = os.getenv("BINANCE_API_KEY")
    secret_key = os.getenv("BINANCE_SECRET_KEY")
    client = Client(api_key, secret_key)
    all_candles = []

    while start_ts < end_ts:
        candles = client.get_klines(
            symbol=symbol,
            interval=interval,
            startTime=start_ts,
            endTime=end_ts,
            limit=1000
        )

        if not candles:
            break

        all_candles.extend(candles)

        last_time = candles[-1][0]
        start_ts = last_time + 1

        time.sleep(0.5)  # respeita limite da API

    return all_candles

def analisar_predicoes(df, modelos):

    resultados = {}
    for modelo in modelos:

        resultados[modelo] = []

    for i in range(len(df) - 1):
        acertos_compra = 0
        acertos_venda = 0
        erros_compra = 0
        erros_venda = 0
        modelo = df.iloc[i]['modelo']

        if 'predicao_padronizada' in df.columns: #adicionado essa linha.
          decisao = df.iloc[i]['predicao_padronizada']

          if modelo in modelos and decisao in ['COMPRA', 'VENDA']:
              # Verifica a predição na linha seguinte
              valor_atual = df.iloc[i]['preco']
              valor_futuro = df.iloc[i + 1]['preco']

              if decisao == 'COMPRA' and valor_futuro > valor_atual or decisao == 'VENDA' and valor_futuro < valor_atual:
                  predicao_correta = 'ACERTOU'
                  if decisao == 'COMPRA':
                      acertos_compra += 1
                  else:
                      acertos_venda += 1
              else:
                  predicao_correta = 'ERROU'
                  if decisao == 'COMPRA':
                      erros_compra += 1
                  else:
                      erros_venda += 1

              resultados[modelo].append({'predicao': decisao, 'valor_atual':valor_atual, 'valor_futuro': valor_futuro,
                                         'predicao_correta': predicao_correta, 'acertos_compra': acertos_compra,
                                         'acertos_venda': acertos_venda, 'erros_compra': erros_compra,
                                         'erros_venda': erros_venda
                                        })
        else:
            print("Coluna 'predicao_padronizada' não encontrada nesta linha.")

    return resultados

def calculando_lucro_prej_operacao(df_todos_resultados):
    import numpy as np
    # Define o valor investido por operação
    valor_investido = 100

    try:
        # =========================
        # OPERAÇÕES DE COMPRA
        # =========================
        df_compras = df_todos_resultados[df_todos_resultados['predicao'] == 'COMPRA'].copy()
        df_compras['retorno_percentual'] = (df_compras['valor_futuro'] - df_compras['valor_atual']) / df_compras['valor_atual']
        df_compras['lucro_bruto'] = df_compras['retorno_percentual'] * valor_investido
        df_compras['taxa_corretora'] = 0.01
        df_compras['lucro_liquido'] = df_compras['lucro_bruto'] - df_compras['taxa_corretora']
        df_compras['lucro_liquido'] = df_compras['lucro_liquido'].where(df_compras['lucro_bruto'] > 0, 0)
        df_compras['prejuizo_liquido'] = df_compras['lucro_bruto'] - df_compras['taxa_corretora']
        df_compras['prejuizo_liquido'] = df_compras['prejuizo_liquido'].where(df_compras['lucro_bruto'] < 0, 0)
        df_compras['acertos_compra'] = df_compras['retorno_percentual'].apply(lambda x: 1 if x > 0 else 0)
        df_compras['erro_compra'] = df_compras['retorno_percentual'].apply(lambda x: 1 if x <= 0 else 0)

        # =========================
        # OPERAÇÕES DE VENDA
        # =========================
        df_vendas = df_todos_resultados[df_todos_resultados['predicao'] == 'VENDA'].copy()
        df_vendas['retorno_percentual'] = (df_vendas['valor_atual'] - df_vendas['valor_futuro']) / df_vendas['valor_atual']
        df_vendas['acertos_venda'] = np.where(df_vendas['retorno_percentual'] > 0, 1, 0)
        df_vendas['erro_venda'] = np.where(df_vendas['retorno_percentual'] <= 0, 1, 0)

        # =========================
        # AGRUPAMENTO FINAL
        # =========================
        resultado_compras = df_compras.groupby('modelo').agg(
            acertos_compra=('acertos_compra', 'sum'),
            erros_compra=('erro_compra', 'sum'),
            lucro_compras=('lucro_liquido', 'sum'),
            prejuizo_compras=('prejuizo_liquido', 'sum')
        )

        resultado_vendas = df_vendas.groupby('modelo').agg(
            acertos_venda=('acertos_venda', 'sum'),
            erros_venda=('erro_venda', 'sum'), 
        )

        resultado = resultado_compras.join(resultado_vendas, how='outer').fillna(0)
        
        # Resultado total por modelo
        resultado['resultado_total'] = (
            resultado['lucro_compras'] + 
            resultado['prejuizo_compras'] 
        )

        # Porcentagem de acertos
        resultado['%_acerto_compra'] = (
            resultado['acertos_compra'] / 
            (resultado['acertos_compra'] + resultado['erros_compra']).replace(0, np.nan)
        ) * 100

        resultado['%_acerto_venda'] = (
            resultado['acertos_venda'] / 
            (resultado['acertos_venda'] + resultado['erros_venda']).replace(0, np.nan)
        ) * 100

        resultado['%_acerto_compra'] = resultado['%_acerto_compra'].fillna(0)
        resultado['%_acerto_venda'] = resultado['%_acerto_venda'].fillna(0)

        preco_medio = df_todos_resultados['valor_atual'].mean()
        resultado = resultado.reset_index()

        return resultado, preco_medio

    except Exception as e:
        print(f"[ERRO] Falha ao calcular os lucros/prejuízos de compra: {e}")
        return None

def calculando_taxa_acerto_erro(df_todos_resultados, resultado_por_modelo):
    # Calcula taxa de acerto e erro gerais por modelo (com normalização)
    resumo = (
        df_todos_resultados
        .groupby('modelo')['predicao_correta']
        .value_counts(normalize=True)
        .unstack(fill_value=0)
        .reset_index()
        .rename(columns={'ACERTOU': 'taxa_acerto_total (%)', 'ERROU': 'taxa_erro_total (%)'})
    )

    # Adiciona métricas de lucro/prejuízo/resultados/acertos por tipo
    resumo = resumo.merge(
        resultado_por_modelo[
            [
                'modelo', 'lucro_compras', 'prejuizo_compras', 'resultado_total',
                'acertos_compra', 'erros_compra', 'acertos_venda', 'erros_venda',
                '%_acerto_compra', '%_acerto_venda'
            ]
        ],
        on='modelo',
        how='left'
    )
    # Calcula o número total de predições por modelo
    resumo['total_predicoes'] = df_todos_resultados.groupby('modelo').size().values

    # Converte as taxas para porcentagem e trata valores nulos
    resumo['taxa_acerto_total (%)'] = (resumo['taxa_acerto_total (%)'] * 100).round(2)
    resumo['taxa_erro_total (%)'] = (resumo['taxa_erro_total (%)'] * 100).round(2)

    # Garante que não tenha NaNs
    resumo = resumo.fillna({
        'lucro_compras': 0,
        'prejuizo_compras': 0,
        'resultado_total': 0,
        '%_acerto_compra': 0,
        '%_acerto_venda': 0
    })

    return resumo

def criando_relatorio_xlsx(resumo, numero_candles, preco_medio, folder):

    data_atual = datetime.date.today()
    data_atual_formatada = data_atual.strftime("%d-%m-%Y")

    nome_arquivo_excel = f"relatorio_modelos_{data_atual_formatada}.xlsx"
    moeda_avaliada = "INDEFINIDA"
    caminho_completo = os.path.join(folder, nome_arquivo_excel)

    # Cria o arquivo Excel com várias abas
    with pd.ExcelWriter(caminho_completo, engine="xlsxwriter") as writer:
        # Informações gerais em uma planilha separada
        info_geral = pd.DataFrame({
            "Descrição": [
                "Moeda analisada",
                "Preço médio",
                "Total de candles analisados"
            ],
            "Valor": [
                moeda_avaliada,
                preco_medio,
                numero_candles[2]
            ]
        })
        info_geral.to_excel(writer, sheet_name="Resumo Geral", index=False)
        mais_predicoes = resumo.sort_values(by="total_predicoes", ascending=False)
        maior_taxa_acerto = resumo.sort_values(by="taxa_acerto_total (%)", ascending=False)
        maior_lucro = resumo.sort_values(by="lucro_compras", ascending=False)
        maior_prejuizo = resumo.sort_values(by="prejuizo_compras", ascending=True)  # mais negativo = pior
        melhor_acerto_compra = resumo.sort_values(by="%_acerto_compra", ascending=False)
        melhor_acerto_venda = resumo.sort_values(by="%_acerto_venda", ascending=False)
        melhor_resultado = resumo.sort_values(by="resultado_total", ascending=False)

        # Cada aba é uma visão do relatório
        resumo.to_excel(writer, sheet_name="Resumo por modelo", index=False)
        mais_predicoes[["modelo", "total_predicoes"]].to_excel(writer, sheet_name="Mais predições", index=False)
        maior_taxa_acerto[["modelo", "taxa_acerto_total (%)"]].to_excel(writer, sheet_name="Maior acerto (%)", index=False)
        maior_lucro[["modelo", "lucro_compras"]].to_excel(writer, sheet_name="Maior lucro", index=False)
        maior_prejuizo[["modelo", "prejuizo_compras"]].to_excel(writer, sheet_name="Maior prejuízo", index=False)
        melhor_acerto_compra[["modelo", "%_acerto_compra"]].to_excel(writer, sheet_name="Melhor acerto compra", index=False)
        melhor_acerto_venda[["modelo", "%_acerto_venda"]].to_excel(writer, sheet_name="Melhor acerto venda", index=False)
        melhor_resultado[["modelo", "resultado_total"]].to_excel(writer, sheet_name="Ranking final", index=False)

        # Melhor modelo geral
        top_modelo = melhor_resultado.iloc[0]
        melhor_modelo_df = pd.DataFrame([{
            "Melhor modelo geral": top_modelo["modelo"],
            "Resultado total": top_modelo["resultado_total"]
        }])
        melhor_modelo_df.to_excel(writer, sheet_name="Melhor modelo", index=False)

    print(f"Relatório completo salvo em '{nome_arquivo_excel}'")

def simular_trade_compra_com_csv(
    preco_entrada,
    df_candles,
    valor_investido=100,
    stop_loss=0.03,
    stop_gain=0.05,
    taxa_corretagem=0.01,
    usar_trailing_stop=True,
    trailing_percentual=0.02,
    usar_break_even=True,
    break_even_trigger=0.03
    ):
    """
    Simula uma operação de compra a partir de um preço de entrada, considerando valor investido, taxa de corretagem e estratégias de proteção como trailing stop e break-even.

    Esta função percorre candles futuros e verifica se os preços atingem os critérios de stop loss, stop gain, trailing stop ou break-even, encerrando a operação conforme o primeiro gatilho acionado. Caso nenhum seja atingido, a venda ocorre ao final do último candle.

    Args:
        preco_entrada (float): Preço de entrada no trade.
        df_candles (pd.DataFrame): DataFrame com candles subsequentes. Deve conter colunas: 'timestamp', 'high', 'low', 'close'.
        valor_investido (float): Valor em dólares investido na operação (default 100).
        stop_loss (float): Percentual de perda máxima aceitável (default 0.03 = 3%).
        stop_gain (float): Percentual de ganho alvo (default 0.05 = 5%).
        taxa_corretagem (float): Taxa de corretagem aplicada em cada operação (default 0.01 = 1%).
        usar_trailing_stop (bool): Se True, ativa o trailing stop (default True).
        trailing_percentual (float): Percentual do trailing stop abaixo do novo topo (default 0.02 = 2%).
        usar_break_even (bool): Se True, ativa o break-even (default True).
        break_even_trigger (float): Percentual de lucro necessário para mover o stop para o preço de entrada (default 0.03 = 3%).

    Returns:
        tuple: 
            - valor_lucro_prejuizo (float): Lucro ou prejuízo absoluto em dólares.
            - resultado_percentual (float): Retorno percentual da operação.
            - indice_saida (int): Índice do candle onde o trade foi encerrado.
            - duracao (timedelta): Tempo total da operação.
            - resumo (str): String descritiva resumindo a operação.
    """
    
    df_candles['timestamp'] = pd.to_datetime(df_candles['timestamp'])
    
    stop_loss_price = preco_entrada * (1 - stop_loss)
    stop_gain_price = preco_entrada * (1 + stop_gain)
    
    valor_efetivo_compra = valor_investido * (1 - taxa_corretagem)
    quantidade = valor_efetivo_compra / preco_entrada
    timestamp_entrada = df_candles.iloc[0]["timestamp"]
    
    max_price = preco_entrada
    break_even_ativado = False

    print(f"\n🟢 INICIANDO OPERAÇÃO DE COMPRA")
    print(f"Preço de entrada: {preco_entrada:.8f}")
    print(f"Stop Loss inicial: {stop_loss_price:.8f}")
    print(f"Stop Gain: {stop_gain_price:.8f}")
    print(f"Trailing ativo: {usar_trailing_stop} | Break-even ativo: {usar_break_even}")

    for i, (_, row) in enumerate(df_candles.iterrows()):
        timestamp_atual = row["timestamp"]
        high = row["high"]
        low = row["low"]

        # Trailing stop: atualiza stop loss baseado no high
        if usar_trailing_stop:
            if high > max_price:
                max_price = high
                novo_stop = max_price * (1 - trailing_percentual)
                if novo_stop > stop_loss_price:
                    print(f"🔁 Atualizando trailing stop: {stop_loss_price:.8f} -> {novo_stop:.8f}")
                    stop_loss_price = novo_stop

        # Break-even: move stop para entrada após atingir lucro mínimo
        if usar_break_even and not break_even_ativado:
            if high >= preco_entrada * (1 + break_even_trigger):
                stop_loss_price = preco_entrada
                break_even_ativado = True
                print(f"⚖️ Break-even ativado! Novo stop: {stop_loss_price:.8f}")

        # Stop loss atingido
        if low <= stop_loss_price:
            preco_venda = stop_loss_price * (1 - taxa_corretagem)
            lucro_prejuizo = quantidade * (preco_venda - preco_entrada)
            tempo_operacao = timestamp_atual - timestamp_entrada
            print(f"🔴 Stop Loss atingido em {stop_loss_price:.8f} | Venda por {preco_venda:.8f}")
            resumo = f"Stop Loss acionado em {timestamp_atual}, após {tempo_operacao}. Preço de venda: {preco_venda:.8f}."
            return lucro_prejuizo, lucro_prejuizo / valor_investido, row.name, tempo_operacao, resumo

        # Stop gain atingido
        if high >= stop_gain_price:
            preco_venda = stop_gain_price * (1 - taxa_corretagem)
            lucro_prejuizo = quantidade * (preco_venda - preco_entrada)
            tempo_operacao = timestamp_atual - timestamp_entrada
            print(f"🟢 Stop Gain atingido em {stop_gain_price:.8f} | Venda por {preco_venda:.8f}")
            resumo = f"Stop Gain acionado em {timestamp_atual}, após {tempo_operacao}. Preço de venda: {preco_venda:.8f}."
            return lucro_prejuizo, lucro_prejuizo / valor_investido, row.name, tempo_operacao, resumo

    # Nenhum stop atingido: vende no fechamento do último candle
    ultimo_preco = df_candles.iloc[-1]["close"]
    preco_venda = ultimo_preco * (1 - taxa_corretagem)
    lucro_prejuizo = quantidade * (preco_venda - preco_entrada)
    resultado_percentual = (preco_venda - preco_entrada) / preco_entrada
    tempo_operacao = df_candles.iloc[-1]["timestamp"] - timestamp_entrada
    print(f"⚪ Operação encerrada no fechamento ({ultimo_preco:.8f}) sem atingir stop.")
    resumo = f"Trade encerrado no fechamento final em {df_candles.iloc[-1]['timestamp']}, após {tempo_operacao}. Preço de venda: {preco_venda:.8f}."
    
    return lucro_prejuizo, resultado_percentual, df_candles.iloc[-1].name, tempo_operacao, resumo

def simular_trade_compra(
    preco_entrada,
    df_candles,
    valor_investido=100,
    stop_loss=0.03,
    stop_gain=0.05,
    taxa_corretagem=0.01,
    usar_trailing_stop=False,
    trailing_percentual=0.02,
    usar_break_even=False,
    break_even_trigger=0.03
    ):
    stop_gain_price = preco_entrada * (1 + stop_gain)
    stop_loss_price = preco_entrada * (1 - stop_loss)
    preco_entrada_com_corretagem = preco_entrada * (1 + taxa_corretagem)

    trailing_ativado = False
    max_price = preco_entrada

    break_even_ativado = False
    df_candles['timestamp'] = pd.to_datetime(df_candles['timestamp'])
    
    for i, row in df_candles.iterrows():
        high = row["high"]
        low = row["low"]

        # Break even: se atingiu trigger, mova stop para o preço de entrada + taxa
        if usar_break_even and not break_even_ativado and high >= preco_entrada * (1 + break_even_trigger):
            stop_loss_price = preco_entrada_com_corretagem
            break_even_ativado = True

        # Trailing stop: ativa somente se o preço estiver acima da entrada + corretagem
        if usar_trailing_stop:
            if high > preco_entrada_com_corretagem and not trailing_ativado:
                trailing_ativado = True
                # print(f"📈 Trailing stop ativado! Preço ultrapassou a entrada + corretagem ({preco_entrada_com_corretagem:.8f})")

            if trailing_ativado and high > max_price:
                max_price = high
                novo_stop = max_price * (1 - trailing_percentual)
                if novo_stop > stop_loss_price:
                    # print(f"🔁 Atualizando trailing stop: {stop_loss_price:.8f} -> {novo_stop:.8f}")
                    stop_loss_price = novo_stop

        # Stop Gain
        if high >= stop_gain_price:
            preco_saida = stop_gain_price
            break

        # Stop Loss
        if low <= stop_loss_price:
            preco_saida = stop_loss_price
            break
    else:
        # Caso nenhum dos dois alvos tenha sido atingido
        preco_saida = df_candles.iloc[-1]["close"]
        i = df_candles.index[-1]

    # Cálculo do lucro
    preco_entrada_total = preco_entrada * (1 + taxa_corretagem)
    preco_saida_total = preco_saida * (1 - taxa_corretagem)
    retorno_pct = (preco_saida_total - preco_entrada_total) / preco_entrada_total
    lucro = valor_investido * retorno_pct

    timestamp_entrada = df_candles.iloc[0]["timestamp"]
    timestamp_saida = row["timestamp"]
    tempo_operacao = timestamp_saida - timestamp_entrada
    tempo_em_minutos = tempo_operacao.total_seconds() / 60

    resumo = "gain" if preco_saida >= stop_gain_price else "loss" if preco_saida <= stop_loss_price else "neutro"

    return lucro, retorno_pct, i, tempo_em_minutos, resumo

def gerando_predição_tempo_real(cripto, interval,  modelo = None, limite = 500):
    """
    Função para gerar predições com o modelo de linguagem.
    """
    def acertar_linhas(linhas):
        if isinstance(linhas, (pd.Series, list)):
            linhas = [x for x in linhas if x is not None and not pd.isna(x)]
            ultima_linha = linhas[-1] if linhas else 'N/A'
        else:
            ultima_linha = linhas if pd.notna(linhas) else 'N/A'
        return ultima_linha
    
    tool_indicator = BinanceGetTechnicalIndicators()
    
    # Verifica se o conteúdo retornado é uma string (erro)
    MAX_TENTATIVAS = 5  
    tentativas = 0
    while tentativas < MAX_TENTATIVAS:
        content, df_historico = tool_indicator.get_technical_indicators(asset=cripto, interval=interval, limit=limite)

        if isinstance(df_historico, str):
            print(f"Erro ao obter dados (tentativa {tentativas + 1}/{MAX_TENTATIVAS}): {df_historico}")
            print("Aguardando 30 segundos para tentar novamente...")
            time.sleep(30)
            tentativas += 1
        else:
            # Processamento normal se df_historico for um DataFrame
            df_historico['Open_time'] = pd.to_datetime(df_historico['Open time'], unit='ms')
            df_historico['Close_time'] = pd.to_datetime(df_historico['Close time'], unit='ms')
            print("Dados processados com sucesso!")
            break  # Sai do loop se os dados forem obtidos com sucesso
    else:
        print("Não foi possível obter os dados após várias tentativas.")

    df_historico['Open_time'] = pd.to_datetime(df_historico['Open time'], unit='ms')
    df_historico['Close_time'] = pd.to_datetime(df_historico['Close time'], unit='ms')

    #ultimo candle
    ultimo_candle = df_historico.iloc[-1]
    ultimo_open_ = ultimo_candle['Open']
    ultimo_high = ultimo_candle['High']
    ultimo_low = ultimo_candle['Low']
    ultimo_close = ultimo_candle['Close']
    ultimo_volume = ultimo_candle['Volume']
    ultimo_dia = ultimo_candle['Close_time'].strftime("%Y-%m-%d %H:%M:%S")
    
    # Pegando o penúltimo candle
    penultimo_candle = df_historico.iloc[-2]
    penultimo_open_ = penultimo_candle['Open']
    penultimo_high = penultimo_candle['High']
    penultimo_low = penultimo_candle['Low']
    penultimo_close = penultimo_candle['Close']
    penultimo_volume = penultimo_candle['Volume']

    # Pegando o antepenúltimo candle
    antepenultimo_candle = df_historico.iloc[-3]
    antepenultimo_open_ = antepenultimo_candle['Open']
    antepenultimo_high = antepenultimo_candle['High']
    antepenultimo_low = antepenultimo_candle['Low']
    antepenultimo_close = antepenultimo_candle['Close']
    antepenultimo_volume = antepenultimo_candle['Volume']

    #for data in content.items():
        # Pegando os indicadores
    rsi = content['data']['indicators'].get('rsi', 'N/A')
    if rsi is not None:
        ultimo_valor_rsi = acertar_linhas(rsi)
    else:
        ultimo_valor_rsi = 'N/A'

    sma_50 = content['data']['indicators'].get('sma_50', 'N/A')
    if sma_50 is not None:
        ultimo_valor_sma_50 = acertar_linhas(sma_50)
    else:
        ultimo_valor_sma_50 = 'N/A'

    sma_200 = content['data']['indicators'].get('sma_200', 'N/A')
    if sma_200 is not None:
        ultimo_valor_sma_200 = acertar_linhas(sma_200)
    else:
        ultimo_valor_sma_200 = 'N/A'

    ema_20 = content['data']['indicators'].get('ema_20', 'N/A')
    if ema_20 is not None:
        ultimo_valor_ema_20 = acertar_linhas(ema_20)
    else:
        ultimo_valor_ema_20 = 'N/A'

    ema_50 = content['data']['indicators'].get('ema_50', 'N/A')
    if ema_50 is not None:
        ultimo_valor_ema_50 = acertar_linhas(ema_50)
    else:
        ultimo_valor_ema_50 = 'N/A'

    adx = content['data']['indicators'].get('adx', 'N/A')
    if adx is not None:
        ultimo_valor_adx = acertar_linhas(adx)
    else:   
        ultimo_valor_adx = 'N/A'

    mfi = content['data']['indicators'].get('mfi', 'N/A')
    if mfi is not None:
        ultimo_valor_mfi = acertar_linhas(mfi)
    else:
        ultimo_valor_mfi = 'N/A'

    macd = content['data']['indicators'].get('macd', 'N/A')
    if macd is not None:
        ultimo_valor_macd_line = acertar_linhas(macd['macd_line'])
        ultimo_valor_macd_signal = acertar_linhas(macd['signal_line'])
        ultimo_valor_macd_histogram = acertar_linhas(macd['histogram'])
    else:
        ultimo_valor_macd_line = 'N/A'
        ultimo_valor_macd_signal = 'N/A'
        ultimo_valor_macd_histogram = 'N/A'

    bollinger = content['data']['indicators'].get('bollinger_bands', 'N/A')
    if bollinger is not None:
        ultimo_valor_bollinger_upper = acertar_linhas(bollinger['upper_band'])
        ultimo_valor_bollinger_middle = acertar_linhas(bollinger['middle_band'])
        ultimo_valor_bollinger_lower = acertar_linhas(bollinger['lower_band'])
    else:
        ultimo_valor_bollinger_upper = 'N/A'
        ultimo_valor_bollinger_middle = 'N/A'
        ultimo_valor_bollinger_lower = 'N/A'

    pivot = content['data']['indicators'].get('pivot_points', 'N/A')
    if pivot is not None:
        ultimo_valor_pivot = acertar_linhas(pivot['pivot'])
        ultimo_valor_pivot_r1 = acertar_linhas(pivot['r1'])
        ultimo_valor_pivot_s1 = acertar_linhas(pivot['s1'])
        ultimo_valor_pivot_r2 = acertar_linhas(pivot['r2'])
        ultimo_valor_pivot_s2 = acertar_linhas(pivot['s2'])
        ultimo_valor_pivot_r3 = acertar_linhas(pivot['r3'])
        ultimo_valor_pivot_s3 = acertar_linhas(pivot['s3'])
    else:
        ultimo_valor_pivot = 'N/A'
        ultimo_valor_pivot_r1 = 'N/A'
        ultimo_valor_pivot_s1 = 'N/A'
        ultimo_valor_pivot_r2 = 'N/A'
        ultimo_valor_pivot_s2 = 'N/A'
        ultimo_valor_pivot_r3 = 'N/A'
        ultimo_valor_pivot_s3 = 'N/A'
    
    stochastic = content['data']['indicators'].get('stochastic', 'N/A')
    if stochastic is not None:
        ultimo_valor_stochastic_k = acertar_linhas(stochastic['stochastic_k'])
        ultimo_valor_stochastic_d = acertar_linhas(stochastic['stochastic_d'])
    else:
        ultimo_valor_stochastic_k = 'N/A'
        ultimo_valor_stochastic_d = 'N/A'
    # tool_price = BinanceGetPrice()
    # price = tool_price._run(cripto)

    # preco_dict = ast.literal_eval(price.split(": ", 1)[1])
    # preco_float = float(preco_dict["price"])

    prompt_gerador_relatorio = f"""
                    Com base nesses dados fornecidos a seguir, crie uma recomendação de compra, venda ou manter possição para esse ativo:
                    Antepenúltimo candlestick
                    - Opening: {antepenultimo_open_}
                    - Maximum: {antepenultimo_high}
                    - Minimum: {antepenultimo_low}
                    - Closing: {antepenultimo_close}
                    - Volume: {antepenultimo_volume}
                    Penúltimo candlestick
                    - Opening: {penultimo_open_}
                    - Maximum: {penultimo_high}
                    - Minimum: {penultimo_low}
                    - Closing: {penultimo_close}
                    - Volume: {penultimo_volume}
                    Último candlestick
                    - Opening: {ultimo_open_}
                    - Maximum: {ultimo_high}
                    - Minimum: {ultimo_low}
                    - Closing: {ultimo_close}
                    - Volume: {ultimo_volume}
                    Technical indicators
                    - SMA(50): {ultimo_valor_sma_50}
                    - SMA(200): {ultimo_valor_sma_200}
                    - EMA(20): {ultimo_valor_ema_20}
                    - EMA(50): {ultimo_valor_ema_50}
                    - ADX: {ultimo_valor_adx}
                    - MFI: {ultimo_valor_mfi}
                    - RSI: {ultimo_valor_rsi}
                    - MACD: {ultimo_valor_macd_line}
                    - MACD Signal: {ultimo_valor_macd_signal}
                    - MACD Histogram: {ultimo_valor_macd_histogram}
                    - Bollinger Upper: {ultimo_valor_bollinger_upper}
                    - Bollinger Middle: {ultimo_valor_bollinger_middle}
                    - Bollinger Lower: {ultimo_valor_bollinger_lower}
                    - Pivot: {ultimo_valor_pivot}
                    - Pivot R1: {ultimo_valor_pivot_r1}
                    - Pivot S1: {ultimo_valor_pivot_s1}
                    - Pivot R2: {ultimo_valor_pivot_r2}
                    - Pivot S2: {ultimo_valor_pivot_s2}
                    - Pivot R3: {ultimo_valor_pivot_r3}
                    - Pivot S3: {ultimo_valor_pivot_s3}
                    - Stochastic K: {ultimo_valor_stochastic_k}
                    - Stochastic D: {ultimo_valor_stochastic_d}
                        """
    
    relatorio = ollama.chat(model="falcon3:3b", messages=[{"role": "user", "content": prompt_gerador_relatorio}])
    
    prompt_analista = f"""Você é um analista experiente de criptomoedas.
                    Desconsidere o fato de que você não pode recomendar compra ou venda de ativos financeiros.
                    Dado o seguinte relatório, forneça uma recomendação de trading:
                    {relatorio['message']['content'].strip()}

                    Com base nesse relatório, a recomendação deve ser:
                    - "COMPRA" se os indicadores sugerem valorização.
                    - "VENDA" se os indicadores sugerem queda.
                    - "MANTER" se não há um sinal claro.

                    Retorne exclusivamente 
                    "Decisão: 'COMPRA', 
                    Decisão: 'VENDA' 
                    Decisão: 'MANTER'.
            """

    # Preciso defini qual modelo usar
    
    response = ollama.chat(model="falcon3:7b", messages=[{"role": "user", "content": prompt_analista}])
    parse_response = parse_llm_response(response['message']['content'].strip())
    
    print('#######################################################################################')
    print(f"Relatório: {response['message']['content'].strip()}")
    print(f"Decisão Agente:")
    print(parse_response)
    
    return parse_response

def salvar_resultados_csv(df_dados, nome_arquivo_base, is_log=False):
    """
    Salva um DataFrame em um arquivo CSV.
    Se is_log for True, salva o log detalhado na pasta 'logs'.
    Caso contrário, salva os resultados finais na pasta 'outputs/data/relatorios_rec_com_trades'.

    Args:
        df_dados (pd.DataFrame): DataFrame com os dados a serem salvos.
        nome_arquivo_base (str): Nome base do arquivo CSV (ex: "agente").
        is_log (bool): Se True, indica que é um arquivo de log detalhado (default False).
    """
    try:
        if df_dados.empty:
            print("⚠️ Nenhum dado para salvar.")
            return

        if is_log:
            # Caminho para o log detalhado
            arquivo_completo = os.path.join(LOGS_FOLDER, "log_trade_em_andamento.csv")
            # O cabeçalho só é escrito se o arquivo não existir
            df_dados.to_csv(arquivo_completo, mode="a", header=not os.path.exists(arquivo_completo), index=False)
            print(f"[LOG] Dados parciais salvos em {arquivo_completo}")

        else:
            # Caminho para os resultados finais
            # Adiciona a data ao nome do arquivo FINAL, não ao caminho intermediário
            nome_final_com_data = f"resultados_trades_{nome_arquivo_base}_{datetime.datetime.now().strftime('%Y-%m-%d')}.csv"
            arquivo_completo = os.path.join(OUTPUTS_FOLDER, nome_final_com_data)
            
            df_para_salvar = df_dados.copy() # Cria uma cópia para evitar SettingWithCopyWarning

            # Se o arquivo de resultados finais já existir, concatena e remove duplicatas
            if os.path.exists(arquivo_completo):
                try:
                    df_existente = pd.read_csv(arquivo_completo)
                    # Concatena e remove duplicatas. Ajuste 'subset' se 'trade_id' for a chave principal única
                    # Assumindo que 'trade_id' é a chave para evitar duplicatas em resultados finais
                    if 'trade_id' in df_para_salvar.columns and 'trade_id' in df_existente.columns:
                        df_completo = pd.concat([df_existente, df_para_salvar], ignore_index=True)
                        df_completo.drop_duplicates(subset=['trade_id'], keep='last', inplace=True)
                    else:
                        # Fallback se 'trade_id' não estiver presente, use as colunas existentes para duplicatas
                        # Se você tem uma chave única diferente, ajuste aqui.
                        # Do contrário, a lógica original do subset de colunas pode ser usada, mas é mais propenso a erros.
                        print("Atenção: 'trade_id' não encontrado para desduplicar resultados finais. Usando concat simples.")
                        df_completo = pd.concat([df_existente, df_para_salvar], ignore_index=True)
                except pd.errors.EmptyDataError:
                    df_completo = df_para_salvar # Arquivo existia mas estava vazio
                except Exception as e:
                    print(f"Erro ao ler CSV existente {arquivo_completo}: {e}. Salvando apenas os novos dados.")
                    df_completo = df_para_salvar
            else:
                df_completo = df_para_salvar

            # Salva o DataFrame final
            df_completo.to_csv(arquivo_completo, index=False)
            print(f"✅ Resultados salvos em {arquivo_completo}")

    except PermissionError as pe:
        print(f"❌ Erro de permissão ao salvar o arquivo: {pe}")
    except FileNotFoundError as fnfe:
        print(f"❌ Diretório não encontrado: {fnfe}. Verifique a criação das pastas.")
    except pd.errors.ParserError as pe:
        print(f"❌ Erro ao ler CSV existente: {pe}")
    except Exception as e:
        print(f"❌ Erro desconhecido ao salvar os dados: {e}")

def salvar_estado_trade_principal(trade_info, nome_arquivo="trades_principais_em_andamento.json"):
    """
    Salva o estado atual de um trade principal em um arquivo JSON.
    Este arquivo contém um mapeamento de trade_id para o estado atual do trade.
    """
    # --- Configuração da Pasta de Logs ---
    LOGS_FOLDER = "logs"
    # Cria a pasta de logs se ela não existir
    os.makedirs(LOGS_FOLDER, exist_ok=True)
    caminho_completo_arquivo = os.path.join(LOGS_FOLDER, nome_arquivo)

    trades_ativos = {}
    if os.path.exists(caminho_completo_arquivo):
        try:
            with open(caminho_completo_arquivo, 'r') as f:
                trades_ativos = json.load(f)
        except json.JSONDecodeError:
            print(f"Erro ao ler {caminho_completo_arquivo}. Criando um novo arquivo.")
            trades_ativos = {}
    
    if 'trade_id' in trade_info:
        trades_ativos[trade_info['trade_id']] = trade_info
    else:
        print("Atenção: trade_info sem 'trade_id'. Não foi possível salvar.")
        return

    # Usar default=str para serializar objetos datetime e timedelta
    with open(caminho_completo_arquivo, 'w') as f:
        json.dump(trades_ativos, f, indent=4, default=str) 
    
    print(f"Estado do trade principal (ID: {trade_info.get('trade_id', 'N/A')}) salvo em {nome_arquivo}.")

def simular_compra_tempo_real(cripto, 
                                preco_entrada,
                                trade_id,
                                valor_investido=100,
                                stop_loss=0.03,
                                stop_gain=0.05,
                                taxa_corretagem=0.01,
                                usar_trailing_stop=True,
                                trailing_percentual=0.02,
                                usar_break_even=True,
                                break_even_trigger=0.03,
                                get_preco_atual=None,
                                verbose=True):
    """
    Simula uma operação de compra a partir de um preço de entrada, considerando valor investido, taxa de corretagem e estratégias de proteção como trailing stop e break-even.

    Esta função verifica o valor do ativo a cada minuto e verifica se os preços atingem os critérios de stop loss, stop gain, trailing stop ou break-even, encerrando a operação conforme o primeiro gatilho acionado.
    
    Args:
        preco_entrada (float): Preço de entrada no trade.
        valor_investido (float): Valor em dólares investido na operação (default 100).
        stop_loss (float): Percentual de perda máxima aceitável (default 0.03 = 3%).
        stop_gain (float): Percentual de ganho alvo (default 0.05 = 5%).
        taxa_corretagem (float): Taxa de corretagem aplicada em cada operação (default 0.01 = 1%).
        usar_trailing_stop (bool): Se True, ativa o trailing stop (default True).
        trailing_percentual (float): Percentual do trailing stop abaixo do novo topo (default 0.02 = 2%).
        usar_break_even (bool): Se True, ativa o break-even (default True).
        break_even_trigger (float): Percentual de lucro necessário para mover o stop para o preço de entrada (default 0.03 = 3%).

    Returns:
        tuple: 
            - valor_lucro_prejuizo (float): Lucro ou prejuízo absoluto em dólares.
            - resultado_percentual (float): Retorno percentual da operação.
            - indice_saida (int): Índice do candle onde o trade foi encerrado.
            - duracao (timedelta): Tempo total da operação.
            - resumo (str): String descritiva resumindo a operação.
    """

    quantidade = valor_investido / preco_entrada
    preco_stop = preco_entrada * (1 - stop_loss)
    preco_alvo = preco_entrada * (1 + stop_gain)
    trailing_topo = preco_entrada
    preco_break_even = preco_entrada
    atingiu_break_even = False

    inicio_operacao = datetime.datetime.now()
    indice_minuto = 0
    
    historico_trade = []
    ultimo_salvamento = datetime.datetime.now()
    intervalo_salvamento = 600

    if verbose:
        print(f"[{inicio_operacao}] Início da operação.")
        print(f"Preço de entrada: {preco_entrada:.8f}")
        print(f"Alvo: {preco_alvo:.8f}, Stop loss: {preco_stop:.8f}")
        print(f"Trailing ativo: {usar_trailing_stop}, Break-even ativo: {usar_break_even}\n")

    def get_preco_atual():
        try:
            tool_price = BinanceGetPrice()
            price = tool_price._run(cripto)
            return price
        except Exception as e:
            print(f"Erro ao obter preço atual: {e}")
            return None
    
    estado_trade_principal = {
        "trade_id": trade_id,
        "cripto": cripto,
        "status": "EM_ANDAMENTO",
        "timestamp_entrada": inicio_operacao,
        "preco_entrada": preco_entrada,
        "valor_investido": valor_investido,
        "preco_alvo": preco_alvo,
        "preco_stop_loss_inicial": preco_stop,
        "preco_stop_atual": preco_stop, 
        "trailing_topo_atual": trailing_topo,
        "duracao_atual_minutos": 0,
        "lucro_liquido_estimado": 0.0,
        "retorno_percentual_estimado": 0.0
    }
    salvar_estado_trade_principal(estado_trade_principal)

    while True:
        preco_atual = get_preco_atual()
        try:
            preco_atual = ast.literal_eval(preco_atual.split(": ", 1)[1])
        except Exception as e:
            print(f"Erro ao processar preço: {e}")
            time.sleep(30)
            continue

        if preco_atual is not None:
            if isinstance(preco_atual, dict):
                # Caso seja um dicionário, extraia o preço
                preco_str = preco_atual.get('price')  # Usar .get() para evitar KeyError
                if preco_str is not None:
                    preco_float = float(preco_str)
                else:
                    raise ValueError("A chave 'price' não existe no dicionário.")
            else:
                # Caso seja uma string, converta diretamente
                preco_float = float(preco_atual)
        else:
            if verbose:
                print(f"[{datetime.datetime.now()}] Preço indisponível. Aguardando 30 segundos...")
            time.sleep(30)
            continue
        
        if verbose:
            print(f"[{datetime.datetime.now()}] Minuto {indice_minuto} - Preço atual: {preco_float:.8f}")
            print(f"Preço stop atual: {preco_stop:.8f} | Topo: {trailing_topo:.8f}")

        
        # Atualiza o estado para o salvamento principal a cada iteração
        estado_trade_principal.update({
            "preco_atual": preco_float,
            "preco_stop_atual": preco_stop,
            "trailing_topo_atual": trailing_topo,
            "duracao_atual_minutos": indice_minuto,
            "timestamp_ultima_atualizacao": datetime.datetime.now()
        })

        
        # 📝 Adiciona dados ao histórico
        historico_trade.append({
            "timestamp": datetime.datetime.now(),
            "minuto": indice_minuto,
            "preco_atual": preco_float,
            "preco_stop": preco_stop,
            "preco_alvo": preco_alvo,
            "trailing_topo": trailing_topo,
            "atingiu_break_even": atingiu_break_even,
            "trade_id": trade_id
        })
        
        # Verifica Stop Loss
        if preco_float <= preco_stop:
            resultado = "Stop Loss"
            if verbose:
                print(f"[{datetime.datetime.now()}] Stop Loss acionado a {preco_float:.8f}")
            break

        # Verifica Stop Gain
        if preco_float >= preco_alvo:
            resultado = "Stop Gain"
            if verbose:
                print(f"[{datetime.datetime.now()}] Stop Gain acionado a {preco_float:.8f}")
            break

        # Verifica Break Even
        if usar_break_even and not atingiu_break_even:
            if preco_float >= preco_entrada * (1 + break_even_trigger):
                # Atingiu o gatilho do break-even
                if preco_entrada > preco_stop: # Só move o stop se o preço de entrada for melhor que o stop atual
                    preco_stop = preco_break_even # Move o stop para o preço de entrada
                    atingiu_break_even = True
                    estado_trade_principal["atingiu_break_even"] = True # Atualiza no estado principal
                    if verbose:
                        print(f"[{datetime.datetime.now()}] Break-even ATIVADO. Preço atual: {preco_float:.8f}. Novo stop: {preco_stop:.8f}")
                elif verbose: # Se o stop já era melhor ou igual ao preço de entrada
                    print(f"[{datetime.datetime.now()}] Break-even trigger atingido ({preco_float:.8f}), mas stop atual ({preco_stop:.8f}) já é >= preço de entrada ({preco_entrada:.8f}). Break-even considerado ativo.")
                    atingiu_break_even = True # Marca como ativo mesmo assim para lógica do trailing stop
                    estado_trade_principal["atingiu_break_even"] = True

        # 4. Gerencia Trailing Stop (★★★ ALTERAÇÃO PRINCIPAL AQUI ★★★)
        # Só ativa o trailing stop SE `usar_trailing_stop` E `atingiu_break_even` forem verdadeiros
        # E o preço atual for maior que o último topo registrado para o trailing.
        if usar_trailing_stop and atingiu_break_even and preco_float > trailing_topo:
            trailing_topo = preco_float # Novo topo para o trailing
            novo_stop_trailing = trailing_topo * (1 - trailing_percentual)
            
            # O novo stop do trailing só é aplicado se for MAIOR que o preco_stop ATUAL.
            # Isso evita que o trailing stop "puxe para baixo" um stop que já foi elevado
            # (por exemplo, pelo break-even para o preço de entrada, ou por um trailing anterior).
            if novo_stop_trailing > preco_stop:
                preco_stop = novo_stop_trailing
                if verbose:
                    print(f"[{datetime.datetime.now()}] Trailing Stop ATUALIZADO (pós break-even). Novo topo: {trailing_topo:.8f} -> Novo Stop: {preco_stop:.8f}")
        
        # Atualiza estado principal (importante fazer antes do salvamento periódico)
        # Muitos campos já foram atualizados, mas podemos re-chamar para garantir consistência
        estado_trade_principal.update({
            "preco_stop_atual": preco_stop,
            "trailing_topo_atual": trailing_topo, # Garante que o topo usado no print é o mais recente
            "timestamp_ultima_atualizacao": datetime.datetime.now().isoformat()
        })

        # Salvamento automático por tempo
        tempo_passado = (datetime.datetime.now() - ultimo_salvamento).total_seconds()
        if tempo_passado >= intervalo_salvamento:
            df_parcial = pd.DataFrame(historico_trade)
            df_parcial.to_csv("log_trade_em_andamento.csv", mode="a", header=not os.path.exists("log_trade_em_andamento.csv"), index=False)
            salvar_estado_trade_principal(estado_trade_principal)
            historico_trade.clear()
            ultimo_salvamento = datetime.datetime.now()
            if verbose:
                print(f"[{datetime.datetime.now()}] Log parcial salvo.")
                print(f"[{datetime.datetime.now()}] Estado principal do trade salvo (por tempo).")

        time.sleep(30)  
        indice_minuto += 1

    # 💾 Salva o histórico antes de encerrar
    if historico_trade:
        df_parcial = pd.DataFrame(historico_trade)
        salvar_resultados_csv(df_parcial, nome_arquivo_base="agente", is_log=True)

    # Cálculo do resultado
    preco_saida = preco_float
    valor_final = preco_saida * quantidade
    lucro_bruto = valor_final - valor_investido
    custo_corretagem = valor_investido * taxa_corretagem + valor_final * taxa_corretagem
    lucro_liquido = lucro_bruto - custo_corretagem
    retorno_percentual = lucro_liquido / valor_investido
    duracao = datetime.datetime.now() - inicio_operacao

    resumo = f"{resultado} atingido após {indice_minuto} minutos. Lucro líquido: ${lucro_liquido:.8f} ({retorno_percentual:.2%})"
    print(resumo)

    resultado_final_trade = {
        "trade_id": trade_id,
        "cripto": cripto,
        "timestamp_entrada": inicio_operacao,
        "preco_entrada": preco_entrada,
        "preco_saida": preco_saida,
        "lucro_liquido": lucro_liquido,
        "retorno_percentual": retorno_percentual,
        "duracao": duracao,
        "saida_por": resultado,
        "status": "CONCLUIDO"
    }
    # --- Gatilho Final: Salva o estado principal como "CONCLUIDO" ---
    salvar_estado_trade_principal(resultado_final_trade)
    df_resultado_final_csv = pd.DataFrame([resultado_final_trade])
    salvar_resultados_csv(df_resultado_final_csv, nome_arquivo_base="agente", is_log=False)

    return resumo

def calcular_acertividade_modelo():
    """
    Função para calcular a acertividade do modelo.
    """
    # Obtém o caminho absoluto do diretório do script atual
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    
    # Define o caminho raiz corretamente (ex: ../bot_mcp/outputs/data)
    raiz = os.path.abspath(os.path.join(diretorio_atual, '..', 'outputs', 'data'))
    
    # Verifica se o caminho existe
    if not os.path.exists(raiz):
        raise FileNotFoundError(f"Diretório não encontrado: {raiz}")

    # Pastas de interesse
    pastas_desejadas = {"analise 04-29", "analise 04-30", "analise 05-01", "analise 05-02"}

    # Coluna que representa o lucro
    coluna_lucro = 'lucro_prejuizo'  # ajuste se necessário

    # Lista para armazenar os resultados
    resultados = []

    # Percorre as pastas de interesse
    for pasta in os.listdir(raiz):
        if pasta in pastas_desejadas:
            caminho_analise = os.path.join(raiz, pasta)

            for subpasta_raiz, _, arquivos in os.walk(caminho_analise):
                for arquivo in arquivos:
                    if arquivo.endswith('.csv'):
                        print
                        caminho_csv = os.path.join(subpasta_raiz, arquivo)

                        try:
                            df = pd.read_csv(caminho_csv)

                            if coluna_lucro not in df.columns:
                                print(f"[{arquivo}] Coluna '{coluna_lucro}' não encontrada.")
                                continue

                            total_predicoes = len(df)
                            predicoes_positivas = df[df[coluna_lucro] > 0].shape[0]
                            lucro_total = df[coluna_lucro].sum()

                            nome_modelo = os.path.splitext(arquivo)[0].replace('resultados_trades_', '')

                            resultados.append({
                                'modelo': nome_modelo,
                                'arquivo': arquivo,
                                'total_predicoes': total_predicoes,
                                'predicoes_positivas': predicoes_positivas,
                                'lucro_total': lucro_total
                            })

                        except Exception as e:
                            print(f"Erro ao processar {caminho_csv}: {e}")

    # Cria DataFrame com os resultados
    df_resultados = pd.DataFrame(resultados)

    # Salva o resultado consolidado em CSV e XLSX
    df_resultados.to_csv('relatorio_resultados_modelos.csv', index=False)

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

def escolher_top_cryptos(max_price: float = 0.1, intervalo: str = "1d", limite: int = 500, csv: bool = False) -> dict:
    """
    Roda a coleta de indicadores técnicos para todas as criptos em um DataFrame.
    :param df_criptos: DataFrame com uma coluna 'symbol' contendo os nomes das criptos (ex: BTCUSDT).
    :param intervalo: Intervalo das velas.
    :param limite: Número de candles.
    :return: Dicionário com dados históricos e indicadores para cada cripto.
    """
    resultados = {}
    
    modelos_ollama = ['falcon3:3b', 'falcon3:7b']
    data_hoje = datetime.datetime.today().strftime('%Y-%m-%d')
    resultados_por_modelo = {modelo: '' for modelo in modelos_ollama}   
    tool = BinanceListCryptosByPrice(max_price)
    
    df_criptos = tool._run()
    print(df_criptos.shape[0])

    for symbol in df_criptos["symbol"]:
        print(f"Processando {symbol}...")
        try:
            indicador_tool = BinanceGetTechnicalIndicators()
            content, df_historico = indicador_tool.get_technical_indicators(asset=symbol, interval=intervalo, limit=limite)
            df_historico['Open_time'] = pd.to_datetime(df_historico['Open time'], unit='ms')
            df_historico['Close_time'] = pd.to_datetime(df_historico['Close time'], unit='ms')
            
            if content["success"]:
                resultados[symbol] = {
                    "historical_data": df_historico,
                    "indicators": content["data"]["indicators"]
                }
            else:
                print(f"[ERRO] {symbol}: {content['error']}")
        
        except Exception as e:
            print(f"[EXCEÇÃO] {symbol}: {e}")
    
    def acertar_linhas(linhas):
        if isinstance(linhas, (pd.Series, list)):
            linhas = [x for x in linhas if x is not None and not pd.isna(x)]
            ultima_linha = linhas[-1] if linhas else 'N/A'
        else:
            ultima_linha = linhas if pd.notna(linhas) else 'N/A'
        return ultima_linha

    resultados_finais_notas = []
    for symbol, data in resultados.items():
        if 'historical_data' in data and isinstance(data['historical_data'], pd.DataFrame) and len(data['historical_data']) >= 4:
            valor_maximo = data['historical_data']['High'].iloc[-1]
            # Pegando o último candle
            ultimo_candle = data['historical_data'].iloc[-2]
            ultimo_open_ = ultimo_candle['Open']
            ultimo_high = ultimo_candle['High']
            ultimo_low = ultimo_candle['Low']
            ultimo_close = ultimo_candle['Close']
            ultimo_volume = ultimo_candle['Volume']
            ultimo_dia = ultimo_candle['Close_time'].strftime("%Y-%m-%d %H:%M:%S")
            
            # Pegando o penúltimo candle
            penultimo_candle = data['historical_data'].iloc[-3]
            penultimo_open_ = penultimo_candle['Open']
            penultimo_high = penultimo_candle['High']
            penultimo_low = penultimo_candle['Low']
            penultimo_close = penultimo_candle['Close']
            penultimo_volume = penultimo_candle['Volume']

            # Pegando o antepenúltimo candle
            antepenultimo_candle = data['historical_data'].iloc[-4]
            antepenultimo_open_ = antepenultimo_candle['Open']
            antepenultimo_high = antepenultimo_candle['High']
            antepenultimo_low = antepenultimo_candle['Low']
            antepenultimo_close = antepenultimo_candle['Close']
            antepenultimo_volume = antepenultimo_candle['Volume']
        
            # Pegando os indicadores
            rsi = data['indicators'].get('rsi', 'N/A')
            if rsi is not None:
                ultimo_valor_rsi = acertar_linhas(rsi)
            else:
                ultimo_valor_rsi = 'N/A'

            sma_50 = data['indicators'].get('sma_50', 'N/A')
            if sma_50 is not None:
                ultimo_valor_sma_50 = acertar_linhas(sma_50)
            else:
                ultimo_valor_sma_50 = 'N/A'

            sma_200 = data['indicators'].get('sma_200', 'N/A')
            if sma_200 is not None:
                ultimo_valor_sma_200 = acertar_linhas(sma_200)
            else:
                ultimo_valor_sma_200 = 'N/A'

            ema_20 = data['indicators'].get('ema_20', 'N/A')
            if ema_20 is not None:
                ultimo_valor_ema_20 = acertar_linhas(ema_20)
            else:
                ultimo_valor_ema_20 = 'N/A'

            ema_50 = data['indicators'].get('ema_50', 'N/A')
            if ema_50 is not None:
                ultimo_valor_ema_50 = acertar_linhas(ema_50)
            else:
                ultimo_valor_ema_50 = 'N/A'

            adx = data['indicators'].get('adx', 'N/A')
            if adx is not None:
                ultimo_valor_adx = acertar_linhas(adx)
            else:   
                ultimo_valor_adx = 'N/A'

            mfi = data['indicators'].get('mfi', 'N/A')
            if mfi is not None:
                ultimo_valor_mfi = acertar_linhas(mfi)
            else:
                ultimo_valor_mfi = 'N/A'

            macd = data['indicators'].get('macd', 'N/A')
            if macd is not None:
                ultimo_valor_macd_line = acertar_linhas(macd['macd_line'])
                ultimo_valor_macd_signal = acertar_linhas(macd['signal_line'])
                ultimo_valor_macd_histogram = acertar_linhas(macd['histogram'])
            else:
                ultimo_valor_macd_line = 'N/A'
                ultimo_valor_macd_signal = 'N/A'
                ultimo_valor_macd_histogram = 'N/A'

            bollinger = data['indicators'].get('bollinger_bands', 'N/A')
            if bollinger is not None:
                ultimo_valor_bollinger_upper = acertar_linhas(bollinger['upper_band'])
                ultimo_valor_bollinger_middle = acertar_linhas(bollinger['middle_band'])
                ultimo_valor_bollinger_lower = acertar_linhas(bollinger['lower_band'])
            else:
                ultimo_valor_bollinger_upper = 'N/A'
                ultimo_valor_bollinger_middle = 'N/A'
                ultimo_valor_bollinger_lower = 'N/A'

            pivot = data['indicators'].get('pivot_points', 'N/A')
            if pivot is not None:
                ultimo_valor_pivot = acertar_linhas(pivot['pivot'])
                ultimo_valor_pivot_r1 = acertar_linhas(pivot['r1'])
                ultimo_valor_pivot_s1 = acertar_linhas(pivot['s1'])
                ultimo_valor_pivot_r2 = acertar_linhas(pivot['r2'])
                ultimo_valor_pivot_s2 = acertar_linhas(pivot['s2'])
                ultimo_valor_pivot_r3 = acertar_linhas(pivot['r3'])
                ultimo_valor_pivot_s3 = acertar_linhas(pivot['s3'])
            else:
                ultimo_valor_pivot = 'N/A'
                ultimo_valor_pivot_r1 = 'N/A'
                ultimo_valor_pivot_s1 = 'N/A'
                ultimo_valor_pivot_r2 = 'N/A'
                ultimo_valor_pivot_s2 = 'N/A'
                ultimo_valor_pivot_r3 = 'N/A'
                ultimo_valor_pivot_s3 = 'N/A'
            
            stochastic = data['indicators'].get('stochastic', 'N/A')
            if stochastic is not None:
                ultimo_valor_stochastic_k = acertar_linhas(stochastic['stochastic_k'])
                ultimo_valor_stochastic_d = acertar_linhas(stochastic['stochastic_d'])
            else:
                ultimo_valor_stochastic_k = 'N/A'
                ultimo_valor_stochastic_d = 'N/A'

            prompt = f"""
            O ativo {symbol} apresentou os seguintes dados no último candle:
            Antepenúltimo candlestick
            - Opening: {antepenultimo_open_}
            - Maximum: {antepenultimo_high}
            - Minimum: {antepenultimo_low}
            - Closing: {antepenultimo_close}
            - Volume: {antepenultimo_volume}
            Penúltimo candlestick
            - Opening: {penultimo_open_}
            - Maximum: {penultimo_high}
            - Minimum: {penultimo_low}
            - Closing: {penultimo_close}
            - Volume: {penultimo_volume}
            Último candlestick
            - Opening: {ultimo_open_}
            - Maximum: {ultimo_high}
            - Minimum: {ultimo_low}
            - Closing: {ultimo_close}
            - Volume: {ultimo_volume}
            Technical indicators
            - SMA(50): {ultimo_valor_sma_50}
            - SMA(200): {ultimo_valor_sma_200}
            - EMA(20): {ultimo_valor_ema_20}
            - EMA(50): {ultimo_valor_ema_50}
            - ADX: {ultimo_valor_adx}
            - MFI: {ultimo_valor_mfi}
            - RSI: {ultimo_valor_rsi}
            - MACD: {ultimo_valor_macd_line}
            - MACD Signal: {ultimo_valor_macd_signal}
            - MACD Histogram: {ultimo_valor_macd_histogram}
            - Bollinger Upper: {ultimo_valor_bollinger_upper}
            - Bollinger Middle: {ultimo_valor_bollinger_middle}
            - Bollinger Lower: {ultimo_valor_bollinger_lower}
            - Pivot: {ultimo_valor_pivot}
            - Pivot R1: {ultimo_valor_pivot_r1}
            - Pivot S1: {ultimo_valor_pivot_s1}
            - Pivot R2: {ultimo_valor_pivot_r2}
            - Pivot S2: {ultimo_valor_pivot_s2}
            - Pivot R3: {ultimo_valor_pivot_r3}
            - Pivot S3: {ultimo_valor_pivot_s3}
            - Stochastic K: {ultimo_valor_stochastic_k}
            - Stochastic D: {ultimo_valor_stochastic_d}
                
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
                print('#########################################################################')
                print(f'Predicao {modelo} para o ativo: {symbol}')
                print(f'Conteudo: {conteudo}')
                print('#########################################################################')

                nota = parse_llm_score(conteudo)
                try:
                    nota = float(nota)  # transforma para número, se possível
                except ValueError:
                    nota = None  # se não for número, guarda como None

                notas_modelos[modelo] = nota
            # Calcular a média das notas (ignorando None)
            notas_validas = [v for k, v in notas_modelos.items() if k != 'symbol' and isinstance(v, (int, float))]
            notas_modelos['media'] = sum(notas_validas) / len(notas_validas) if notas_validas else None

            notas_modelos[f'valor_dia_{ultimo_dia}'] = ultimo_close
            notas_modelos[f'maior_valor_dia_{data_hoje}'] = valor_maximo
            notas_modelos['valorizacao'] = ((valor_maximo - ultimo_close) / ultimo_close) * 100
            resultados_finais_notas.append(notas_modelos)
        else:
            continue
    # Criar DataFrame com uma única linha
    df_resultados = pd.DataFrame(resultados_finais_notas)

    df_resultados = df_resultados.sort_values(by='media', ascending=False)
    df_resultados = df_resultados.sort_values(by='media', ascending=False).reset_index(drop=True)
    df_resultados = df_resultados.dropna()
    df_top_cryptos = df_resultados.head(10)
    df_piores_cryptos = df_resultados.tail(10)

    print('Top 10 criptos:')
    print(df_top_cryptos)
    print('Piores 10 criptos:')
    print(df_piores_cryptos)

    if csv == True:
        df_top_cryptos.to_csv(f'outputs/data/relatorios_recomendação_diaria/top_cryptos_{data_hoje}.csv', index=False)
        df_piores_cryptos.to_csv(f'outputs/data/relatorios_recomendação_diaria/piores_cryptos_{data_hoje}.csv', index=False)

    return df_resultados

def avaliar_btc(intervalo: str = "1d", symbol: str = "BTCUSDT", limite: int = 500):
    def acertar_linhas(linhas):
        if isinstance(linhas, (pd.Series, list)):
            linhas = [x for x in linhas if x is not None and not pd.isna(x)]
            ultima_linha = linhas[-1] if linhas else 'N/A'
        else:
            ultima_linha = linhas if pd.notna(linhas) else 'N/A'
        return ultima_linha
    
    resultados = {}
    modelos_ollama = ['falcon3:3b', 'falcon3:7b']
    try:
        
        indicador_tool = BinanceGetTechnicalIndicators()
        content, df_historico = indicador_tool.get_technical_indicators(asset=symbol, interval=intervalo, limit=limite)
        df_historico['Open_time'] = pd.to_datetime(df_historico['Open time'], unit='ms')
        df_historico['Close_time'] = pd.to_datetime(df_historico['Close time'], unit='ms')
        
        if content["success"]:
            resultados[symbol] = {
                "historical_data": df_historico,
                "indicators": content["data"]["indicators"]
            }
        
        else:
            print(f"[ERRO] {symbol}: {content['error']}")
        
    except Exception as e:
        print(f"[EXCEÇÃO] {symbol}: {e}")
    
    for symbol, data in resultados.items():
        if 'historical_data' in data and isinstance(data['historical_data'], pd.DataFrame) and len(data['historical_data']) >= 4:
            valor_maximo = data['historical_data']['High'].iloc[-1]
            # Pegando o último candle
            ultimo_candle = data['historical_data'].iloc[-2]
            ultimo_open_ = ultimo_candle['Open']
            ultimo_high = ultimo_candle['High']
            ultimo_low = ultimo_candle['Low']
            ultimo_close = ultimo_candle['Close']
            ultimo_volume = ultimo_candle['Volume']
            ultimo_dia = ultimo_candle['Close_time'].strftime("%Y-%m-%d %H:%M:%S")
            
            # Pegando o penúltimo candle
            penultimo_candle = data['historical_data'].iloc[-3]
            penultimo_open_ = penultimo_candle['Open']
            penultimo_high = penultimo_candle['High']
            penultimo_low = penultimo_candle['Low']
            penultimo_close = penultimo_candle['Close']
            penultimo_volume = penultimo_candle['Volume']

            # Pegando o antepenúltimo candle
            antepenultimo_candle = data['historical_data'].iloc[-4]
            antepenultimo_open_ = antepenultimo_candle['Open']
            antepenultimo_high = antepenultimo_candle['High']
            antepenultimo_low = antepenultimo_candle['Low']
            antepenultimo_close = antepenultimo_candle['Close']
            antepenultimo_volume = antepenultimo_candle['Volume']
        
            # Pegando os indicadores
            rsi = data['indicators'].get('rsi', 'N/A')
            if rsi is not None:
                ultimo_valor_rsi = acertar_linhas(rsi)
            else:
                ultimo_valor_rsi = 'N/A'

            sma_50 = data['indicators'].get('sma_50', 'N/A')
            if sma_50 is not None:
                ultimo_valor_sma_50 = acertar_linhas(sma_50)
            else:
                ultimo_valor_sma_50 = 'N/A'

            sma_200 = data['indicators'].get('sma_200', 'N/A')
            if sma_200 is not None:
                ultimo_valor_sma_200 = acertar_linhas(sma_200)
            else:
                ultimo_valor_sma_200 = 'N/A'

            ema_20 = data['indicators'].get('ema_20', 'N/A')
            if ema_20 is not None:
                ultimo_valor_ema_20 = acertar_linhas(ema_20)
            else:
                ultimo_valor_ema_20 = 'N/A'

            ema_50 = data['indicators'].get('ema_50', 'N/A')
            if ema_50 is not None:
                ultimo_valor_ema_50 = acertar_linhas(ema_50)
            else:
                ultimo_valor_ema_50 = 'N/A'

            adx = data['indicators'].get('adx', 'N/A')
            if adx is not None:
                ultimo_valor_adx = acertar_linhas(adx)
            else:   
                ultimo_valor_adx = 'N/A'

            mfi = data['indicators'].get('mfi', 'N/A')
            if mfi is not None:
                ultimo_valor_mfi = acertar_linhas(mfi)
            else:
                ultimo_valor_mfi = 'N/A'

            macd = data['indicators'].get('macd', 'N/A')
            if macd is not None:
                ultimo_valor_macd_line = acertar_linhas(macd['macd_line'])
                ultimo_valor_macd_signal = acertar_linhas(macd['signal_line'])
                ultimo_valor_macd_histogram = acertar_linhas(macd['histogram'])
            else:
                ultimo_valor_macd_line = 'N/A'
                ultimo_valor_macd_signal = 'N/A'
                ultimo_valor_macd_histogram = 'N/A'

            bollinger = data['indicators'].get('bollinger_bands', 'N/A')
            if bollinger is not None:
                ultimo_valor_bollinger_upper = acertar_linhas(bollinger['upper_band'])
                ultimo_valor_bollinger_middle = acertar_linhas(bollinger['middle_band'])
                ultimo_valor_bollinger_lower = acertar_linhas(bollinger['lower_band'])
            else:
                ultimo_valor_bollinger_upper = 'N/A'
                ultimo_valor_bollinger_middle = 'N/A'
                ultimo_valor_bollinger_lower = 'N/A'

            pivot = data['indicators'].get('pivot_points', 'N/A')
            if pivot is not None:
                ultimo_valor_pivot = acertar_linhas(pivot['pivot'])
                ultimo_valor_pivot_r1 = acertar_linhas(pivot['r1'])
                ultimo_valor_pivot_s1 = acertar_linhas(pivot['s1'])
                ultimo_valor_pivot_r2 = acertar_linhas(pivot['r2'])
                ultimo_valor_pivot_s2 = acertar_linhas(pivot['s2'])
                ultimo_valor_pivot_r3 = acertar_linhas(pivot['r3'])
                ultimo_valor_pivot_s3 = acertar_linhas(pivot['s3'])
            else:
                ultimo_valor_pivot = 'N/A'
                ultimo_valor_pivot_r1 = 'N/A'
                ultimo_valor_pivot_s1 = 'N/A'
                ultimo_valor_pivot_r2 = 'N/A'
                ultimo_valor_pivot_s2 = 'N/A'
                ultimo_valor_pivot_r3 = 'N/A'
                ultimo_valor_pivot_s3 = 'N/A'
            
            stochastic = data['indicators'].get('stochastic', 'N/A')
            if stochastic is not None:
                ultimo_valor_stochastic_k = acertar_linhas(stochastic['stochastic_k'])
                ultimo_valor_stochastic_d = acertar_linhas(stochastic['stochastic_d'])
            else:
                ultimo_valor_stochastic_k = 'N/A'
                ultimo_valor_stochastic_d = 'N/A'

            prompt = f"""
            O ativo {symbol} apresentou os seguintes dados no último candle:
            Antepenúltimo candlestick
            - Opening: {antepenultimo_open_}
            - Maximum: {antepenultimo_high}
            - Minimum: {antepenultimo_low}
            - Closing: {antepenultimo_close}
            - Volume: {antepenultimo_volume}
            Penúltimo candlestick
            - Opening: {penultimo_open_}
            - Maximum: {penultimo_high}
            - Minimum: {penultimo_low}
            - Closing: {penultimo_close}
            - Volume: {penultimo_volume}
            Último candlestick
            - Opening: {ultimo_open_}
            - Maximum: {ultimo_high}
            - Minimum: {ultimo_low}
            - Closing: {ultimo_close}
            - Volume: {ultimo_volume}
            Technical indicators
            - SMA(50): {ultimo_valor_sma_50}
            - SMA(200): {ultimo_valor_sma_200}
            - EMA(20): {ultimo_valor_ema_20}
            - EMA(50): {ultimo_valor_ema_50}
            - ADX: {ultimo_valor_adx}
            - MFI: {ultimo_valor_mfi}
            - RSI: {ultimo_valor_rsi}
            - MACD: {ultimo_valor_macd_line}
            - MACD Signal: {ultimo_valor_macd_signal}
            - MACD Histogram: {ultimo_valor_macd_histogram}
            - Bollinger Upper: {ultimo_valor_bollinger_upper}
            - Bollinger Middle: {ultimo_valor_bollinger_middle}
            - Bollinger Lower: {ultimo_valor_bollinger_lower}
            - Pivot: {ultimo_valor_pivot}
            - Pivot R1: {ultimo_valor_pivot_r1}
            - Pivot S1: {ultimo_valor_pivot_s1}
            - Pivot R2: {ultimo_valor_pivot_r2}
            - Pivot S2: {ultimo_valor_pivot_s2}
            - Pivot R3: {ultimo_valor_pivot_r3}
            - Pivot S3: {ultimo_valor_pivot_s3}
            - Stochastic K: {ultimo_valor_stochastic_k}
            - Stochastic D: {ultimo_valor_stochastic_d}
                
            Com base nesses indicadores e no comportamento histórico recente, 
            avalie a probabilidade de um movimento de alta para o ativo 
            {symbol} em uma escala de 0 (probabilidade muito baixa) a 100 (probabilidade muito alta).

            Responda somente e exclusivamente dessa forma:
            "nota: SUA NOTA"
            """
    notas_modelos = {}    
    for modelo in modelos_ollama:
        #"role": "user", 
        relatorio = ollama.chat(model=modelo, messages=[{"role": "user", "content": prompt}])
        conteudo = relatorio['message']['content'] 
        #if isinstance(relatorio, dict) else str(relatorio)
        print('#########################################################################')
        print(f'Predicao {modelo} para o ativo: {symbol}')
        print(f'Conteudo: {conteudo}')
        
        nota = parse_llm_score(conteudo)
        notas_modelos[modelo] = nota
    
    notas_validas = [nota for nota in notas_modelos.values() if nota is not None]

    if notas_validas:
        media_aritmetica = sum(notas_validas) / len(notas_validas)
        print(f"A média aritmética das notas válidas é: {media_aritmetica}")
        # ... e depois pode salvar no dicionário e criar o DataFrame
        notas_modelos['media_aritmetica'] = media_aritmetica
        
    else:
        print("Não há notas válidas para calcular a média.")
        notas_modelos['media_aritmetica'] = None

    df_notas = pd.Series(notas_modelos).to_frame(name='Nota')
    valor_media = df_notas.loc['media_aritmetica', 'Nota']
    return valor_media