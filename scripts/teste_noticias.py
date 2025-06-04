import requests
from bs4 import BeautifulSoup
import ollama
import csv
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
from datetime import datetime, timezone, timedelta

# Configurações
COINTELEGRAPH_SITEMAP_URL = "https://cointelegraph.com/sitemap-google-news.xml"
# Certifique-se que este modelo está disponível no seu Ollama (`ollama list`)
OLLAMA_MODEL = "gemma3:12b" 
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
# Limitar o número de notícias para processamento (para fins de demonstração/teste)
MAX_NEWS_TO_PROCESS = 20 # Aumentado um pouco para testar mais artigos do sitemap

def get_news_from_cointelegraph_sitemap():
    """
    Busca o sitemap de notícias do Cointelegraph Brasil e extrai
    informações sobre os artigos.
    Retorna uma lista de dicionários, cada um com 'title', 'original_article_url', 
    'publication_date', e 'source_name'.
    """
    print(f"Buscando notícias do Cointelegraph em: {COINTELEGRAPH_SITEMAP_URL}")
    news_items = []
    try:
        response = requests.get(COINTELEGRAPH_SITEMAP_URL, headers=REQUEST_HEADERS)
        response.raise_for_status()
        
        # Usar 'xml' ou 'lxml-xml' como parser para arquivos XML
        soup = BeautifulSoup(response.content, 'xml')

        # O sitemap contém múltiplas tags <url>
        url_tags = soup.find_all('url')
        
        count = 0
        for url_tag in url_tags:
            loc_tag = url_tag.find('loc')
            news_tag = url_tag.find('news:news') # Acessa o namespace news

            if loc_tag and news_tag:
                original_article_url = loc_tag.get_text(strip=True)
                
                title_tag = news_tag.find('news:title')
                publication_date_tag = news_tag.find('news:publication_date')
                publication_tag = news_tag.find('news:publication')
                
                title = title_tag.get_text(strip=True) if title_tag else "N/A"
                # Formatar a data para um formato mais legível, se desejado.
                # O formato original é ISO 8601. Ex: 2025-05-27T18:20:00.000Z
                publication_date_str = publication_date_tag.get_text(strip=True) if publication_date_tag else "N/A"
                
                source_name = "COINTELEGRAPH" # Padrão, mas podemos pegar do XML se preferir
                if publication_tag:
                    name_tag = publication_tag.find('news:name')
                    if name_tag:
                        source_name = name_tag.get_text(strip=True)
                
                news_items.append({
                    'title': title,
                    'original_article_url': original_article_url,
                    'publication_date': publication_date_str,
                    'source_name': source_name
                })
                count += 1
                if count >= MAX_NEWS_TO_PROCESS: # Limitar o número de notícias
                    break
        
        if not news_items:
            print("Nenhum item de notícia encontrado no sitemap. Verifique o URL ou a estrutura do XML.")

    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar sitemap do Cointelegraph: {e}")
    except Exception as e:
        print(f"Erro ao processar o sitemap XML: {e}")
    return news_items

