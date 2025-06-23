import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from openai import AsyncOpenAI
from config.config import OPENAI_API_KEY
import asyncio
from config.config import OPENROUTER_API_KEY

async def analisar_sentimento_openrouter(textos, idioma='pt', seed=42):
    """
    Analisa o sentimento de uma lista de textos usando um modelo do OpenRouter.

    Args:
        textos (list): Uma lista de strings com as notícias.
        idioma (str): 'pt' para português ou 'en' para inglês.
        modelo (str): O identificador do modelo no OpenRouter.
                      (ex: "google/gemini-flash-1.5", "mistralai/mistral-7b-instruct-v0.2")

    Returns:
        list: Uma lista de dicionários com o sentimento e a justificativa.
    """
    client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    default_headers={
        "X-Title": "Falcon Crypto AI"
    },
)
    resultados = []
    for texto in textos:
        prompt = f"""
                    Você é um classificador de sentimento financeiro.
                    Leia o título da notícia abaixo e classifique como POSITIVO, NEGATIVO ou NEUTRO.
                    Em seguida, escreva uma justificativa em uma frase.

                    Responda APENAS neste formato JSON, sem nenhum texto ou formatação adicional:
                    {{
                        "sentimento": "...",
                        "justificativa": "..."
                    }}

                    Título: "{texto}"
                    """
        
        # Ajuste para inglês se necessário
        if idioma == 'en':
            prompt = f"""
                        You are a financial sentiment classifier.
                        Read the news headline below and classify it as POSITIVE, NEGATIVE, or NEUTRAL.
                        Then, write a one-sentence justification.

                        Respond ONLY in this JSON format, with no additional text or formatting:
                        {{
                        "sentiment": "...",
                        "justification": "..."
                        }}

                        Headline: "{texto}"
                        """
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model="google/gemma-3-27b-it:free",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                seed=seed
            )
            conteudo = response.choices[0].message.content.strip()

            try:
                resultados.append(eval(conteudo))
            except:
                resultados.append({"sentiment": "ERROR", "justification": conteudo})

        except Exception as e:
            resultados.append({"sentiment": "ERROR", "justification": str(e)})

        await asyncio.sleep(1.5)

    return resultados

def gerar_resumo(df):
    total = len(df)
    resumo = df['sentiment'].value_counts(normalize=True) * 100
    counts = df['sentiment'].value_counts()

    resumo_texto = "\n".join([f"• {s}: {counts[s]} ({resumo[s]:.1f}%)" for s in resumo.index])

    data_min = df['data'].min()
    data_max = df['data'].max()

    noticia_mais_nova = df[df['data'] == data_min].iloc[0]
    noticia_mais_antiga = df[df['data'] == data_max].iloc[0]

    texto = (
        f"📰 *Resumo das Notícias*\n"
        f"• Total de notícias: {total}\n\n"
        f"*Distribuição de Sentimento:*\n{resumo_texto}\n\n"
        f"🕒 *Mais recente:* \"{noticia_mais_nova['titulo']}\" - {noticia_mais_nova['data']}\n"
        f"🔗 {noticia_mais_nova['link']}\n\n"
        f"🕰️ *Mais antiga:* \"{noticia_mais_antiga['titulo']}\" - {noticia_mais_antiga['data']}\n"
        f"🔗 {noticia_mais_antiga['link']}"
    )
    return texto