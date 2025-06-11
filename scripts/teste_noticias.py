import requests
from bs4 import BeautifulSoup
import ollama
import csv
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
from datetime import datetime, timezone, timedelta
import json
import os

# def testar_api_get(url):
#     """
#     Função para fazer uma chamada GET a uma API e exibir a resposta.
#     """
#     print(f"Fazendo chamada GET para: {url}")
    
#     try:
#         # 1. Fazer a chamada para a API usando requests.get()
#         response = requests.get(url)

#         # 2. Verificar se a chamada foi bem-sucedida
#         # O método raise_for_status() lançará um erro se o status não for 2xx (sucesso).
#         response.raise_for_status()
        
#         # Se chegamos aqui, a chamada foi um sucesso (Status Code 200 OK)
#         print(f"Sucesso! Código de Status: {response.status_code}")

#         # 3. Extrair os dados da resposta em formato JSON
#         # O método .json() já converte a resposta JSON em um dicionário Python.
#         print(response.text)
#         dados = response.json()

#         # 4. Apresentar os dados de forma legível
#         print("\n--- DADOS RECEBIDOS DA API ---")
#         # Usamos json.dumps com indent=4 para formatar o dicionário e facilitar a leitura.
#         print(json.dumps(dados, indent=4, ensure_ascii=False))

#     except requests.exceptions.HTTPError as errh:
#         # Erros específicos de HTTP (ex: 404 Not Found, 403 Forbidden)
#         print(f"Erro HTTP: {errh}")
#         print(f"Código de Status: {response.status_code}")
#         print(f"Resposta do servidor: {response.text}")
#     except requests.exceptions.RequestException as err:
#         # Erros mais genéricos (ex: falha de conexão)
#         print(f"Ocorreu um erro na requisição: {err}")

# testar_api_get('https://api.cryptotreemap.com/coins')



import requests
import pandas as pd
import matplotlib.pyplot as plt
import squarify 
import numpy as np