def extract_article_text_from_url(article_url):
    """
    Extrai o texto principal de um URL de artigo de notícias.
    Esta é uma função genérica e pode não funcionar perfeitamente para todos os sites.
    """
    print(f"    Extraindo texto de: {article_url}")
    try:
        response = requests.get(article_url, headers=REQUEST_HEADERS, timeout=15) # Aumentado timeout
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Seletores comuns para conteúdo de artigo no Cointelegraph (podem mudar)
        # O Cointelegraph usa classes como 'post-content', 'post__content'
        main_content_tags = [
            'div.post-content', 
            'div.post__content', 
            'article.post__article', # Mais específico para o article
            'article', # Genérico
            'main' # Genérico
        ]
        content_html = None
        for tag_selector in main_content_tags:
            if '.' in tag_selector or '#' in tag_selector or '[' in tag_selector: # Seletor CSS complexo
                content_html = soup.select_one(tag_selector)
            else: # Seletor de tag simples
                content_html = soup.find(tag_selector)
            
            if content_html:
                print(f"      Container de conteúdo encontrado com seletor: '{tag_selector}'")
                break
        
        if not content_html: # Fallback para o body se nada específico for encontrado
            print("      Nenhum container de conteúdo principal específico encontrado, tentando body...")
            content_html = soup.body

        if not content_html:
             print(f"      Não foi possível encontrar o container principal de conteúdo em {article_url}")
             return ""

        # Remover elementos indesejados (scripts, styles, menus, etc.) antes de extrair texto
        for unwanted_tag in content_html(['script', 'style', 'nav', 'header', 'footer', 'aside', '.related-articles', '.social-share']):
            unwanted_tag.decompose()

        # Extrair texto de parágrafos <p> dentro do conteúdo principal
        paragraphs = content_html.find_all('p')
        article_text = "\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]) # Evitar parágrafos vazios
        
        if not article_text.strip(): # Se não houver parágrafos, tentar pegar todo o texto do container
            print("      Nenhum parágrafo encontrado no container, tentando texto geral do container.")
            article_text = content_html.get_text(separator='\n', strip=True)

        # Limpeza adicional (opcional)
        article_text = "\n".join([line for line in article_text.splitlines() if line.strip()])

        if not article_text.strip():
            print(f"Texto extraído de {article_url} está vazio após tentativas.")
        
        return article_text

    except requests.exceptions.Timeout:
        print(f"    Timeout ao extrair texto de {article_url}")
    except requests.exceptions.RequestException as e:
        print(f"    Erro de requisição ao extrair texto de {article_url}: {e}")
    except Exception as e:
        print(f"    Erro inesperado ao processar {article_url} para extração de texto: {e}")
    return ""

def summarize_text_with_ollama(text, model_name=OLLAMA_MODEL):
    """
    Envia o texto para o Ollama para resumo e análise de sentimento.
    """
    if not text or not text.strip():
        print("Texto vazio fornecido para resumo. Pulando.")
        return "Não foi possível extrair conteúdo para resumo."

    print(f"      Enviando texto para o modelo Ollama '{model_name}' para resumo...")
    
    # Prompt ajustado para ser mais direto
    prompt = f"""Por favor, resuma o seguinte texto de notícia em português, em aproximadamente 3 frases.
O resumo deve focar em identificar o sentimento predominante (positivo, negativo ou neutro) expresso no texto.
Se o texto for muito curto, irrelevante ou não for uma notícia financeira/cripto, indique isso.

Texto da notícia:
---
{text[:5000]} 
---
Resumo Conciso e Sentimento:""" # Limitar o tamanho do prompt para Ollama

    try:
        response_ollama = ollama.generate(
            model=model_name,
            prompt=prompt,
            # options={"temperature": 0.5} # Exemplo de opção, ajuste conforme necessário
        )
        summary = response_ollama['response'].strip()
        print(f"      Resumo recebido: {summary}")
        return summary
    except Exception as e:
        print(f"      Erro ao comunicar com Ollama ou gerar resumo: {e}")
        print(f"      Verifique se o Ollama está rodando e o modelo '{model_name}' está disponível ('ollama list').")
        return "Erro ao gerar resumo via Ollama."

