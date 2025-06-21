import aiohttp
import asyncio
import pandas as pd
from GoogleNews import GoogleNews

async def get_economic_events_async():
    url = 'https://economic-calendar.tradingview.com/events'
    today = pd.Timestamp.today().normalize()

    start_time_sp = today + pd.Timedelta(hours=6)
    end_time_sp = today + pd.Timedelta(days=1)

    headers = {'Origin': 'https://in.tradingview.com'}
    params = {
        'from': start_time_sp.isoformat() + '.000Z',
        'to': end_time_sp.isoformat() + '.000Z',
        'countries': 'US'
    }

    attempts = 0
    max_attempts = 5

    while attempts < max_attempts:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    data = await response.json()

            df = pd.DataFrame(data['result'])
            df = df[df['importance'] == 1][['title', 'indicator', 'actual', 'previous', 'forecast', 'importance', 'date']]
            df['date'] = pd.to_datetime(df['date'])

            if df['date'].dt.tz is None:
                df['date'] = df['date'].dt.tz_localize('UTC')
            df['date'] = df['date'].dt.tz_convert('America/Sao_Paulo')
            df['hora'] = df['date'].dt.strftime('%H:%M')

            return df

        except Exception as e:
            print(f"Erro ao buscar dados econômicos: {e}")
            attempts += 1
            await asyncio.sleep(5)

    return None

async def buscar_noticias_google(termos, idioma='en', dias=1, max_paginas=2):
    lang = idioma.lower()
    region = 'BR' if lang == 'pt' else 'EN'

    googlenews = GoogleNews(lang=lang, region=region, period=f'{dias}d')
    resultados = []

    for termo in termos:
        googlenews.search(termo)

        for pagina in range(1, max_paginas + 1):
            googlenews.getpage(pagina)
            noticias = googlenews.result()

            for n in noticias:
                data = n.get('date', '').lower()

                if any(x in data for x in ['minutes', 'minutos', 'hora', 'hour']):
                    resultados.append({
                        'termo': termo,
                        'titulo': n.get('title'),
                        'data': n.get('date'),
                        'link': n.get('link'),
                        'fonte': n.get('media'),
                        'desc': n.get('desc')
                    })

            await asyncio.sleep(0.5)

        googlenews.clear()

    df = pd.DataFrame(resultados).drop_duplicates(subset=['titulo', 'link'])
    return df