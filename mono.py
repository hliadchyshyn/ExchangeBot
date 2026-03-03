import threading
import time
from typing import Optional

import requests

URL = 'https://api.monobank.ua/bank/currency'
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
