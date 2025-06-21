from openai import OpenAI
from config.config import OPENAI_API_KEY
import asyncio

# client = OpenAI(OPENAI_API_KEY)

async def analisar_sentimento_openai(textos, idioma='en', seed=42):
    client = OpenAI(OPENAI_API_KEY)
    resultados = []
    for texto in textos:
        prompt = f"""
                    You are a financial sentiment classifier.
                    Read the news headline below and classify it as POSITIVE, NEGATIVE, or NEUTRAL.
                    Then, write a one-sentence justification.

                    Respond ONLY in this JSON format:
                    {{
                    "sentiment": "...",
                    "justification": "..."
                    }}

                    Headline: "{texto}"
                    """ if idioma == 'en' else f"""
                    Você é um classificador de sentimento financeiro.
                    Leia o título da notícia abaixo e classifique como POSITIVO, NEGATIVO ou NEUTRO.
                    Em seguida, escreva uma justificativa em uma frase.

                    Responda APENAS neste formato JSON:
                    {{
                    "sentimento": "...",
                    "justificativa": "..."
                    }}

                    Título: "{texto}"
                    """
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-4-turbo",
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

        await asyncio.sleep(0.5)

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