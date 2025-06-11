import requests
from bs4 import BeautifulSoup
import ollama
import csv
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
from datetime import datetime, timezone, timedelta
import json

# # Configurações
# COINTELEGRAPH_SITEMAP_URL = "https://cointelegraph.com/sitemap-google-news.xml"
# # Certifique-se que este modelo está disponível no seu Ollama (`ollama list`)
# OLLAMA_MODEL = "gemma3:12b" 
# REQUEST_HEADERS = {
#     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
# }
# # Limitar o número de notícias para processamento (para fins de demonstração/teste)
# MAX_NEWS_TO_PROCESS = 20 # Aumentado um pouco para testar mais artigos do sitemap

# def get_news_from_cointelegraph_sitemap():
#     """
#     Busca o sitemap de notícias do Cointelegraph Brasil e extrai
#     informações sobre os artigos.
#     Retorna uma lista de dicionários, cada um com 'title', 'original_article_url', 
#     'publication_date', e 'source_name'.
#     """
#     print(f"Buscando notícias do Cointelegraph em: {COINTELEGRAPH_SITEMAP_URL}")
#     news_items = []
#     try:
#         response = requests.get(COINTELEGRAPH_SITEMAP_URL, headers=REQUEST_HEADERS)
#         response.raise_for_status()
        
#         # Usar 'xml' ou 'lxml-xml' como parser para arquivos XML
#         soup = BeautifulSoup(response.content, 'xml')

#         # O sitemap contém múltiplas tags <url>
#         url_tags = soup.find_all('url')
        
#         count = 0
#         for url_tag in url_tags:
#             loc_tag = url_tag.find('loc')
#             news_tag = url_tag.find('news:news') # Acessa o namespace news

#             if loc_tag and news_tag:
#                 original_article_url = loc_tag.get_text(strip=True)
                
#                 title_tag = news_tag.find('news:title')
#                 publication_date_tag = news_tag.find('news:publication_date')
#                 publication_tag = news_tag.find('news:publication')
                
#                 title = title_tag.get_text(strip=True) if title_tag else "N/A"
#                 # Formatar a data para um formato mais legível, se desejado.
#                 # O formato original é ISO 8601. Ex: 2025-05-27T18:20:00.000Z
#                 publication_date_str = publication_date_tag.get_text(strip=True) if publication_date_tag else "N/A"
                
#                 source_name = "COINTELEGRAPH" # Padrão, mas podemos pegar do XML se preferir
#                 if publication_tag:
#                     name_tag = publication_tag.find('news:name')
#                     if name_tag:
#                         source_name = name_tag.get_text(strip=True)
                
#                 news_items.append({
#                     'title': title,
#                     'original_article_url': original_article_url,
#                     'publication_date': publication_date_str,
#                     'source_name': source_name
#                 })
#                 count += 1
#                 if count >= MAX_NEWS_TO_PROCESS: # Limitar o número de notícias
#                     break
        
#         if not news_items:
#             print("Nenhum item de notícia encontrado no sitemap. Verifique o URL ou a estrutura do XML.")

#     except requests.exceptions.RequestException as e:
#         print(f"Erro ao buscar sitemap do Cointelegraph: {e}")
#     except Exception as e:
#         print(f"Erro ao processar o sitemap XML: {e}")
#     return news_items

# def extract_article_text_from_url(article_url):
#     """
#     Extrai o texto principal de um URL de artigo de notícias.
#     Esta é uma função genérica e pode não funcionar perfeitamente para todos os sites.
#     """
#     print(f"    Extraindo texto de: {article_url}")
#     try:
#         response = requests.get(article_url, headers=REQUEST_HEADERS, timeout=15) # Aumentado timeout
#         response.raise_for_status()
#         soup = BeautifulSoup(response.content, 'html.parser')

#         # Seletores comuns para conteúdo de artigo no Cointelegraph (podem mudar)
#         # O Cointelegraph usa classes como 'post-content', 'post__content'
#         main_content_tags = [
#             'div.post-content', 
#             'div.post__content', 
#             'article.post__article', # Mais específico para o article
#             'article', # Genérico
#             'main' # Genérico
#         ]
#         content_html = None
#         for tag_selector in main_content_tags:
#             if '.' in tag_selector or '#' in tag_selector or '[' in tag_selector: # Seletor CSS complexo
#                 content_html = soup.select_one(tag_selector)
#             else: # Seletor de tag simples
#                 content_html = soup.find(tag_selector)
            
