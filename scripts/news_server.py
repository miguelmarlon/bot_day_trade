import requests
import ollama
import csv
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
from datetime import datetime, timezone, timedelta
import pandas as pd
import ollama
import csv
from datetime import datetime, timezone, timedelta
import time
import logging
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, urljoin
import asyncio
import os
import telegram
from dotenv import load_dotenv
import re
import json
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime

#Configuração necessária para a class EconomicEvents
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NewsProcessor:
    """
    Uma classe para buscar, processar, resumir e analisar o sentimento de notícias
    de uma fonte específica (inicialmente Cointelegraph).
    """

    # Atributo de classe para headers padrão de requisição
    DEFAULT_REQUEST_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    def __init__(self,
                 sitemap_url="https://cointelegraph.com/sitemap-google-news.xml",
                 ollama_model="gemma3:12b", # Atualizado conforme seu código
                 max_news_to_process=1,
                 request_headers=None):
        """
        Inicializa o processador de notícias.

        Args:
            sitemap_url (str): URL do sitemap XML para buscar as notícias.
            ollama_model (str): Nome do modelo Ollama a ser usado para resumo e sentimento.
            max_news_to_process (int): Número máximo de notícias a serem processadas do sitemap.
            request_headers (dict, optional): Headers HTTP para as requisições. 
                                              Usa DEFAULT_REQUEST_HEADERS se None.
        """
        self.sitemap_url = sitemap_url
        self.ollama_model = ollama_model
        self.max_news_to_process = max_news_to_process
        self.request_headers = request_headers if request_headers else self.DEFAULT_REQUEST_HEADERS
        
        print(f"NewsProcessor inicializado com:")
        print(f"  Sitemap URL: {self.sitemap_url}")
        print(f"  Ollama Model: {self.ollama_model}")
        print(f"  Max News to Process: {self.max_news_to_process}")

    def _get_news_from_sitemap(self):
        """
        Busca o sitemap de notícias e extrai informações sobre os artigos.
        Interno à classe, usa atributos de instância.

        Retorna:
            list: Uma lista de dicionários, cada um com 'title', 'original_article_url', 
                  'publication_date', e 'source_name'.
        """
        print(f"Buscando notícias em: {self.sitemap_url}")
        news_items = []
        try:
            response = requests.get(self.sitemap_url, headers=self.request_headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'xml')
            url_tags = soup.find_all('url')
            
            count = 0
            for url_tag in url_tags:
                loc_tag = url_tag.find('loc')
                news_tag = url_tag.find('news:news')

                if loc_tag and news_tag:
                    original_article_url = loc_tag.get_text(strip=True)
                    
                    title_tag = news_tag.find('news:title')
                    publication_date_tag = news_tag.find('news:publication_date')
                    publication_tag = news_tag.find('news:publication') # Para o nome da fonte
                    
                    title = title_tag.get_text(strip=True) if title_tag else "N/A"
                    publication_date_str = publication_date_tag.get_text(strip=True) if publication_date_tag else "N/A"
                    
                    source_name = "COINTELEGRAPH" # Padrão
                    if publication_tag:
                        name_tag = publication_tag.find('news:name')
                        if name_tag:
                            source_name = name_tag.get_text(strip=True)
                    
                    news_items.append({
                        'title': title,
                        'original_article_url': original_article_url,
                        'publication_date': publication_date_str,
                        'source_name': source_name # Usando o nome da fonte do sitemap se disponível
                    })
                    count += 1
                    if count >= self.max_news_to_process:
                        print(f"Limite de {self.max_news_to_process} notícias atingido no sitemap.")
                        break
            
            if not news_items:
                print("Nenhum item de notícia encontrado no sitemap. Verifique o URL ou a estrutura do XML.")

        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar sitemap: {e}")
        except Exception as e:
            print(f"Erro ao processar o sitemap XML: {e}")
        return news_items

    def _extract_article_text_from_url(self, article_url):
        """
        Extrai o texto principal de um URL de artigo de notícias.
        Interno à classe.

        Args:
            article_url (str): O URL do artigo.

        Returns:
            str: O texto extraído do artigo.
        """
        print(f"    Extraindo texto de: {article_url}")
        try:
            response = requests.get(article_url, headers=self.request_headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            main_content_tags = [
                'div.post-content', 'div.post__content', 'article.post__article',
                'article', 'main'
            ]
            content_html = None
            for tag_selector in main_content_tags:
                if '.' in tag_selector or '#' in tag_selector or '[' in tag_selector:
                    content_html = soup.select_one(tag_selector)
                else:
                    content_html = soup.find(tag_selector)
                
                if content_html:
                    print(f"      Container de conteúdo encontrado com seletor: '{tag_selector}'")
                    break
            
            if not content_html:
                print("      Nenhum container de conteúdo principal específico encontrado, tentando body...")
                content_html = soup.body

            if not content_html:
                print(f"      Não foi possível encontrar o container principal de conteúdo em {article_url}")
                return ""

            for unwanted_tag in content_html(['script', 'style', 'nav', 'header', 'footer', 'aside', '.related-articles', '.social-share']):
                unwanted_tag.decompose()

            paragraphs = content_html.find_all('p')
            article_text = "\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            
            if not article_text.strip():
                print("      Nenhum parágrafo encontrado no container, tentando texto geral do container.")
                article_text = content_html.get_text(separator='\n', strip=True)

            article_text = "\n".join([line for line in article_text.splitlines() if line.strip()])

            if not article_text.strip():
                print(f"      Texto extraído de {article_url} está vazio após tentativas.")
            else:
                print(f"      Texto extraído (primeiros 200 chars): {article_text[:200]}...")
            
            return article_text

        except requests.exceptions.Timeout:
            print(f"    Timeout ao extrair texto de {article_url}")
        except requests.exceptions.RequestException as e:
            print(f"    Erro de requisição ao extrair texto de {article_url}: {e}")
        except Exception as e:
            print(f"    Erro inesperado ao processar {article_url} para extração de texto: {e}")
        return ""

    def _summarize_and_analyze_with_ollama(self, text):
        """
        Envia o texto para o Ollama para resumo e análise de sentimento.
        Interno à classe, usa self.ollama_model.

        Args:
            text (str): O texto a ser resumido e analisado.

        Returns:
            tuple: (resumo, sentimento) ou (mensagem_de_erro_resumo, "N/A")
        """
        if not text or not text.strip():
            print("    Texto vazio fornecido para resumo. Pulando.")
            return "Não foi possível extrair conteúdo para resumo.", "N/A"

        print(f"      Enviando texto para o modelo Ollama '{self.ollama_model}' para resumo e sentimento...")
        
        prompt_resumo = f"""Por favor, resuma o seguinte texto de notícia em português, em aproximadamente 3 frases.
                            O resumo deve ser pronto para ser postado em um canal de rede social.
                            Se o texto for muito curto, irrelevante ou não for uma notícia financeira/cripto, indique isso com uma mensagem de erro: "ERRO!".

                            Texto da notícia:
                            ---
                            {text[:5000]} 
                            ---"""
        resumo = "ERRO! Falha ao gerar resumo inicial."
        sentimento = "N/A" # Valor padrão

        try:
            response_resumo = ollama.generate(
                model=self.ollama_model,
                prompt=prompt_resumo,
                options={"temperature": 0.3}
            )
            resumo = response_resumo['response'].strip()
            
            if not resumo or "ERRO!" in resumo: # Verificando se o resumo indica um erro
                print("Resumo inválido ou erro detectado pelo modelo. Não prosseguindo para análise de sentimento.")
                return resumo if resumo else "ERRO! O texto não é relevante ou não pôde ser resumido adequadamente.", "N/A"
            else:
                prompt_editor = f"""
                        Você é um editor de conteúdos experiente, especializado em criar posts altamente engajadores para redes sociais.

                        Sua tarefa é analisar o texto fornecido abaixo e transformá-lo em um post otimizado e pronto para ser publicado no aplicativo Telegram. O objetivo é maximizar a clareza, o engajamento e a facilidade de leitura.

                        Instruções Detalhadas:
                        1.  **Linguagem e Tom:** Utilize português do Brasil. O tom deve ser amigável. Adapte a linguagem para ser de fácil entendimento pelo público geral.
                        2.  **Sem Título:** O post final NÃO deve conter um título explícito.
                        3.  **Estrutura e Formato:**
                            * Divida o texto em parágrafos curtos para facilitar a leitura em dispositivos móveis.
                            * Use 1 emojis relevantes para tornar o post mais visual e expressivo.
                        4.  **Engajamento:**
                            * Caso a notícia envolva algum criptomoeda use uma hashtag com o nome dela.
                        5.  **Conteúdo e Alterações:**
                            * Preserve a mensagem central e as informações mais importantes do texto.
                            * Realize as alterações necessárias para melhorar a fluidez, concisão e impacto do texto. Corrija eventuais erros gramaticais ou ortográficos.
                        6.  **Resultado Final:** Apresente apenas a versão final do texto do post. Se houver múltiplas formas de reescrever, escolha aquela que for mais coerente, impactante e de fácil entendimento.

                        Texto a ser transformado:
                        {resumo}"""
                
                response_resumo_editor = ollama.generate(
                model=self.ollama_model,
                prompt=prompt_editor,
                options={"temperature": 0.3}
                )
                resumo_final = response_resumo_editor['response'].strip()
                print(f"Resumo recebido: {resumo_final}")

            # Se o resumo foi bem-sucedido, prossegue para análise de sentimento
            prompt_sentimento = f"""Você é um analista de sentimento especializado em notícias. Sua tarefa é ler o resumo da notícia fornecida abaixo e classificar o sentimento predominante nele em uma escala numérica de 0 a 10.

                                Considere a seguinte escala para sua avaliação:
                                * **0:** Notícia extremamente negativa, péssima, desastrosa.
                                * **1-2:** Notícia muito negativa.
                                * **3-4:** Notícia negativa.
                                * **5:** Notícia neutra ou mista.
                                * **6-7:** Notícia positiva.
                                * **8-9:** Notícia muito positiva.
                                * **10:** Notícia extremamente positiva, excelente.

                                Analise cuidadosamente o conteúdo do resumo abaixo. Forneça **apenas o número** da sua avaliação (0-10).

                                Resumo da notícia:
                                "{resumo_final}"

                                Avaliação (0-10):"""

            response_sentimento = ollama.generate(
                model=self.ollama_model, # Pode usar o mesmo modelo ou um específico para classificação
                prompt=prompt_sentimento,
                options={"temperature": 0.1} # Temperatura muito baixa para classificação precisa
            )
            sentimento = response_sentimento['response'].strip()
            print(f"      Sentimento recebido: {sentimento}")
            # Validar se o sentimento é um número, opcionalmente
            try:
                int(sentimento) # Apenas para verificar se é conversível
            except ValueError:
                print(f"AVISO: Sentimento recebido não é um número simples: '{sentimento}'. Usando como está.")

            return resumo_final, sentimento
        
        except Exception as e:
            print(f"      Erro ao comunicar com Ollama: {e}")
            print(f"      Verifique se o Ollama está rodando e o modelo '{self.ollama_model}' está disponível ('ollama list').")
            return "Erro ao gerar resumo/sentimento via Ollama.", sentimento # Retorna o sentimento que pode ter sido obtido, ou N/A

    def _save_summaries_to_csv(self, summaries, csv_filename):
        """Salva uma lista de resumos em um arquivo CSV."""
        if not summaries:
            print("Nenhum resumo para salvar em CSV.")
            return
            
        print(f"\nSalvando resumos em {csv_filename}...")
        try:
            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                # Corrigindo para corresponder às chaves do dicionário summary_data
                fieldnames = ['Titulo', 'Resumo', 'Link Original', 'Fonte', 'Data Publicacao', 'Data Extracao', 'Sentimento']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for summary in summaries:
                    # Mapeamento para garantir que as chaves do CSV sejam preenchidas corretamente
                    writer.writerow({
                        'Titulo': summary.get('titulo'),
                        'Resumo': summary.get('resumo'),
                        'Link Original': summary.get('link_original'),
                        'Fonte': summary.get('fonte'),
                        'Data Publicacao': summary.get('data_publicacao'),
                        'Data Extracao': summary.get('data_extracao'),
                        'Sentimento': summary.get('sentimento', "N/A") # Pega 'sentimento' ou default
                    })
            print(f"Resumos salvos com sucesso em {csv_filename}")
        except IOError as e:
            print(f"Erro ao salvar arquivo CSV: {e}")
        except Exception as e:
            print(f"Erro inesperado ao salvar CSV: {e}")

    def _print_summaries(self, summaries):
        """Imprime uma lista de resumos no console."""
        if not summaries:
            print("Nenhum resumo para imprimir.")
            return

        print("\n--- Resumos das Notícias (Dentro do Limite de Tempo) ---")
        for summary in summaries:
            print(f"\nTítulo: {summary.get('titulo', 'N/A')}")
            print(f"Fonte: {summary.get('fonte', 'N/A')}")
            print(f"Link Original: {summary.get('link_original', 'N/A')}")
            print(f"Data Publicação: {summary.get('data_publicacao', 'N/A')}")
            print(f"Resumo (LLM): {summary.get('resumo', 'N/A')}")
            print(f"Sentimento (LLM): {summary.get('sentimento', 'N/A')}")
            print(f"Data de Extração (Script): {summary.get('data_extracao', 'N/A')}")
            print("---")

    def process_news(self, output_format='print', csv_filename='crypto_news_summary.csv', hours_limit=2):
        """
        Função principal para monitorar, extrair, resumir notícias e apresentar/salvar os resultados.
        Processa apenas notícias publicadas dentro do 'hours_limit' especificado.

        Args:
            output_format (str): Pode ser 'print', 'csv', 'list', ou 'all'.
            csv_filename (str): Nome do arquivo CSV para salvar os resultados se 'csv' ou 'all' for usado.
            hours_limit (int): Limite em horas para considerar notícias recentes.

        Returns:
            list: Lista de dicionários contendo os dados dos resumos processados.
        """
        print(f"\nIniciando processamento de notícias (Fonte: {self.sitemap_url})...")
        print(f"Processando notícias publicadas nas últimas {hours_limit} hora(s).")

        sitemap_news_items = self._get_news_from_sitemap()

        if not sitemap_news_items:
            print("Nenhuma notícia encontrada no sitemap para processar.")
            return []

        all_summaries = []
        extraction_datetime_utc = datetime.now(timezone.utc)
        print(f'Horário atual (UTC): {extraction_datetime_utc.strftime("%Y-%m-%d %H:%M:%S %Z")}')
        extraction_date_str = extraction_datetime_utc.strftime('%Y-%m-%d %H:%M:%S %Z')

        time_threshold = extraction_datetime_utc - timedelta(hours=hours_limit)
        print(f"Filtrando notícias publicadas após: {time_threshold.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        processed_count = 0

        for item in sitemap_news_items: # sitemap_news_items já está limitado por self.max_news_to_process
            print(f"\nVerificando notícia: {item.get('title', 'Título Desconhecido')}")
            print(f"  Data de Publicação (do sitemap): {item.get('publication_date', 'N/A')}")

            publication_date_str = item.get('publication_date')
            news_publication_date_obj = None

            if publication_date_str and publication_date_str != "N/A":
                try:
                    publication_date_str_adjusted = publication_date_str
                    if publication_date_str.endswith('Z'):
                        publication_date_str_adjusted = publication_date_str[:-1] + '+00:00'
                    elif not any(c in publication_date_str for c in ['+', '-']) and len(publication_date_str) > 19: # Heurística para timezone faltando
                         # Tenta tratar casos onde o offset pode estar faltando mas o formato é quase ISO
                         # Ex: 2024-05-27T18:20:00.000 (sem Z ou offset) -> assumir UTC pode ser uma opção
                         # No entanto, fromisoformat é mais rigoroso. Se o formato for consistentemente com Z,
                         # este 'elif' pode não ser necessário.
                         pass


                    news_publication_date_obj = datetime.fromisoformat(publication_date_str_adjusted)
                    
                    if news_publication_date_obj.tzinfo is None:
                        news_publication_date_obj = news_publication_date_obj.replace(tzinfo=timezone.utc)
                
                except ValueError as ve:
                    print(f"  AVISO: Não foi possível converter a data de publicação '{publication_date_str}'. Erro: {ve}. Pulando filtro de data.")
                    news_publication_date_obj = None 
            
            if not news_publication_date_obj:
                print(f"  Data de publicação inválida ou ausente. Pulando notícia: {item.get('title', 'Título Desconhecido')}")
                continue

            if news_publication_date_obj >= time_threshold:
                print(f"  -> Notícia DENTRO do limite de {hours_limit} hora(s). Processando...")
                processed_count += 1
                
                article_text = self._extract_article_text_from_url(item['original_article_url'])
                article_summary = "Conteúdo do artigo original não pôde ser extraído."
                sentimento_artigo = "N/A" # Default

                if article_text.strip():
                    # Passar o nome do modelo explicitamente se necessário ou usar o self.ollama_model
                    article_summary, sentimento_artigo = self._summarize_and_analyze_with_ollama(article_text)
                else:
                    print(f"Texto do artigo de '{item['original_article_url']}' está vazio. Pulando resumo e análise.")

                summary_data = {
                    'titulo': item.get('title'),
                    'resumo': article_summary,
                    'link_original': item.get('original_article_url'),
                    'fonte': item.get('source_name'),
                    'data_publicacao': item.get('publication_date'), 
                    'data_extracao': extraction_date_str,
                    'sentimento': sentimento_artigo
                }
                all_summaries.append(summary_data)
            else:
                print(f"  -> Notícia FORA do limite de {hours_limit} hora(s) (publicada em {news_publication_date_obj.strftime('%Y-%m-%d %H:%M:%S %Z')}). Ignorando.")

        if processed_count == 0 and len(sitemap_news_items) > 0:
            print(f"\nNenhuma notícia encontrada dentro do limite de {hours_limit} hora(s) das {len(sitemap_news_items)} notícias verificadas do sitemap.")

        if not all_summaries:
            print("Nenhum resumo foi gerado (ou nenhuma notícia passou no filtro de tempo).")
            #return [] # Já retorna all_summaries que estará vazio

        # Saída dos resultados
        if output_format in ['print', 'all']:
            self._print_summaries(all_summaries)
        
        if output_format in ['csv', 'all']:
            self._save_summaries_to_csv(all_summaries, csv_filename)
        
        return all_summaries

    def extract_fear_greed(self):
        """
        Busca os dados do índice "Fear & Greed" da API coin-stats,
        trata possíveis erros de conexão, HTTP e de dados.
        """
        url= 'https://api.coin-stats.com/v2/fear-greed'
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        try:
            # 1. Tenta fazer a requisição para a API
            response = requests.get(url, headers=headers, timeout=10) # Adicionado timeout

            # 2. Verifica se a requisição foi bem-sucedida (códigos 2xx)
            # Se ocorrer um erro de cliente (4xx) ou servidor (5xx), isso levantará uma exceção.
            response.raise_for_status()

            # 3. Tenta decodificar a resposta JSON
            data = response.json()

            # 4. Tenta acessar as chaves no dicionário
            atual = data["now"]["value"]
            classificacao = data["now"]["value_classification"]
            ontem = data["yesterday"]["value"]
            semana_passada = data["lastWeek"]["value"]

            # Se tudo deu certo, imprime os resultados
            print("--- Índice Fear & Greed ---")
            print(f"Valor atual: {atual} ({classificacao})")
            print(f"Ontem: {ontem}")
            print(f"Semana passada: {semana_passada}")
            print("---------------------------")
            return atual, classificacao, ontem
        
        except requests.exceptions.RequestException as e:
            # Captura erros de conexão, timeout, DNS, etc.
            print(f"❌ Erro de conexão com a API: {e}")

        except requests.exceptions.JSONDecodeError:
            # Captura erro se a resposta não for um JSON válido
            print("❌ Erro: A resposta da API não está no formato JSON esperado.")

        except KeyError as e:
            # Captura erro se uma chave esperada não for encontrada no JSON
            print(f"❌ Erro: A estrutura dos dados mudou. Chave não encontrada: {e}")

        except Exception as e:
            # Captura qualquer outro erro inesperado
            print(f"😕 Ocorreu um erro inesperado: {e}")

    def escapar_markdown_v2(self, texto: str) -> str:
        """
        Escapa todos os caracteres reservados do MarkdownV2 do Telegram.
        """
        self.texto = texto
        # A lista de caracteres que precisam ser escapados
        caracteres_reservados = r"[_*\[\]()~`>#+\-=|{}.!]"
        
        # Usa a função re.sub() para adicionar uma '\' antes de cada caractere reservado
        return re.sub(f'({caracteres_reservados})', r'\\\1', texto)

    def formatar_mensagem_fear_greed(self, atual: int, classificacao: str, ontem: int) -> str:
        """
        Cria uma mensagem formatada e dinâmica para o índice Fear & Greed.
        """
        self.atual = atual
        self.classificacao = classificacao
        self.ontem = ontem

        classificacao_escapada = self.escapar_markdown_v2(texto = self.classificacao)

        # Dicionário de emojis para cada classificação
        emojis = {
            "extreme fear": "🥶",
            "fear": "😨",
            "neutral": "😐",
            "greed": "😏",
            "extreme greed": "🤑"
        }
        # Pega o emoji correspondente, ou um padrão caso a classificação não seja encontrada
        emoji_atual = emojis.get(self.classificacao.lower(), "📊")

        # Compara o valor atual com o de ontem
        comparacao = ""
        if self.atual > self.ontem:
            self.comparacao = f"Subiu desde ontem 📈"
        elif self.atual < ontem:
            self.comparacao = f"Desceu desde ontem 📉"
        else:
            self.comparacao = f"Estável ↔️"
        
        # Monta a mensagem final (não esqueça de escapar os caracteres para o MarkdownV2)
        mensagem = (
            f"{emoji_atual} *Fear & Greed Index* {emoji_atual}\n\n"
            f"👉 *Agora:* {self.atual} \\- *{classificacao_escapada}*\n"
            f"🗓️ *Ontem:* {self.ontem}\n\n"
            f"{self.comparacao}"
        )
        return mensagem

class EconomicEventsError(Exception):
    """Exceção personalizada para erros na classe EconomicEvents."""
    pass

class EconomicEvents:
    DEFAULT_URL = 'https://economic-calendar.tradingview.com/events'
    DEFAULT_COUNTRIES = ['US']
    DEFAULT_MAX_ATTEMPTS = 3
    DEFAULT_RETRY_DELAY_SECONDS = 5
    DEFAULT_REQUEST_TIMEOUT_SECONDS = 10 # Timeout para a requisição HTTP
    def __init__(self,
                 url: str = DEFAULT_URL,
                 default_countries: Optional[List[str]] = None,
                 max_attempts: int = DEFAULT_MAX_ATTEMPTS,
                 retry_delay: int = DEFAULT_RETRY_DELAY_SECONDS,
                 request_timeout: int = DEFAULT_REQUEST_TIMEOUT_SECONDS
                 ):
        self.url = url

        self.url = url
        self.default_countries = default_countries if default_countries is not None else list(self.DEFAULT_COUNTRIES)
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay
        self.request_timeout = request_timeout

        print(f"EconomicEvents inicializado. URL: {self.url}, Países Padrão: {self.default_countries}, Tentativas: {self.max_attempts}")

        """
        Inicializa o cliente para buscar eventos econômicos.

        Args:
            url (str): URL da API de eventos econômicos.
            default_countries (Optional[List[str]]): Lista de códigos de países padrão.
            max_attempts (int): Número máximo de tentativas para a requisição.
            retry_delay (int): Tempo de espera (em segundos) entre as tentativas.
            request_timeout (int): Timeout em segundos para a requisição HTTP.
        """

    def _prepare_time_payload(self,
                              start_date_param: Optional[pd.Timestamp] = None,
                              end_date_param: Optional[pd.Timestamp] = None
                             ) -> Dict[str, str]:
        """
        Prepara o payload de tempo para a API, garantindo que os tempos sejam em UTC.
        A intenção é usar o fuso 'America/Sao_Paulo' como referência para os padrões
        e converter para UTC para a API.
        """
        # Define o fuso horário de referência para datas/horas não especificadas
        local_tz = 'America/Sao_Paulo'

        # Determina a data de início no fuso local
        if start_date_param:
            if start_date_param.tzinfo is None:
                start_local = start_date_param.tz_localize(local_tz)
            else:
                start_local = start_date_param.tz_convert(local_tz)
        else:
            # Padrão: hoje às 06:00 no fuso local de referência
            start_local = pd.Timestamp.now(tz=local_tz).normalize() + pd.Timedelta(hours=6)

        # Determina a data de fim no fuso local
        if end_date_param:
            if end_date_param.tzinfo is None:
                end_local = end_date_param.tz_localize(local_tz)
            else:
                end_local = end_date_param.tz_convert(local_tz)
        else:
            # Padrão: dia seguinte (em relação ao 'hoje' do fuso local) à meia-noite.
            # Isso cobre eventos do dia inteiro de 'start_local' se start_local for 00:00,
            # ou eventos a partir das 6h até o final do dia.
            # A lógica original era `today + pd.Timedelta(days=1)`, que seria 00:00 do dia seguinte ao 'today'.
            end_local = pd.Timestamp.now(tz=local_tz).normalize() + pd.Timedelta(days=1)

        # Converte para UTC e formata para a API
        start_utc = start_local.tz_convert('UTC')
        end_utc = end_local.tz_convert('UTC')

        # O formato '.000Z' é uma forma comum de representar UTC com milissegundos.
        # O .isoformat() para Timestamps UTC já inclui o offset (+00:00 ou Z se for simples).
        # Garantir o formato específico que a API espera.
        return {
            'from': start_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z', # Formato ISO com milissegundos e Z
            'to': end_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
        }
    
    def get_economic_events(self,
                            countries: Optional[List[str]] = None,
                            start_date_param: Optional[pd.Timestamp] = None,
                            end_date_param: Optional[pd.Timestamp] = None
                           ) -> Optional[pd.DataFrame]:
        """
        Busca eventos econômicos da API do TradingView.

        Args:
            countries (Optional[List[str]]): Lista de códigos de países. Usa padrão da instância se None.
            start_date_param (Optional[pd.Timestamp]): Data/hora de início (naive ou aware).
            end_date_param (Optional[pd.Timestamp]): Data/hora de fim (naive ou aware).

        Returns:
            Optional[pd.DataFrame]: DataFrame com eventos, ou um DataFrame vazio se nenhum evento
                                   for encontrado. Colunas: ['title', 'indicator', 'actual',
                                   'previous', 'forecast', 'importance', 'date', 'hora'].
                                   'date' e 'hora' estão em 'America/Sao_Paulo'.

        Raises:
            EconomicEventsError: Se não for possível buscar os eventos após todas as tentativas.
        """
        time_payload = self._prepare_time_payload(start_date_param, end_date_param)
        current_countries = countries if countries is not None else self.default_countries
        
        headers = {'Origin': 'https://in.tradingview.com'}
        payload = {
            **time_payload,
            'countries': ','.join(current_countries)
        }

        print(f"Buscando eventos econômicos. Payload: {payload}")
        last_exception = None

        for attempt in range(self.max_attempts):
            try:
                response = requests.get(self.url, headers=headers, params=payload, timeout=self.request_timeout)
                response.raise_for_status()

                data = response.json()

                if 'result' not in data or not isinstance(data['result'], list):
                    # Este é um erro estrutural na resposta da API. Novas tentativas podem não ajudar.
                    print("Chave 'result' não encontrada ou formato inesperado na resposta da API.")
                    raise EconomicEventsError("Resposta da API com estrutura inválida: sem 'result' ou não é lista.")

                df = pd.DataFrame(data['result'])
                
                if df.empty:
                    print("Nenhum evento encontrado nos dados retornados pela API para os critérios fornecidos.")
                    return df # Retorna DataFrame vazio se a API não retornou eventos

                # Validação de colunas essenciais
                required_cols_from_api = {'importance', 'title', 'indicator', 'date'}
                if not required_cols_from_api.issubset(df.columns):
                    missing_cols = required_cols_from_api - set(df.columns)
                    print(f"Colunas essenciais ausentes nos dados da API: {missing_cols}")
                    raise EconomicEventsError(f"Dados da API incompletos, colunas ausentes: {missing_cols}")
                
                # Filtrar por importância (se a coluna existir e for desejado)
                # A lógica original filtrava df[df['importance'] == 1]. Vamos manter isso.
                df = df[df['importance'] == 1].copy() # .copy() para evitar SettingWithCopyWarning

                if df.empty:
                    print("Nenhum evento encontrado com importância == 1.")
                    return df # Retorna DataFrame vazio se não houver eventos importantes

                # Selecionar e reordenar colunas desejadas, garantindo que existam
                desired_cols_output = ['title', 'indicator', 'actual', 'previous', 'forecast', 'importance', 'date']
                cols_to_keep = [col for col in desired_cols_output if col in df.columns]
                df = df[cols_to_keep]

                # Tratamento de data/hora
                # A API do TradingView retorna 'date' como string ISO 8601 em UTC (com Z)
                df['date'] = pd.to_datetime(df['date'], errors='coerce', utc=True) # utc=True informa ao pandas
                df.dropna(subset=['date'], inplace=True) # Remove linhas onde a data não pôde ser convertida

                if df.empty:
                     print("Nenhum evento com data válida após conversão e remoção de NaT.")
                     return df

                # Converter para o fuso horário de São Paulo e extrair a hora
                df['date'] = df['date'].dt.tz_convert('America/Sao_Paulo')
                df['hora'] = df['date'].dt.strftime('%H:%M:%S')
                
                print(f"Total de {len(df)} eventos econômicos importantes processados.")
                return df

            except requests.exceptions.HTTPError as e:
                logger.warning(f"Erro HTTP (tentativa {attempt + 1}/{self.max_attempts}): {e.response.status_code} - {e.response.text}")
                last_exception = e
                if 400 <= e.response.status_code < 500 and e.response.status_code not in [429]: # 429 Too Many Requests pode se beneficiar de retry
                    logger.error(f"Erro de cliente ({e.response.status_code}), interrompendo tentativas.")
                    break # Interrompe para erros de cliente (ex: 400, 401, 403, 404)
            except requests.exceptions.Timeout as e:
                logger.warning(f"Timeout na requisição (tentativa {attempt + 1}/{self.max_attempts}): {e}")
                last_exception = e
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Erro de conexão (tentativa {attempt + 1}/{self.max_attempts}): {e}")
                last_exception = e
            except requests.exceptions.JSONDecodeError as e:
                logger.error(f"Erro ao decodificar JSON (tentativa {attempt + 1}/{self.max_attempts}): {e.msg}. Resposta: {e.doc[:200]}...") # Mostra parte da resposta problemática
                last_exception = e
                break # Erro de decodificação JSON geralmente não se resolve com nova tentativa.
            except EconomicEventsError as e: # Nossa exceção personalizada para erros de lógica/estrutura
                logger.error(f"Erro de processamento interno (tentativa {attempt + 1}/{self.max_attempts}): {e}")
                last_exception = e
                break # Interrompe pois é um erro que nós identificamos como problemático para continuar.
            except KeyError as e: # Pode ocorrer se a estrutura do DataFrame mudar inesperadamente
                logger.error(f"Erro de chave ao acessar dados do DataFrame (tentativa {attempt + 1}/{self.max_attempts}): Coluna {e} não encontrada.")
                last_exception = e
                break # Mudança na estrutura de dados, provável que não se resolva com retry.
            except Exception as e: # Captura qualquer outra exceção não prevista
                logger.error(f"Erro inesperado (tentativa {attempt + 1}/{self.max_attempts}): {type(e).__name__} - {e}", exc_info=True) # exc_info=True para logar o traceback completo
                last_exception = e
            
            if attempt < self.max_attempts - 1:
                 print(f"Aguardando {self.retry_delay}s para próxima tentativa...")
                 time.sleep(self.retry_delay)

        # Se todas as tentativas falharem
        error_message = "Todas as tentativas de buscar eventos econômicos falharam."
        print(error_message)
        if last_exception:
            raise EconomicEventsError(error_message) from last_exception
        else:
            # Caso o loop termine sem exceções mas não retorne (improvável com a lógica atual)
            raise EconomicEventsError(f"{error_message} Motivo desconhecido.")

class TelegramNotifier:
    """
    Uma classe robusta para enviar notificações para o Telegram.
    
    Gerencia a inicialização do bot e o envio de mensagens de forma
    eficiente e flexível.
    """
    def __init__(self, token: str = None, chat_id: str = None):
        """
        Construtor da classe. Carrega as credenciais e inicializa o bot.

        Args:
            token (str, optional): Token do bot do Telegram. 
                                   Se não for fornecido, tenta carregar do .env.
            chat_id (str, optional): ID do chat para onde enviar as mensagens.
                                     Se não for fornecido, tenta carregar do .env.
        """
        load_dotenv()
        
        # Prioriza os argumentos passados, mas usa o .env como fallback
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.default_chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

        if not self.token:
            raise ValueError("Token do Telegram não encontrado. Forneça via argumento ou no arquivo .env.")
        
        # O bot é inicializado UMA VEZ aqui, e não a cada envio.
        self.bot = telegram.Bot(token=self.token)
        logger.info("Instância do TelegramNotifier criada com sucesso.")

    async def enviar_mensagem(self, texto: str, target_chat_id: str = None) -> bool:
        """
        Envia uma mensagem de texto para um chat do Telegram.

        Args:
            texto (str): A mensagem a ser enviada.
            target_chat_id (str, optional): O ID do chat de destino. 
                                            Se não for fornecido, usa o ID padrão.

        Returns:
            bool: True se a mensagem foi enviada com sucesso, False caso contrário.
        """
        chat_id_to_use = target_chat_id or self.default_chat_id

        if not chat_id_to_use:
            logger.error("Nenhum CHAT_ID de destino foi definido (nem padrão, nem via argumento).")
            return False

        logger.info(f"Tentando enviar mensagem para o chat ID: {chat_id_to_use[:4]}...") # Mostra só o início do ID por segurança
        
        try:
            await self.bot.send_message(
                chat_id=chat_id_to_use,
                text=texto,
                parse_mode='MarkdownV2'
            )
            logger.info("✅ Mensagem enviada com sucesso!")
            return True

        except telegram.error.TelegramError as e:
            logger.error(f"❌ Falha ao enviar mensagem: {e}")
            logger.error("Causas possíveis: Bot não está no grupo, Chat ID incorreto ou bot bloqueado.")
            return False
        except Exception as e:
            logger.error(f"😕 Ocorreu um erro inesperado: {e}", exc_info=True) # exc_info=True mostra o traceback
            return False

class ScraperCoinranking:
    """
    Uma classe para fazer scraping da página de 'gainers' do Coinranking
    e formatar um relatório para o Telegram.
    """
    def __init__(self, url='https://coinranking.com/coins/gainers'):
        """
        O construtor da classe. É executado quando criamos um novo objeto.
        """
        self.url = url
        print(f"ScraperTelegram inicializado para a URL: {self.url}")

    def _carregar_html_da_pagina(self):
        # Este método é "privado" (convenção do underscore _),
        # pois só precisa ser usado dentro desta classe.
        print("Iniciando o navegador com Selenium...")
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        try:
            driver.get(self.url)
            print(f"Página {self.url} carregada.")
            wait = WebDriverWait(driver, 20)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, 'tbody')))
            time.sleep(2)
            print("Conteúdo carregado. Extraindo o HTML...")
            return driver.page_source
        except Exception as e:
            print(f"Ocorreu um erro ao carregar a página com Selenium: {e}")
            return None
        finally:
            driver.quit()
            print("Navegador fechado.")

    def _extrair_dados_da_tabela(self, html_completo):
        # Este método também é para uso interno.
        if not html_completo: return []
        soup = BeautifulSoup(html_completo, 'html.parser')
        # ... (lógica de extração completa como antes) ...
        lista_de_moedas = []
        tabela_body = soup.find('tbody')
        if not tabela_body: return []
        linhas = tabela_body.find_all('tr', id=lambda x: x and x.startswith('coin-'))
        print(f"Encontradas {len(linhas)} moedas na tabela.")
        for linha in linhas:
            rank = linha.select_one("td:nth-of-type(2)").get_text(strip=True)
            nome = linha.select_one(".coin-profile__name").get_text(strip=True)
            simbolo = linha.select_one(".coin-profile__symbol").get_text(strip=True)
            preco = linha.select_one("real-time-price").get_text(strip=True)
            market_cap_tag = linha.select_one("td.hidden-tablet-landscape.hidden-mobile")
            market_cap = market_cap_tag.get_text(strip=True) if market_cap_tag else 'N/A'
            change_24h_tag = linha.select_one(".change__percentage")
            change_24h = change_24h_tag.get_text(strip=True) if change_24h_tag else 'N/A'
            lista_de_moedas.append({
                'rank': rank, 'nome': nome, 'simbolo': simbolo,
                'preco_usd': preco.replace('$', '').strip(),
                'market_cap': market_cap.replace('$', '').strip(),
                'variacao_24h_percent': change_24h.replace('+', '').replace('%', '').strip()
            })
        return lista_de_moedas

    def formatar_mensagem_telegram(self, lista_de_moedas, tipo_relatorio="gainers"):
        """
        Formata os dados das top 10 moedas para uma mensagem de Telegram,
        adaptando-se para 'gainers' ou 'losers'.
        """
        if not lista_de_moedas:
            return f"Não foi possível obter os dados para o relatório de '{tipo_relatorio}'."

        top_10 = lista_de_moedas[:10]
        
        # 1. Define o título e emoji principal baseado no tipo de relatório
        if tipo_relatorio.lower() == "losers":
            titulo_mensagem = "📉 *Top 10 Cripto Losers do Dia* 💔"
        else: # O padrão é 'gainers'
            titulo_mensagem = "🏆 *Top 10 Cripto Gainers do Dia* 🚀"
        
        mensagem = [titulo_mensagem + "\n"]
        
        # Cabeçalho da tabela
        mensagem.append("```")
        mensagem.append(f"{'#':<3} {'Símbolo':<8} {'Preço (USD)':<15} {'Variação 24h'}")
        mensagem.append(f"{'-'*3} {'-'*8} {'-'*15} {'-'*14}")

        # 2. Adiciona cada moeda à mensagem
        for moeda in top_10:
            try:
                rank = moeda['rank']
                simbolo = moeda['simbolo']
                preco = float(moeda['preco_usd'])
                variacao = float(moeda['variacao_24h_percent'])
                
                # 3. Escolhe o emoji correto para a variação
                emoji_variacao = "🟢" if variacao >= 0 else "🔴"
                
                # Formata a linha. O f-string `+7.2f` já lida com o sinal de '+' ou '-'.
                linha = (f"{rank:<3} {simbolo:<8} ${preco:<14,.6f} {variacao:>+7.2f}% {emoji_variacao}")
                mensagem.append(linha)
            except (ValueError, TypeError):
                continue
                
        mensagem.append("```")

        # Rodapé
        agora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        # Ajustamos a fonte para ser genérica, pois a classe pode ter URLs diferentes
        mensagem.append(f"\n_Atualizado em: {agora}_")
        mensagem.append(f"🔗 _Fonte: Coinranking_")

        return "\n".join(mensagem)

    # ---- O MÉTODO PÚBLICO E ORQUESTRADOR ----
    def gerar_relatorio_telegram(self):
        """
        Este é o único método que precisa ser chamado de fora.
        Ele orquestra todo o processo.
        """
        print("\n--- INICIANDO PROCESSO COMPLETO DE GERAÇÃO DE RELATÓRIO ---")
        
        # 1. Carregar a página
        html = self._carregar_html_da_pagina()
        if not html:
            return "Falha ao carregar a página. Relatório não pode ser gerado."

        # 2. Extrair os dados
        dados = self._extrair_dados_da_tabela(html)
        if not dados:
            return "Falha ao extrair dados. Relatório não pode ser gerado."
        
        # 3. extrair o texto da url
        parsed_url = urlparse(self.url)
        caminho = parsed_url.path
        tipo = [p for p in caminho.split('/') if p][-1]
        # 4. Formatar a mensagem

        mensagem_final = self.formatar_mensagem_telegram(dados, tipo)
        
        print("--- PROCESSO FINALIZADO COM SUCESSO ---")
        return mensagem_final

