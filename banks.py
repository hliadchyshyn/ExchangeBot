import requests

import mono

PRIVAT_URL = 'https://api.privatbank.ua/p24api/pubinfo?json&exchange&coursid=5'
BINANCE_URL = 'https://api.binance.com/api/v3/ticker/price'
BINANCE_SYMBOLS = ['USDTUAH', 'BTCUAH', 'ETHUAH', 'SOLUAH']

CCY_CODES = {'USD': 840, 'EUR': 978}


def get_privat_rates() -> dict:
    """Returns {'USD': {'buy': float, 'sell': float}, 'EUR': {...}}"""
    response = requests.get(PRIVAT_URL, timeout=10)
    response.raise_for_status()
    result = {}
    for item in response.json():
        if item['ccy'] in ('USD', 'EUR') and item['base_ccy'] == 'UAH':
            result[item['ccy']] = {
                'buy': float(item['buy']),
                'sell': float(item['sale']),
            }
    return result


def get_binance_rates() -> list[dict]:
    """Returns list of {'symbol': str, 'price': float} for available UAH pairs."""
    results = []
    for symbol in BINANCE_SYMBOLS:
        try:
            response = requests.get(BINANCE_URL, params={'symbol': symbol}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results.append({'symbol': data['symbol'], 'price': float(data['price'])})
        except Exception:
            pass
    return results


def get_best_rates(ccy: str) -> list[dict]:
    """Return banks sorted by lowest sell rate (cheapest to buy from)."""
    sources = []

    ex = mono.get_exchange(CCY_CODES[ccy])
    if ex:
        sources.append({'bank': 'MonoBank', 'buy': ex['rateBuy'], 'sell': ex['rateSell']})

    try:
        privat = get_privat_rates()
        if ccy in privat:
            sources.append({'bank': 'PrivatBank', **privat[ccy]})
    except Exception:
        pass

    sources = [s for s in sources if s.get('sell')]
    sources.sort(key=lambda x: x['sell'])
    return sources