class HeatMap():
    """
    Classe para pesquisar as maior moedas do mercado e criar o gráfico Heatmap das 40 maiores.
    """
    def __init__(self):
        pass
    # --- Passo 1: Obter as 100 principais moedas por capitalização de mercado (sem alterações) ---
    def get_top_100_coins(self):
        """Busca as 100 maiores criptomoedas por capitalização de mercado no CoinGecko."""
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': 100,
            'page': 1,
            'sparkline': 'false'
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            df = pd.DataFrame(data)[['symbol', 'market_cap']]
            df['symbol'] = df['symbol'].str.upper()
            return df
        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar dados do CoinGecko: {e}")
            return None

    # --- Passo 2: Obter dados de variação de 24h da API da Binance (sem alterações) ---
    def get_binance_24h_changes(self):
        """Busca os dados de variação de preço de 24h para todos os pares na Binance."""
        url = "https://api.binance.com/api/v3/ticker/24hr"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            price_data = {}
            for item in data:
                if item['symbol'].endswith('USDT'):
                    symbol = item['symbol'].replace('USDT', '')
                    price_data[symbol] = {
                        'price': float(item['lastPrice']),
                        'change_24h': float(item['priceChangePercent'])
                    }
            return price_data
        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar dados da Binance: {e}")
            return None

    # --- Passo 3: Combinar os dados e gerar o gráfico ---
    def create_crypto_treemap(self):
        """Função principal que combina os dados e cria o treemap com Matplotlib."""

        # --- CONFIGURAÇÕES ---
        STABLECOINS_A_EXCLUIR = ['USDT', 'USDC', 'DAI', 'TUSD', 'FDUSD', 'USDP', 'BUSD', 'USDS']
        MOEDAS_PARA_MOSTRAR_INDIVIDUALMENTE = 40
        COR_DAS_DIVISORIAS = 'black'
        LARGURA_DAS_DIVISORIAS = 1
        FATOR_DE_COMPRESSAO = 0.5

        print("Buscando e processando dados...")
        top_coins_df = self.get_top_100_coins()
        if top_coins_df is None:
            return

        binance_data = self.get_binance_24h_changes()
        if binance_data is None:
            return

        # Combinar os dados
        data_to_plot = []
        for _, row in top_coins_df.iterrows():
            symbol = row['symbol']
            if symbol in binance_data:
                coin_info = binance_data[symbol]
                data_to_plot.append({
                    'symbol': symbol,
                    'market_cap': row['market_cap'],
                    'change_24h': coin_info['change_24h'],
                    'price': coin_info['price']
                })

        full_df = pd.DataFrame(data_to_plot)

        print(f"Excluindo stablecoins: {', '.join(STABLECOINS_A_EXCLUIR)}")
        plot_df = full_df[~full_df['symbol'].isin(STABLECOINS_A_EXCLUIR)].copy()

        # Agrupar menores como "OUTROS"
        if len(plot_df) > MOEDAS_PARA_MOSTRAR_INDIVIDUALMENTE:
            print(f"Mostrando as {MOEDAS_PARA_MOSTRAR_INDIVIDUALMENTE} maiores e agrupando as outras.")
            df_top = plot_df.head(MOEDAS_PARA_MOSTRAR_INDIVIDUALMENTE)
            df_others = plot_df.tail(len(plot_df) - MOEDAS_PARA_MOSTRAR_INDIVIDUALMENTE)
            others_market_cap = df_others['market_cap'].sum()
            weighted_change_others = np.average(df_others['change_24h'], weights=df_others['market_cap'])
            df_others_grouped = pd.DataFrame([{
                'symbol': 'OUTROS',
                'market_cap': others_market_cap,
                'change_24h': weighted_change_others,
                'price': 0
            }])
            plot_df = pd.concat([df_top, df_others_grouped]).reset_index(drop=True)

        print("Gerando o gráfico treemap com Matplotlib...")

        # Preparar dados para squarify
        plot_df['size'] = plot_df['market_cap'] ** FATOR_DE_COMPRESSAO
        colors = ['#2ca02c' if x >= 0 else '#d62728' for x in plot_df['change_24h']]

        # Normalizar tamanho da fonte com base no log da capitalização
        log_caps = np.log10(plot_df['market_cap'] + 1)
        min_size, max_size = 6, 18
        font_sizes = min_size + (log_caps - log_caps.min()) / (log_caps.max() - log_caps.min()) * (max_size - min_size)

        # Gerar retângulos
        rects = squarify.normalize_sizes(plot_df['size'], 100, 100)
        rects = squarify.squarify(rects, 0, 0, 100, 100)

        # Criar gráfico
        fig, ax = plt.subplots(figsize=(16, 9))
        for i, rect in enumerate(rects):
            symbol = plot_df.iloc[i]['symbol']
            change = plot_df.iloc[i]['change_24h']
            price = plot_df.iloc[i]['price']
            font_size = font_sizes.iloc[i]

            label = f"{symbol}\n{change:.2f}%\n${price:,.2f}" if symbol != 'OUTROS' else "OUTROS"

            # Retângulo
            ax.add_patch(plt.Rectangle(
                (rect['x'], rect['y']), rect['dx'], rect['dy'],
                facecolor=colors[i], edgecolor=COR_DAS_DIVISORIAS, linewidth=LARGURA_DAS_DIVISORIAS
            ))

            # Texto centralizado
            ax.text(
                rect['x'] + rect['dx'] / 2,
                rect['y'] + rect['dy'] / 2,
                label,
                ha='center', va='center',
                fontsize=font_size,
                color='white',
                weight='bold'
            )

        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.axis('off')
        plt.title('Heatmap Cripto por Capitalização de Mercado (24h)', fontsize=20, fontweight='bold')
        os.makedirs('outputs/images', exist_ok=True)
        plt.savefig('outputs/images/crypto_treemap_ajustado.png', 
                    dpi=300, 
                    bbox_inches='tight', 
                    pad_inches=0.1, 
                    facecolor='white')

        print("\nGráfico gerado com sucesso! O arquivo 'outputs/images/crypto_treemap_ajustado.png' foi salvo.")

# def create_crypto_treemap():
#     """Função principal que combina os dados e cria o treemap com Matplotlib."""
    