#             if content_html:
#                 print(f"      Container de conteúdo encontrado com seletor: '{tag_selector}'")
#                 break
        
#         if not content_html: # Fallback para o body se nada específico for encontrado
#             print("      Nenhum container de conteúdo principal específico encontrado, tentando body...")
#             content_html = soup.body

#         if not content_html:
#              print(f"      Não foi possível encontrar o container principal de conteúdo em {article_url}")
#              return ""

#         # Remover elementos indesejados (scripts, styles, menus, etc.) antes de extrair texto
#         for unwanted_tag in content_html(['script', 'style', 'nav', 'header', 'footer', 'aside', '.related-articles', '.social-share']):
#             unwanted_tag.decompose()

#         # Extrair texto de parágrafos <p> dentro do conteúdo principal
#         paragraphs = content_html.find_all('p')
#         article_text = "\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]) # Evitar parágrafos vazios
        
#         if not article_text.strip(): # Se não houver parágrafos, tentar pegar todo o texto do container
#             print("      Nenhum parágrafo encontrado no container, tentando texto geral do container.")
#             article_text = content_html.get_text(separator='\n', strip=True)

#         # Limpeza adicional (opcional)
#         article_text = "\n".join([line for line in article_text.splitlines() if line.strip()])

#         if not article_text.strip():
#             print(f"Texto extraído de {article_url} está vazio após tentativas.")
        
#         return article_text

#     except requests.exceptions.Timeout:
#         print(f"    Timeout ao extrair texto de {article_url}")
#     except requests.exceptions.RequestException as e:
#         print(f"    Erro de requisição ao extrair texto de {article_url}: {e}")
#     except Exception as e:
#         print(f"    Erro inesperado ao processar {article_url} para extração de texto: {e}")
#     return ""

# def summarize_text_with_ollama(text, model_name=OLLAMA_MODEL):
#     """
#     Envia o texto para o Ollama para resumo e análise de sentimento.
#     """
#     if not text or not text.strip():
#         print("Texto vazio fornecido para resumo. Pulando.")
#         return "Não foi possível extrair conteúdo para resumo."

#     print(f"      Enviando texto para o modelo Ollama '{model_name}' para resumo...")
    
#     # Prompt ajustado para ser mais direto
#     prompt = f"""Por favor, resuma o seguinte texto de notícia em português, em aproximadamente 3 frases.
# O resumo deve focar em identificar o sentimento predominante (positivo, negativo ou neutro) expresso no texto.
# Se o texto for muito curto, irrelevante ou não for uma notícia financeira/cripto, indique isso.

# Texto da notícia:
# ---
# {text[:5000]} 
# ---
# Resumo Conciso e Sentimento:""" # Limitar o tamanho do prompt para Ollama

#     try:
#         response_ollama = ollama.generate(
#             model=model_name,
#             prompt=prompt,
#             # options={"temperature": 0.5} # Exemplo de opção, ajuste conforme necessário
#         )
#         summary = response_ollama['response'].strip()
#         print(f"      Resumo recebido: {summary}")
#         return summary
#     except Exception as e:
#         print(f"      Erro ao comunicar com Ollama ou gerar resumo: {e}")
#         print(f"      Verifique se o Ollama está rodando e o modelo '{model_name}' está disponível ('ollama list').")
#         return "Erro ao gerar resumo via Ollama."

# def monitor_and_summarize_crypto_news(output_format='print', csv_filename='crypto_news_summary.csv', hours_limit=2): # Adicionado hours_limit
#     """
#     Função principal para monitorar, extrair, resumir notícias e apresentar/salvar os resultados.
#     Processa apenas notícias publicadas dentro do 'hours_limit' especificado.
#     output_format pode ser 'print', 'csv', 'list', ou 'all'.
#     """
#     print(f"Iniciando monitoramento e resumo de notícias cripto (Fonte: Cointelegraph Sitemap)...")
#     print(f"Processando notícias publicadas nas últimas {hours_limit} hora(s).") # Feedback para o usuário