async def main():
    """Função principal que orquestra todo o processo."""
    print("Executando o processo de notícias e notificação...\n")
    
    try:
        # Inicializa o notificador do Telegram
        notifier = TelegramNotifier()

        # Verifica eventos importantes
        events_client = EconomicEvents()
        print("\n--- Eventos importantes ---")
        try:
            df_events_default = events_client.get_economic_events()
            if df_events_default is not None and not df_events_default.empty:
                print(f"Eventos encontrados (Padrão):\n{df_events_default}")
            elif df_events_default is not None: # DataFrame vazio
                print("Nenhum evento encontrado (Padrão).")
        except EconomicEventsError as e:
            print(f"Erro ao buscar eventos (Padrão): {e}")
            if e.__cause__:
                print(f"Causa original: {type(e.__cause__).__name__} - {e.__cause__}")
        
        # verifica top gainers e losers
        tipo = ['gainers', 'losers']
        for t in tipo:
            url = f"https://coinranking.com/coins/{t}"
            
            # 2. Crie uma instância da sua classe
            meu_scraper = ScraperCoinranking(url=url)
            
            # 3. Chame APENAS o método orquestrador
            relatorio_final = meu_scraper.gerar_relatorio_telegram()

            # 4. Use o resultado
            print(f"\n--- MENSAGEM FINAL PRONTA PARA ENVIAR TIPO {t.upper()} ---")
            print(relatorio_final)
            await notifier.enviar_mensagem(relatorio_final)

        # Verifica e envia notícias
        # Configurações do seu scraper
        meu_modelo_ollama = "gemma3:12b"
        maximo_noticias = 1
        limite_horas_recentes = 24

        # Cria uma instância do processador de notícias
        processor = NewsProcessor(
            sitemap_url="https://cointelegraph.com/sitemap-google-news.xml",
            ollama_model=meu_modelo_ollama,
            max_news_to_process=maximo_noticias
        )
        # Processa as notícias
        resultados = processor.process_news(
            output_format='list',
            csv_filename='noticias_cripto_processadas.csv',
            hours_limit=limite_horas_recentes
        )

        # Captura e envia o índice "Fear & Greed" e envia a mensagem
        atual, classificacao, ontem = processor.extract_fear_greed()
        mensagem = processor.formatar_mensagem_fear_greed(atual, classificacao, ontem)
        await notifier.enviar_mensagem(mensagem)

        # Formata a mensagem com os resultados
        if resultados:
            for r in resultados:
                resumo = r['resumo']
                resumo_escapado = processor.escapar_markdown_v2(texto = resumo)
                # Envia a mensagem formatada para o Telegram
                await notifier.enviar_mensagem(resumo_escapado)
        else:
            logger.info("Nenhuma notícia encontrada para enviar.")
 
        print("\nProcesso finalizado com sucesso!")

    except ValueError as e:
        logger.error(f"Erro de configuração: {e}. Verifique seu arquivo .env")
    except Exception as e:
        logger.error(f"Ocorreu um erro crítico no processo principal: {e}", exc_info=True)