#     # --- CONFIGURAÇÕES ---
#     STABLECOINS_A_EXCLUIR = ['USDT', 'USDC', 'DAI', 'TUSD', 'FDUSD', 'USDP', 'BUSD']
#     MOEDAS_PARA_MOSTRAR_INDIVIDUALMENTE = 40 
#     COR_DAS_DIVISORIAS = 'black'
#     LARGURA_DAS_DIVISORIAS = 1
    
#     TAMANHO_DA_FONTE = 7.5
#     # Aumente este valor para fontes maiores no BTC/ETH.
    
#     # Use 0.5 para raiz quadrada. Valores maiores (ex: 0.7) dão mais diferença.
#     # Valores menores (ex: 0.4) dão menos diferença.
#     FATOR_DE_COMPRESSAO = 0.5
    
#     print("Buscando e processando dados...")
#     top_coins_df = get_top_100_coins()
#     if top_coins_df is None: return
    
#     binance_data = get_binance_24h_changes()
#     if binance_data is None: return
    
#     data_to_plot = []
#     for index, row in top_coins_df.iterrows():
#         symbol = row['symbol']
#         if symbol in binance_data:
#             coin_info = binance_data[symbol]
#             data_to_plot.append({'symbol': symbol,'market_cap': row['market_cap'],'change_24h': coin_info['change_24h']})
#     full_df = pd.DataFrame(data_to_plot)
#     print(f"Excluindo stablecoins: {', '.join(STABLECOINS_A_EXCLUIR)}")
#     plot_df = full_df[~full_df['symbol'].isin(STABLECOINS_A_EXCLUIR)].copy()
#     if len(plot_df) > MOEDAS_PARA_MOSTRAR_INDIVIDUALMENTE:
#         print(f"Mostrando as {MOEDAS_PARA_MOSTRAR_INDIVIDUALMENTE} maiores e agrupando as outras.")
#         df_top = plot_df.head(MOEDAS_PARA_MOSTRAR_INDIVIDUALMENTE)
#         df_others = plot_df.tail(len(plot_df) - MOEDAS_PARA_MOSTRAR_INDIVIDUALMENTE)
#         others_market_cap = df_others['market_cap'].sum()
#         weighted_change_others = np.average(df_others['change_24h'], weights=df_others['market_cap'])
#         df_others_grouped = pd.DataFrame([{'symbol': 'OUTROS','market_cap': others_market_cap,'change_24h': weighted_change_others}])
#         plot_df = pd.concat([df_top, df_others_grouped]).reset_index(drop=True)

#     print("Gerando o gráfico treemap com Matplotlib...")

#     # Preparar os dados para o squarify
#     colors = ['#2ca02c' if x >= 0 else '#d62728' for x in plot_df['change_24h']]
#     labels = [f"{row['symbol']}\n{row['change_24h']:.2f}%" for index, row in plot_df.iterrows()]
    
#     # --- MUDANÇA 1: Usando escala logarítmica para os tamanhos ---
#     # Isso equilibra a visualização, diminuindo a dominância do BTC/ETH
#     sizes = plot_df['market_cap'].values ** FATOR_DE_COMPRESSAO

#     # Criar o gráfico
#     plt.figure(figsize=(16, 9))
    
#     ax = squarify.plot(
#         sizes=sizes, 
#         label=labels, 
#         color=colors, 
#         alpha=0.85,
#         # --- MUDANÇA 2: Reduzindo o tamanho da fonte ---
#         text_kwargs={'fontsize': TAMANHO_DA_FONTE, 'color': 'white', 'fontweight': 'bold'}
#     )
    
#     # Adicionando as divisórias
#     for patch in ax.patches:
#         patch.set_edgecolor(COR_DAS_DIVISORIAS)
#         patch.set_linewidth(LARGURA_DAS_DIVISORIAS)

#     plt.title('Heatmap Cripto por Capitalização de Mercado (24h)', fontsize=20, fontweight='bold')
#     plt.axis('off')
    
#     plt.savefig('crypto_treemap_ajustado.png', dpi=300, bbox_inches='tight', pad_inches=0.1, facecolor='white')
    
#     print("\nGráfico ajustado gerado com sucesso! O arquivo 'crypto_treemap_ajustado.png' foi salvo.")

# --- Execução do Script ---
if __name__ == "__main__":
    h = HeatMap()
    h.create_crypto_treemap()