#     sitemap_news_items = get_news_from_cointelegraph_sitemap()

#     # print(f"DEBUG: Total de notícias lidas do sitemap AGORA: {len(sitemap_news_items)}") # Verifique este número!
#     # if sitemap_news_items:
#     #     print(f"DEBUG: Primeira notícia do sitemap (após modificação): '{sitemap_news_items[0]['title']}' Data: {sitemap_news_items[0]['publication_date']}")
#     #     # Vamos imprimir as datas de várias notícias para análise
#     #     print("DEBUG: Listando algumas datas de publicação das notícias lidas do sitemap:")
#     #     for i, news_item in enumerate(sitemap_news_items[:50]): # Veja as primeiras 50, por exemplo
#     #         print(f"  Item {i}: Data {news_item['publication_date']}")
#     #     if len(sitemap_news_items) > 50: # Se houver mais, veja algumas do final também
#     #          print("DEBUG: Listando algumas datas do FINAL da lista do sitemap:")
#     #          for i, news_item in enumerate(sitemap_news_items[-10:]): # Veja as últimas 10 da lista lida
#     #             print(f"  Item {len(sitemap_news_items) - 10 + i}: Data {news_item['publication_date']}")
#     # else:
#     #     print("DEBUG: Nenhuma notícia foi retornada pelo get_news_from_cointelegraph_sitemap.")

#     if not sitemap_news_items:
#         print("Nenhuma notícia encontrada no sitemap do Cointelegraph para processar.")
#         return []

#     all_summaries = []
#     # Usar UTC para data de extração para consistência
#     extraction_datetime_utc = datetime.now(timezone.utc)
#     print(f'Horário atual (UTC): {extraction_datetime_utc}')
#     extraction_date_str = extraction_datetime_utc.strftime('%Y-%m-%d %H:%M:%S %Z')

#     # Calcular o ponto de corte no tempo (X horas atrás a partir de agora em UTC)
#     time_threshold = extraction_datetime_utc - timedelta(hours=hours_limit)
#     print(f"Filtrando notícias publicadas após: {time_threshold.strftime('%Y-%m-%d %H:%M:%S %Z')}")

#     processed_count = 0 # Contador para notícias que passam no filtro de tempo

#     for item in sitemap_news_items:
#         print(f"\nVerificando notícia: {item['title']}")
#         print(f"  Data de Publicação (do sitemap): {item['publication_date']}")

#         # Converter a string de data de publicação para um objeto datetime
#         # O formato da data do sitemap é ISO 8601 (ex: 2024-05-15T14:30:00Z)
#         publication_date_str = item['publication_date']
#         news_publication_date_obj = None

#         if publication_date_str and publication_date_str != "N/A":
#             try:
#                 # O 'Z' no final significa UTC (Zulu time). 
#                 # datetime.fromisoformat lida bem com isso se substituirmos 'Z' por '+00:00'.
#                 if publication_date_str.endswith('Z'):
#                     publication_date_str_adjusted = publication_date_str[:-1] + '+00:00'
#                 else:
#                     # Se não tiver 'Z', pode já ter um offset ou ser naive.
#                     # Para este caso, vamos assumir que se não tem Z, pode precisar de mais tratamento
#                     # ou que já é compatível. A forma mais segura é garantir que ela tenha info de timezone.
#                     # Se as datas do sitemap SEMPRE tiverem 'Z', este 'else' é menos crítico.
#                     publication_date_str_adjusted = publication_date_str

#                 news_publication_date_obj = datetime.fromisoformat(publication_date_str_adjusted)
                
#                 # Garantir que o objeto de data seja timezone-aware (UTC) se fromisoformat não o fizer.
#                 # No entanto, com '+00:00', ele já deve ser.
#                 if news_publication_date_obj.tzinfo is None: # Se for "naive"
#                      news_publication_date_obj = news_publication_date_obj.replace(tzinfo=timezone.utc)


