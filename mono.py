# -*- coding: utf-8 -*-
import re

import requests
import json

URL = 'https://api.monobank.ua/bank/currency'


def load_exchange():
    return json.loads(requests.get(URL).text)


def get_exchange(ccy_code):
    for exc in load_exchange():
        if ccy_code == exc['currencyCodeA']:
            return exc
    return False


def get_exchanges(ccy_pattern):
    result = []
    ccy_pattern = re.escape(ccy_pattern) + '.*'
    for exc in load_exchange():
        if re.match(ccy_pattern, exc['currencyCodeA'], re.IGNORECASE) is not None:
            result.append(exc)
    return result