def monitor_and_summarize_crypto_news(output_format='print', csv_filename='crypto_news_summary.csv', hours_limit=2): # Adicionado hours_limit
    """
    Função principal para monitorar, extrair, resumir notícias e apresentar/salvar os resultados.
    Processa apenas notícias publicadas dentro do 'hours_limit' especificado.
    output_format pode ser 'print', 'csv', 'list', ou 'all'.
    """
    print(f"Iniciando monitoramento e resumo de notícias cripto (Fonte: Cointelegraph Sitemap)...")
    print(f"Processando notícias publicadas nas últimas {hours_limit} hora(s).") # Feedback para o usuário

    sitemap_news_items = get_news_from_cointelegraph_sitemap()

    # print(f"DEBUG: Total de notícias lidas do sitemap AGORA: {len(sitemap_news_items)}") # Verifique este número!
    # if sitemap_news_items:
    #     print(f"DEBUG: Primeira notícia do sitemap (após modificação): '{sitemap_news_items[0]['title']}' Data: {sitemap_news_items[0]['publication_date']}")
    #     # Vamos imprimir as datas de várias notícias para análise
    #     print("DEBUG: Listando algumas datas de publicação das notícias lidas do sitemap:")
    #     for i, news_item in enumerate(sitemap_news_items[:50]): # Veja as primeiras 50, por exemplo
    #         print(f"  Item {i}: Data {news_item['publication_date']}")
    #     if len(sitemap_news_items) > 50: # Se houver mais, veja algumas do final também
    #          print("DEBUG: Listando algumas datas do FINAL da lista do sitemap:")
    #          for i, news_item in enumerate(sitemap_news_items[-10:]): # Veja as últimas 10 da lista lida
    #             print(f"  Item {len(sitemap_news_items) - 10 + i}: Data {news_item['publication_date']}")
    # else:
    #     print("DEBUG: Nenhuma notícia foi retornada pelo get_news_from_cointelegraph_sitemap.")

    if not sitemap_news_items:
        print("Nenhuma notícia encontrada no sitemap do Cointelegraph para processar.")
        return []

    all_summaries = []
    # Usar UTC para data de extração para consistência
    extraction_datetime_utc = datetime.now(timezone.utc)
    print(f'Horário atual (UTC): {extraction_datetime_utc}')
    extraction_date_str = extraction_datetime_utc.strftime('%Y-%m-%d %H:%M:%S %Z')

    # Calcular o ponto de corte no tempo (X horas atrás a partir de agora em UTC)
    time_threshold = extraction_datetime_utc - timedelta(hours=hours_limit)
    print(f"Filtrando notícias publicadas após: {time_threshold.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    processed_count = 0 # Contador para notícias que passam no filtro de tempo

    for item in sitemap_news_items:
        print(f"\nVerificando notícia: {item['title']}")
        print(f"  Data de Publicação (do sitemap): {item['publication_date']}")

        # Converter a string de data de publicação para um objeto datetime
        # O formato da data do sitemap é ISO 8601 (ex: 2024-05-15T14:30:00Z)
        publication_date_str = item['publication_date']
        news_publication_date_obj = None

        if publication_date_str and publication_date_str != "N/A":
            try:
                # O 'Z' no final significa UTC (Zulu time). 
                # datetime.fromisoformat lida bem com isso se substituirmos 'Z' por '+00:00'.
                if publication_date_str.endswith('Z'):
                    publication_date_str_adjusted = publication_date_str[:-1] + '+00:00'
                else:
                    # Se não tiver 'Z', pode já ter um offset ou ser naive.
                    # Para este caso, vamos assumir que se não tem Z, pode precisar de mais tratamento
                    # ou que já é compatível. A forma mais segura é garantir que ela tenha info de timezone.
                    # Se as datas do sitemap SEMPRE tiverem 'Z', este 'else' é menos crítico.
                    publication_date_str_adjusted = publication_date_str

                news_publication_date_obj = datetime.fromisoformat(publication_date_str_adjusted)
                
                # Garantir que o objeto de data seja timezone-aware (UTC) se fromisoformat não o fizer.
                # No entanto, com '+00:00', ele já deve ser.
                if news_publication_date_obj.tzinfo is None: # Se for "naive"
                     news_publication_date_obj = news_publication_date_obj.replace(tzinfo=timezone.utc)


            except ValueError as ve:
                print(f"  AVISO: Não foi possível converter a data de publicação '{publication_date_str}' para {item['original_article_url']}. Erro: {ve}. Pulando filtro de data para este item ou tratando como inválido.")
                # Você pode decidir pular o item ou tentar uma conversão mais robusta se necessário
                # Por agora, vamos pular a verificação de tempo para este item problemático,
                # ou melhor, considerá-lo como não passando no filtro.
                # Para segurança, vamos considerar que não passou no filtro se a data é inválida.
                news_publication_date_obj = None # Reseta para garantir que não passe
        
        if not news_publication_date_obj:
            print(f"  Data de publicação inválida ou ausente. Pulando notícia: {item['title']}")
            continue # Pula para a próxima notícia

        # Agora, aplicar o filtro de tempo
        if news_publication_date_obj >= time_threshold:
            print(f"  -> Notícia DENTRO do limite de {hours_limit} hora(s). Processando...")
            processed_count += 1 # Incrementa o contador de notícias processadas
            
            print(f"Processando notícia: {item['title']}") # Movido para cá
            print(f"  URL Original: {item['original_article_url']}") # Movido para cá
            
            article_text = extract_article_text_from_url(item['original_article_url'])

            if not article_text.strip():
                print(f"  Texto do artigo de '{item['original_article_url']}' está vazio ou não pôde ser extraído. Pulando resumo.")
                article_summary = "Conteúdo do artigo original não pôde ser extraído."
            else:
                article_summary = summarize_text_with_ollama(article_text)
            
            summary_data = {
                'titulo': item['title'],
                'resumo': article_summary,
                'link_original': item['original_article_url'],
                'fonte': item['source_name'],
                'data_publicacao': item['publication_date'], 
                'data_extracao': extraction_date_str
            }
            all_summaries.append(summary_data)
        else:
            print(f"  -> Notícia FORA do limite de {hours_limit} hora(s) (publicada em {news_publication_date_obj.strftime('%Y-%m-%d %H:%M:%S %Z')}). Ignorando.")

    if processed_count == 0 and len(sitemap_news_items) > 0:
        print(f"\nNenhuma notícia encontrada dentro do limite de {hours_limit} hora(s) das {len(sitemap_news_items)} notícias verificadas do sitemap.")


    if not all_summaries:
        print("Nenhum resumo foi gerado (ou nenhuma notícia passou no filtro de tempo).")
        return []

    # Saída dos resultados (permanece igual)
    if output_format in ['print', 'all']:
        print("\n--- Resumos das Notícias (Dentro do Limite de Tempo) ---")
        for summary in all_summaries:
            print(f"\nTítulo: {summary['titulo']}")
            print(f"Fonte: {summary['fonte']}")
            print(f"Link Original: {summary['link_original']}")
            print(f"Data Publicação: {summary['data_publicacao']}")
            print(f"Resumo (LLM): {summary['resumo']}")
            print(f"Data de Extração (Script): {summary['data_extracao']}")
            print("---")

    if output_format in ['csv', 'all']:
        print(f"\nSalvando resumos em {csv_filename}...")
        try:
            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['Titulo', 'Resumo', 'Link', 'Fonte', 'DataPublicacao', 'DataExtracao']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for summary in all_summaries:
                    writer.writerow({
                        'Titulo': summary['titulo'],
                        'Resumo': summary['resumo'],
                        'Link': summary['link_original'],
                        'Fonte': summary['fonte'],
                        'DataPublicacao': summary['data_publicacao'],
                        'DataExtracao': summary['data_extracao']
                    })
            print(f"Resumos salvos com sucesso em {csv_filename}")
        except IOError as e:
            print(f"Erro ao salvar arquivo CSV: {e}")

    if output_format == 'list':
        return all_summaries
    
    return all_summaries

if __name__ == '__main__':
    print(f"Usando modelo Ollama: {OLLAMA_MODEL}")
    print(f"Processando até {MAX_NEWS_TO_PROCESS} notícias do sitemap.")
    
    # Exemplo: Salvar em CSV e imprimir no console
    summarized_news = monitor_and_summarize_crypto_news(
        output_format='all', 
        csv_filename='cointelegraph_br_news_summary.csv',
        hours_limit=10
    )
    
    if summarized_news:
        print(f"\nTotal de {len(summarized_news)} notícias processadas e resumidas.")
    else:
        print("\nNenhuma notícia foi processada.")