#             except ValueError as ve:
#                 print(f"  AVISO: Não foi possível converter a data de publicação '{publication_date_str}' para {item['original_article_url']}. Erro: {ve}. Pulando filtro de data para este item ou tratando como inválido.")
#                 # Você pode decidir pular o item ou tentar uma conversão mais robusta se necessário
#                 # Por agora, vamos pular a verificação de tempo para este item problemático,
#                 # ou melhor, considerá-lo como não passando no filtro.
#                 # Para segurança, vamos considerar que não passou no filtro se a data é inválida.
#                 news_publication_date_obj = None # Reseta para garantir que não passe
        
#         if not news_publication_date_obj:
#             print(f"  Data de publicação inválida ou ausente. Pulando notícia: {item['title']}")
#             continue # Pula para a próxima notícia

#         # Agora, aplicar o filtro de tempo
#         if news_publication_date_obj >= time_threshold:
#             print(f"  -> Notícia DENTRO do limite de {hours_limit} hora(s). Processando...")
#             processed_count += 1 # Incrementa o contador de notícias processadas
            
#             print(f"Processando notícia: {item['title']}") # Movido para cá
#             print(f"  URL Original: {item['original_article_url']}") # Movido para cá
            
#             article_text = extract_article_text_from_url(item['original_article_url'])

#             if not article_text.strip():
#                 print(f"  Texto do artigo de '{item['original_article_url']}' está vazio ou não pôde ser extraído. Pulando resumo.")
#                 article_summary = "Conteúdo do artigo original não pôde ser extraído."
#             else:
#                 article_summary = summarize_text_with_ollama(article_text)
            
#             summary_data = {
#                 'titulo': item['title'],
#                 'resumo': article_summary,
#                 'link_original': item['original_article_url'],
#                 'fonte': item['source_name'],
#                 'data_publicacao': item['publication_date'], 
#                 'data_extracao': extraction_date_str
#             }
#             all_summaries.append(summary_data)
#         else:
#             print(f"  -> Notícia FORA do limite de {hours_limit} hora(s) (publicada em {news_publication_date_obj.strftime('%Y-%m-%d %H:%M:%S %Z')}). Ignorando.")

#     if processed_count == 0 and len(sitemap_news_items) > 0:
#         print(f"\nNenhuma notícia encontrada dentro do limite de {hours_limit} hora(s) das {len(sitemap_news_items)} notícias verificadas do sitemap.")


#     if not all_summaries:
#         print("Nenhum resumo foi gerado (ou nenhuma notícia passou no filtro de tempo).")
#         return []

#     # Saída dos resultados (permanece igual)
#     if output_format in ['print', 'all']:
#         print("\n--- Resumos das Notícias (Dentro do Limite de Tempo) ---")
#         for summary in all_summaries:
#             print(f"\nTítulo: {summary['titulo']}")
#             print(f"Fonte: {summary['fonte']}")
#             print(f"Link Original: {summary['link_original']}")
#             print(f"Data Publicação: {summary['data_publicacao']}")
#             print(f"Resumo (LLM): {summary['resumo']}")
#             print(f"Data de Extração (Script): {summary['data_extracao']}")
#             print("---")

#     if output_format in ['csv', 'all']:
#         print(f"\nSalvando resumos em {csv_filename}...")
#         try:
#             with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
#                 fieldnames = ['Titulo', 'Resumo', 'Link', 'Fonte', 'DataPublicacao', 'DataExtracao']
#                 writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
#                 writer.writeheader()
#                 for summary in all_summaries:
#                     writer.writerow({
#                         'Titulo': summary['titulo'],
#                         'Resumo': summary['resumo'],
#                         'Link': summary['link_original'],
#                         'Fonte': summary['fonte'],
#                         'DataPublicacao': summary['data_publicacao'],
#                         'DataExtracao': summary['data_extracao']
#                     })
#             print(f"Resumos salvos com sucesso em {csv_filename}")
#         except IOError as e:
#             print(f"Erro ao salvar arquivo CSV: {e}")

#     if output_format == 'list':
#         return all_summaries
    
#     return all_summaries

# if __name__ == '__main__':
#     print(f"Usando modelo Ollama: {OLLAMA_MODEL}")
#     print(f"Processando até {MAX_NEWS_TO_PROCESS} notícias do sitemap.")
    
