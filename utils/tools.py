import os
import pandas as pd
from binance.client import Client
import time
from datetime import datetime, timedelta
import datetime

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