if __name__ == "__main__":
    
    asyncio.run(main())

# # --- Exemplo de como usar a classe ---
# if __name__ == "__main__":
#     print("Executando Exemplo de NewsProcessor...\n")

#     # Configurações
#     meu_modelo_ollama = "gemma3:12b"  # Mude para o seu modelo Ollama disponível
#     maximo_noticias = 10       # Quantas notícias do sitemap processar no máximo (independente do filtro de tempo)
#     limite_horas_recentes = 24  # Considerar notícias das últimas X horas

#     # Criar uma instância do processador
#     # Você pode testar diferentes modelos ou sitemaps aqui
#     processor = NewsProcessor(
#         sitemap_url="https://cointelegraph.com/sitemap-google-news.xml", # Ou "https://br.cointelegraph.com/sitemap-google-news.xml" para pt-BR
#         ollama_model=meu_modelo_ollama,
#         max_news_to_process=maximo_noticias
#     )

#     # Processar as notícias e obter os resultados
#     # Opções de output_format: 'print', 'csv', 'list', 'all'
#     resultados = processor.process_news(
#         output_format='csv',  # Mude para 'csv', 'print', 'list', ou 'all' conforme necessário
#         # Se 'csv' ou 'all', o arquivo será salvo com este nome
#         csv_filename='noticias_cripto_processadas.csv',
#         hours_limit=limite_horas_recentes
#     )