#     # Exemplo: Salvar em CSV e imprimir no console
#     summarized_news = monitor_and_summarize_crypto_news(
#         output_format='all', 
#         csv_filename='cointelegraph_br_news_summary.csv',
#         hours_limit=10
#     )
    
#     if summarized_news:
#         print(f"\nTotal de {len(summarized_news)} notícias processadas e resumidas.")
#     else:
#         print("\nNenhuma notícia foi processada.")



def testar_api_get(url):
    """
    Função para fazer uma chamada GET a uma API e exibir a resposta.
    """
    print(f"Fazendo chamada GET para: {url}")
    
    try:
        # 1. Fazer a chamada para a API usando requests.get()
        response = requests.get(url)

        # 2. Verificar se a chamada foi bem-sucedida
        # O método raise_for_status() lançará um erro se o status não for 2xx (sucesso).
        response.raise_for_status()
        
        # Se chegamos aqui, a chamada foi um sucesso (Status Code 200 OK)
        print(f"Sucesso! Código de Status: {response.status_code}")

        # 3. Extrair os dados da resposta em formato JSON
        # O método .json() já converte a resposta JSON em um dicionário Python.
        print(response.text)
        dados = response.json()

        # 4. Apresentar os dados de forma legível
        print("\n--- DADOS RECEBIDOS DA API ---")
        # Usamos json.dumps com indent=4 para formatar o dicionário e facilitar a leitura.
        print(json.dumps(dados, indent=4, ensure_ascii=False))

    except requests.exceptions.HTTPError as errh:
        # Erros específicos de HTTP (ex: 404 Not Found, 403 Forbidden)
        print(f"Erro HTTP: {errh}")
        print(f"Código de Status: {response.status_code}")
        print(f"Resposta do servidor: {response.text}")
    except requests.exceptions.RequestException as err:
        # Erros mais genéricos (ex: falha de conexão)
        print(f"Ocorreu um erro na requisição: {err}")

testar_api_get('https://servedbyadbutler.com/adserve/;MID=177750;type=e959fb862;placementID=3026546;setID=514000;channelID=0;CID=1206471;BID=523218361;TAID=0;place=0;rnd=6565509;_abdk_json=%7B%22product%22%3A%22news%22%2C%22domain%22%3A%22br.beincrypto.com%22%7D;referrer=https%3A%2F%2Fbr.beincrypto.com%2Fgary-cardone-compara-noticias-xrp-covid-19%2F;mt=1749605767816456;hc=c1f341a0ce8675dbe5254ff52dbd9d90142269e5')
####para scraping de notícias ==== https://br.beincrypto.com/news-sitemap.xml


# import json
# import time
# from bs4 import BeautifulSoup
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from webdriver_manager.chrome import ChromeDriverManager

# def carregar_html_da_pagina(url):
#     """
#     Usa o Selenium para carregar uma página web dinâmica e retorna seu HTML completo.
#     """
#     print("Iniciando o navegador com Selenium...")
#     options = webdriver.ChromeOptions()
#     options.add_argument('--headless')  # Executa sem abrir uma janela de navegador
#     options.add_argument('--no-sandbox')
#     options.add_argument('--disable-dev-shm-usage')
#     options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

#     service = Service(ChromeDriverManager().install())
#     driver = webdriver.Chrome(service=service, options=options)

#     try:
#         driver.get(url)
#         print(f"Página {url} carregada.")
        
#         # Espera explícita: aguarda até 20 segundos para que o corpo da tabela (tbody) apareça
#         print("Aguardando o conteúdo dinâmico da tabela...")
#         wait = WebDriverWait(driver, 20)
#         wait.until(EC.presence_of_element_located((By.TAG_NAME, 'tbody')))
        
#         # Pequena pausa para garantir que todos os scripts renderizaram
#         time.sleep(2)
        
#         print("Conteúdo carregado. Extraindo o HTML...")
#         return driver.page_source
#     except Exception as e:
#         print(f"Ocorreu um erro ao carregar a página com Selenium: {e}")
#         return None
#     finally:
#         driver.quit()
#         print("Navegador fechado.")


# def extrair_dados_da_tabela(html_completo):
#     """
#     Recebe o HTML completo de uma página e extrai os dados da tabela de moedas.
#     """
#     if not html_completo:
#         print("HTML não foi fornecido. Abortando a extração.")
#         return []

