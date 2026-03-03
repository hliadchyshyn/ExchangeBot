import threading
import time
from datetime import datetime, timedelta
from typing import Optional

import requests

URL = 'https://api.monobank.ua/bank/currency'
NBU_URL = 'https://bank.gov.ua/NBU_Exchange/exchange_site'
_CACHE_TTL = 60  # seconds
_cache: dict = {'data': None, 'ts': 0}
_lock = threading.Lock()


def _load_exchange() -> list:
    now = time.monotonic()
    with _lock:
        if _cache['data'] is not None and now - _cache['ts'] <= _CACHE_TTL:
            return _cache['data']

    try:
        response = requests.get(URL, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        with _lock:
            if _cache['data'] is not None:
                return _cache['data']  # serve stale on error
        raise

    with _lock:
        _cache['data'] = data
        _cache['ts'] = now
    return data


def get_nbu_history(ccy: str, days: int = 7) -> list[dict]:
    """Fetch official NBU rates for the last `days` days.
    Returns list of {'date': str, 'rate': float} newest first.
    """
    end = datetime.now()
    start = end - timedelta(days=days)
    params = {
        'start': start.strftime('%Y%m%d'),
        'end': end.strftime('%Y%m%d'),
        'valcode': ccy.lower(),
        'sort': 'exchangedate',
        'order': 'desc',
        'json': '',
    }
    response = requests.get(NBU_URL, params=params, timeout=10)
    response.raise_for_status()
    return [
        {'date': entry['exchangedate'], 'rate': entry['rate']}
        for entry in response.json()
    ]


def get_exchange(ccy_code: int) -> Optional[dict]:
    for exc in _load_exchange():
        if ccy_code == exc['currencyCodeA']:
            return exc
    return None


def get_exchanges(ccy_code_prefix: int) -> list[dict]:
    prefix = str(ccy_code_prefix)
    return [
        exc for exc in _load_exchange()
        if str(exc['currencyCodeA']).startswith(prefix)
    ]