#     if resultados:
#         print(f"\n{len(resultados)} notícias foram processadas e retornadas (dentro do limite de tempo e max_news_to_process).")
#         #Você pode fazer algo mais com os 'resultados' aqui se output_format='list' ou 'all'
#         print("\nDados retornados:")
#         for r in resultados:
#             print(f"  - Título: {r['titulo']}, Sentimento: {r['sentimento']}")
#     else:
#         print("\nNenhuma notícia foi processada ou retornada.")
    
#     processor.extract_fear_greed()
    # asyncio.run(enviar_mensagem(mensagem_para_enviar))

# # --- Como Usar a Nova Classe TelegramNotifier---
# async def main():
#     """Função principal para demonstrar o uso da classe."""
#     try:
#         # 1. Cria uma instância da classe (ela carrega tudo do .env automaticamente)
#         notifier = TelegramNotifier()

#         # 2. Envia uma mensagem para o chat padrão
#         mensagem1 = "Esta é a primeira mensagem de teste usando a classe robusta\\."
#         sucesso = await notifier.enviar_mensagem(mensagem1)
#         if sucesso:
#             print("Demonstração 1: Sucesso!")
#         else:
#             print("Demonstração 1: Falha!")
            
#         print("-" * 20)

#         # 3. Envia uma mensagem para um OUTRO chat, especificando o ID na chamada
#         # Descomente a linha abaixo e substitua pelo ID de outro grupo para testar
#         # await notifier.enviar_mensagem("Esta mensagem vai para outro lugar\\!", target_chat_id="-9876543210")

#     except ValueError as e:
#         # Se o token não for encontrado na inicialização, o erro será capturado aqui
#         logger.error(e)

# if __name__ == "__main__":
#     asyncio.run(main())

# Exemplo de uso (para testar):
# if __name__ == '__main__':
#     # Configuração de logging mais detalhada para teste
#     logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
#     events_client = EconomicEvents()
    
#     # Teste 1: Padrão (hoje + 6h até dia seguinte 0h, países padrão US)
#     print("\n--- Teste 1: Padrão ---")
#     try:
#         df_events_default = events_client.get_economic_events()
#         if df_events_default is not None and not df_events_default.empty:
#             print(f"Eventos encontrados (Padrão):\n{df_events_default.head()}")
#         elif df_events_default is not None: # DataFrame vazio
#              print("Nenhum evento encontrado (Padrão).")
#     except EconomicEventsError as e:
#         print(f"Erro ao buscar eventos (Padrão): {e}")
#         if e.__cause__:
#              print(f"  Causa original: {type(e.__cause__).__name__} - {e.__cause__}")