#     soup = BeautifulSoup(html_completo, 'html.parser')
#     lista_de_moedas = []

#     # Encontra o corpo da tabela
#     tabela_body = soup.find('tbody')
#     if not tabela_body:
#         print("Corpo da tabela (tbody) não encontrado.")
#         return []

#     # Encontra todas as linhas de dados (ignorando o anúncio)
#     linhas = tabela_body.find_all('tr', id=lambda x: x and x.startswith('coin-'))
#     print(f"Encontradas {len(linhas)} moedas na tabela.")

#     for linha in linhas:
#         # Usamos seletores de CSS para mais precisão
#         rank = linha.select_one("td:nth-of-type(2)").get_text(strip=True)
#         nome = linha.select_one(".coin-profile__name").get_text(strip=True)
#         simbolo = linha.select_one(".coin-profile__symbol").get_text(strip=True)
#         preco = linha.select_one("real-time-price").get_text(strip=True)
        
#         # O Market Cap tem duas colunas, uma para mobile e outra para desktop. Pegamos a de desktop.
#         market_cap_tag = linha.select_one("td.hidden-tablet-landscape.hidden-mobile")
#         market_cap = market_cap_tag.get_text(strip=True) if market_cap_tag else 'N/A'

#         change_24h_tag = linha.select_one(".change__percentage")
#         change_24h = change_24h_tag.get_text(strip=True) if change_24h_tag else 'N/A'

#         lista_de_moedas.append({
#             'rank': rank,
#             'nome': nome,
#             'simbolo': simbolo,
#             'preco_usd': preco.replace('$', '').strip(),
#             'market_cap': market_cap.replace('$', '').strip(),
#             'variacao_24h_percent': change_24h.replace('+', '').replace('%', '').strip()
#         })
        
#     return lista_de_moedas

# def formatar_mensagem_telegram(lista_de_moedas):
#     """
#     Formata os dados das top 10 moedas para uma mensagem de Telegram.
#     """
#     if not lista_de_moedas:
#         return "Não foi possível obter os dados das moedas no momento."

#     # 1. Seleciona as 10 primeiras moedas
#     top_10 = lista_de_moedas[:10]
    
#     # 2. Constrói a mensagem
#     # O asterisco (*) deixa o texto em negrito no Telegram
#     mensagem = ["🏆 *Top 10 Cripto Gainers do Dia* 🚀\n"]
    
#     # Adiciona o cabeçalho da tabela dentro de um bloco de código (```) para ser monoespaçado
#     mensagem.append("```")
#     mensagem.append(f"{'#':<3} {'Símbolo':<8} {'Preço (USD)':<15} {'Variação 24h'}")
#     mensagem.append(f"{'-'*3} {'-'*8} {'-'*15} {'-'*14}")

#     # 3. Adiciona cada moeda à mensagem
#     for moeda in top_10:
#         try:
#             rank = moeda['rank']
#             simbolo = moeda['simbolo']
#             # Converte para float para formatar e tratar erros
#             preco = float(moeda['preco_usd'])
#             variacao = float(moeda['variacao_24h_percent'])
            
#             # Formata cada linha garantindo o alinhamento
#             # :<3 -> alinha à esquerda com 3 caracteres de espaço
#             # :>8.2f -> alinha à direita com 8 caracteres, 2 casas decimais
#             linha = (f"{rank:<3} {simbolo:<8} ${preco:<14,.6f} {variacao:>+7.2f}% 🟢")
#             mensagem.append(linha)
#         except (ValueError, TypeError):
#             # Se algum dado não puder ser convertido, pula para o próximo
#             continue
            
#     mensagem.append("```") # Fecha o bloco de código

#     # 4. Adiciona um rodapé com a data e hora
#     agora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
#     fonte = "Coinranking.com"
#     # O underline (_) deixa o texto em itálico no Telegram
#     mensagem.append(f"\n_Atualizado em: {agora}_")
#     mensagem.append(f"🔗 _Fonte: {fonte}_")
#     # 5. Junta todas as partes em uma única string de mensagem
#     return "\n".join(mensagem)

# if __name__ == "__main__":
#     url_alvo = "https://coinranking.com/coins/gainers"
    
#     # Passo 1: Usar Selenium para obter o HTML completo
#     html_da_pagina = carregar_html_da_pagina(url_alvo)
    
#     # Passo 2: Usar BeautifulSoup para extrair os dados do HTML
#     if html_da_pagina:
#         dados_finais = extrair_dados_da_tabela(html_da_pagina)
        
#         if dados_finais:
#             print("\n--- DADOS EXTRAÍDOS COM SUCESSO ---\n")
#             # Imprime os resultados de forma legível
#             print(json.dumps(dados_finais, indent=4))
#             print(f"\nTotal de {len(dados_finais)} moedas extraídas.")
#             # Gera a mensagem para o Telegram
#             mensagem_formatada = formatar_mensagem_telegram(dados_finais)
            
#             print("\n--- MENSAGEM PRONTA PARA ENVIAR AO TELEGRAM ---\n")
#             print(mensagem_formatada)
#         else:
#             print("Nenhum dado de moeda foi extraído.")

# import json
# import time
# from bs4 import BeautifulSoup
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from webdriver_manager.chrome import ChromeDriverManager
# from datetime import datetime

# class ScraperCoinranking:
#     """
#     Uma classe para fazer scraping da página de 'gainers' do Coinranking
#     e formatar um relatório para o Telegram.
#     """
#     def __init__(self, url='https://coinranking.com/coins/gainers'):
#         """
#         O construtor da classe. É executado quando criamos um novo objeto.
#         """
#         self.url = url
#         print(f"ScraperTelegram inicializado para a URL: {self.url}")

#     def _carregar_html_da_pagina(self):
#         # Este método é "privado" (convenção do underscore _),
#         # pois só precisa ser usado dentro desta classe.
#         print("Iniciando o navegador com Selenium...")
#         options = webdriver.ChromeOptions()
#         options.add_argument('--headless')
#         options.add_argument('--no-sandbox')
#         options.add_argument('--disable-dev-shm-usage')
#         service = Service(ChromeDriverManager().install())
#         driver = webdriver.Chrome(service=service, options=options)
#         try:
#             driver.get(self.url)
#             print(f"Página {self.url} carregada.")
#             wait = WebDriverWait(driver, 20)
#             wait.until(EC.presence_of_element_located((By.TAG_NAME, 'tbody')))
#             time.sleep(2)
#             print("Conteúdo carregado. Extraindo o HTML...")
#             return driver.page_source
#         except Exception as e:
#             print(f"Ocorreu um erro ao carregar a página com Selenium: {e}")
#             return None
#         finally:
#             driver.quit()
#             print("Navegador fechado.")

#     def _extrair_dados_da_tabela(self, html_completo):
#         # Este método também é para uso interno.
#         if not html_completo: return []
#         soup = BeautifulSoup(html_completo, 'html.parser')
#         # ... (lógica de extração completa como antes) ...
#         lista_de_moedas = []
#         tabela_body = soup.find('tbody')
#         if not tabela_body: return []
#         linhas = tabela_body.find_all('tr', id=lambda x: x and x.startswith('coin-'))
#         print(f"Encontradas {len(linhas)} moedas na tabela.")
#         for linha in linhas:
#             rank = linha.select_one("td:nth-of-type(2)").get_text(strip=True)
#             nome = linha.select_one(".coin-profile__name").get_text(strip=True)
#             simbolo = linha.select_one(".coin-profile__symbol").get_text(strip=True)
#             preco = linha.select_one("real-time-price").get_text(strip=True)
#             market_cap_tag = linha.select_one("td.hidden-tablet-landscape.hidden-mobile")
#             market_cap = market_cap_tag.get_text(strip=True) if market_cap_tag else 'N/A'
#             change_24h_tag = linha.select_one(".change__percentage")
#             change_24h = change_24h_tag.get_text(strip=True) if change_24h_tag else 'N/A'
#             lista_de_moedas.append({
#                 'rank': rank, 'nome': nome, 'simbolo': simbolo,
#                 'preco_usd': preco.replace('$', '').strip(),
#                 'market_cap': market_cap.replace('$', '').strip(),
#                 'variacao_24h_percent': change_24h.replace('+', '').replace('%', '').strip()
#             })
#         return lista_de_moedas

#     def formatar_mensagem_telegram(self, lista_de_moedas, tipo_relatorio="gainers"):
#         """
#         Formata os dados das top 10 moedas para uma mensagem de Telegram,
#         adaptando-se para 'gainers' ou 'losers'.
#         """
#         if not lista_de_moedas:
#             return f"Não foi possível obter os dados para o relatório de '{tipo_relatorio}'."

#         top_10 = lista_de_moedas[:10]
        
#         # 1. Define o título e emoji principal baseado no tipo de relatório
#         if tipo_relatorio.lower() == "losers":
#             titulo_mensagem = "📉 *Top 10 Cripto Losers do Dia* 💔"
#         else: # O padrão é 'gainers'
#             titulo_mensagem = "🏆 *Top 10 Cripto Gainers do Dia* 🚀"
        
#         mensagem = [titulo_mensagem + "\n"]
        
#         # Cabeçalho da tabela
#         mensagem.append("```")
#         mensagem.append(f"{'#':<3} {'Símbolo':<8} {'Preço (USD)':<15} {'Variação 24h'}")
#         mensagem.append(f"{'-'*3} {'-'*8} {'-'*15} {'-'*14}")

#         # 2. Adiciona cada moeda à mensagem
#         for moeda in top_10:
#             try:
#                 rank = moeda['rank']
#                 simbolo = moeda['simbolo']
#                 preco = float(moeda['preco_usd'])
#                 variacao = float(moeda['variacao_24h_percent'])
                
#                 # 3. Escolhe o emoji correto para a variação
#                 emoji_variacao = "🟢" if variacao >= 0 else "🔴"
                
#                 # Formata a linha. O f-string `+7.2f` já lida com o sinal de '+' ou '-'.
#                 linha = (f"{rank:<3} {simbolo:<8} ${preco:<14,.6f} {variacao:>+7.2f}% {emoji_variacao}")
#                 mensagem.append(linha)
#             except (ValueError, TypeError):
#                 continue
                
#         mensagem.append("```")

#         # Rodapé
#         agora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
#         # Ajustamos a fonte para ser genérica, pois a classe pode ter URLs diferentes
#         mensagem.append(f"\n_Atualizado em: {agora}_")
#         mensagem.append(f"🔗 _Fonte: Coinranking_")

#         return "\n".join(mensagem)

#     # ---- O MÉTODO PÚBLICO E ORQUESTRADOR ----
#     def gerar_relatorio_telegram(self):
#         """
#         Este é o único método que precisa ser chamado de fora.
#         Ele orquestra todo o processo.
#         """
#         print("\n--- INICIANDO PROCESSO COMPLETO DE GERAÇÃO DE RELATÓRIO ---")
        
#         # 1. Carregar a página
#         html = self._carregar_html_da_pagina()
#         if not html:
#             return "Falha ao carregar a página. Relatório não pode ser gerado."

#         # 2. Extrair os dados
#         dados = self._extrair_dados_da_tabela(html)
#         if not dados:
#             return "Falha ao extrair dados. Relatório não pode ser gerado."
        
#         # 3. extrair o texto da url
#         parsed_url = urlparse(self.url)
#         caminho = parsed_url.path
#         tipo = [p for p in caminho.split('/') if p][-1]
#         # 4. Formatar a mensagem

#         mensagem_final = self.formatar_mensagem_telegram(dados, tipo)
        
#         print("--- PROCESSO FINALIZADO COM SUCESSO ---")
#         return mensagem_final

# # --- COMO USAR A CLASSE NO SEU SCRIPT MAIOR ---
# if __name__ == "__main__":
#     tipo = ['gainers', 'losers']

#     for t in tipo:
#         url = f"https://coinranking.com/coins/{t}"
        
#         # 2. Crie uma instância da sua classe
#         meu_scraper = ScraperCoinranking(url=url)
        
#         # 3. Chame APENAS o método orquestrador
#         relatorio_final = meu_scraper.gerar_relatorio_telegram()

#         # 4. Use o resultado
#         print(f"\n--- MENSAGEM FINAL PRONTA PARA ENVIAR TIPO {t.upper()} ---")
#         print(relatorio_final)