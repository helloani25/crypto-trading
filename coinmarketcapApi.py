import csv
import logging
from operator import itemgetter
from typing import Tuple, Dict, Any

import backoff
import polling
import requests
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import json
import mongodb_util

headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': 'd905ff43-addb-44fc-8407-af83aff01a37',
    'Accept-Encoding': 'deflate, gzip'
}

api_logger = logging.getLogger('coinmarketcap_api_logger')
api_logger.addHandler(logging.StreamHandler())
api_logger.setLevel(logging.ERROR)

# session = Session()
# session.headers.update(headers)

"""

400 (Bad Request) The server could not process the request, likely due to an invalid argument.
401 (Unauthorized) Your request lacks valid authentication credentials, likely an issue with your API Key.
402 (Payment Required) Your API request was rejected due to it being a paid subscription plan with an overdue balance. Pay the balance in the Developer Portal billing tab and it will be enabled.
403 (Forbidden) Your request was rejected due to a permission issue, likely a restriction on the API Key's associated service plan. Here is a convenient map of service plans to endpoints.
429 (Too Many Requests) The API Key's rate limit was exceeded; consider slowing down your API Request frequency if this is an HTTP request throttling error. Consider upgrading your service plan if you have reached your monthly API call credit limit for the day/month.
500 (Internal Server Error) An unexpected server issue was encountered.

HTTP Status	Error Code	Error Message
401	1001 [API_KEY_INVALID]	This API Key is invalid.
401	1002 [API_KEY_MISSING]	API key missing.
402	1003 [API_KEY_PLAN_REQUIRES_PAYMENT]	Your API Key must be activated. Please go to pro.coinmarketcap.com/account/plan.
402	1004 [API_KEY_PLAN_PAYMENT_EXPIRED]	Your API Key's subscription plan has expired.
403	1005 [API_KEY_REQUIRED]	An API Key is required for this call.
403	1006 [API_KEY_PLAN_NOT_AUTHORIZED]	Your API Key subscription plan doesn't support this endpoint.
403	1007 [API_KEY_DISABLED]	This API Key has been disabled. Please contact support.
429	1008 [API_KEY_PLAN_MINUTE_RATE_LIMIT_REACHED]	You've exceeded your API Key's HTTP request rate limit. Rate limits reset every minute.
429	1009 [API_KEY_PLAN_DAILY_RATE_LIMIT_REACHED]	You've exceeded your API Key's daily rate limit.
429	1010 [API_KEY_PLAN_MONTHLY_RATE_LIMIT_REACHED]	You've exceeded your API Key's monthly rate limit.
429	1011 [IP_RATE_LIMIT_REACHED]	You've hit an IP rate limit.
"""

error_codes = {1008: 60, 1009: 86400, 1010: 2592000}


def fatal_code(e):
    return ((e.response.status_code == 429
             and e.response.status.error_code in [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1011]) or
            (e.response.status_code > 400))


def backoff_hdlr(details):
    print("Backing off {wait:0.1f} seconds after {tries} tries "
          "calling function {target} with args {args} and kwargs "
          "{kwargs}".format(**details))


"""
Response
{
  "data" : {
    ...
  },
  "status": {
    "timestamp": "2018-06-06T07:52:27.273Z",
    "error_code": 400,
    "error_message": "Invalid value for \"id\"",
    "elapsed": 0,
    "credit_count": 0
  }
}

"""


@backoff.on_predicate(
    backoff.runtime,
    predicate=lambda response: response.status_code == 429,
    max_tries=20,
    value=lambda r: error_codes[int(r.status.error_code)],
    jitter=backoff.random_jitter(500),
    on_backoff=backoff_hdlr
)
@backoff.on_exception(backoff.expo,
                      requests.exceptions.HTTPError,
                      max_time=300,
                      logger=api_logger)
@backoff.on_exception(backoff.expo,
                      requests.exceptions.Timeout,
                      max_time=300,
                      logger=api_logger)
@backoff.on_exception(backoff.expo,
                      requests.exceptions.RequestException,
                      max_time=300,
                      giveup=fatal_code,
                      logger=api_logger)
def get_crypto_data(url: str, parameters: dict):
    try:
        return requests.get(url, params=parameters, headers=headers, timeout=180, allow_redirects=False, verify=True)
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)


def print_crypto_data(url: str, filename: str) -> None:
    response = get_crypto_data(url, parameters={})
    data = json.loads(response.text)

    json_formatted_str = json.dumps(data, indent=2)
    # print(json_formatted_str)
    with open(filename, "w+") as outfile:
        outfile.write(json_formatted_str)
    print(data)


@backoff.on_predicate(
    backoff.runtime,
    predicate=lambda response: response.status_code == 429,
    max_tries=20,
    value=lambda r: error_codes[int(r.status.error_code)],
    jitter=backoff.random_jitter(500),
    on_backoff=backoff_hdlr
)
@backoff.on_exception(backoff.expo,
                      requests.exceptions.HTTPError,
                      max_time=300,
                      logger=api_logger)
@backoff.on_exception(backoff.expo,
                      requests.exceptions.Timeout,
                      max_time=300,
                      logger=api_logger)
@backoff.on_exception(backoff.expo,
                      requests.exceptions.RequestException,
                      max_time=300,
                      giveup=fatal_code,
                      logger=api_logger)
def get_crypto_prices():
    try:
        return polling.poll(
            lambda: requests.get('https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest'),
            step=60,
            timeout=180)
        # poll_forever=True)
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)


def print_crypto_prices(url, filename, parameters):
    response = get_crypto_data(url, parameters)
    data = json.loads(response.text)

    json_formatted_str = json.dumps(data, indent=2)
    # print(json_formatted_str)
    with open(filename, "w+") as outfile:
        outfile.write(json_formatted_str)
    print(data)


def sorted_prices(currencies):
    # https://stackoverflow.com/questions/72899/how-to-sort-a-list-of-dictionaries-by-a-value-of-the-dictionary-in-python
    return sorted(currencies,
                  key=itemgetter('percent_change_1h', 'percent_change_24h', 'percent_change_7d', 'percent_change_30d',
                                 'percent_change_60d', 'percent_change_90d'), reverse=True)


def extract_top_cryptocurrencies(filename, db):
    top_cryptocurrencies = []
    with open(filename, "r") as f:
        prices = json.load(f)
        for idx, price in prices["data"].items():
            cb_product = db.util_fetch_one('products',
                                           {'base_name': price['symbol'].capitalize(), 'quote_currency_id': 'USD'})
            if cb_product is None:
                cb_product = db.util_fetch_one('products', {'base_currency_id': price['symbol'].upper(),
                                                            'quote_currency_id': 'USD'})
            if cb_product is None:
                print(f"Symbol : {price['symbol']} does not exist")
                continue
            product = {"symbol": cb_product['product_id'],
                       "name": price["name"],
                       "rank": price["cmc_rank"],
                       "id": price["id"],
                       }
            product.update(price["quote"]["USD"])
            top_cryptocurrencies.append(product)
    print(sorted_prices(top_cryptocurrencies))
    json_formatted_str = json.dumps(sorted_prices(top_cryptocurrencies), indent=2)
    # print(json_formatted_str)
    with open("data_files/price_tracker.json", "w+") as outfile:
        outfile.write(json_formatted_str)
    csv_headers = top_cryptocurrencies[0].keys()
    prices_file = open("data_files/price_tracker.csv", 'w+', newline='\n')
    writer = csv.DictWriter(prices_file, fieldnames=csv_headers)
    writer.writeheader()
    writer.writerows(sorted_prices(top_cryptocurrencies))


def extract_coinbase_crypto_symbols() -> tuple[dict[Any, Any], dict[Any, Any]]:
    cb_base_names = {}
    cb_base_currencies = {}
    with open('data_files/products.json', "r") as f:
        data = json.load(f)
        for product in data['products']:
            if not product['is_disabled'] \
                    and product['base_currency_id'] not in ['EURC', 'USDC', 'PAX', 'RENDER', 'RONIN', 'TVK', 'GODS',
                                                            'XRP', 'FOX'] \
                    and product['quote_currency_id'] == 'USD':
                cb_base_names[product['base_name'].upper()] = product['product_id']
                cb_base_currencies[product['base_currency_id'].upper()] = product['product_id']
    # return ','.join(symbols)
    return cb_base_names, cb_base_currencies


def extract_crypto_cmc_ids(cb_base_names, cb_base_currencies) -> dict[Any, tuple[Any, str]]:
    ids = {}
    missing_symbols = {}
    with (open('data_files/coinmarketcap_idmap.json', 'r') as f):
        assets = json.load(f)
        for currency in assets['data']:
            symbol = currency['symbol'].upper()
            name = currency['name'].upper()
            if currency['is_active'] == 1 \
                    and symbol in cb_base_currencies.keys() \
                    and name in cb_base_names.keys():
                ids[cb_base_currencies[symbol]] = (currency['rank'], str(currency['id']))
            else:
                print(f"Symbol {symbol} name {name} not found")
                missing_symbols[symbol] = currency['name']
    with open('data_files/coinmarketcap_missing_symbols.json', 'w+') as outfile:
        outfile.write(json.dumps(missing_symbols, indent=2))

    # return ','.join(ids)
    return ids


if __name__ == '__main__':
    print_crypto_data('https://pro-api.coinmarketcap.com/v1/cryptocurrency/map', 'data_files/coinmarketcap_idmap.json')
    #print_crypto_data('https://sandbox-api.coinmarketcap.com/v1/cryptocurrency/map')
    #  fetch CMC ID for use instead of cryptocurrency symbols to securely identify cryptocurrencies
    #  with our other endpoints.
    cb_base_names, cb_base_currencies = extract_coinbase_crypto_symbols()
    print("Total coinbase currencies in base names %d" % len(cb_base_names))
    print(cb_base_names.keys())

    print("Total coinbase currencies in base currencies %d" % len(cb_base_currencies))
    print(cb_base_currencies.keys())

    ids = extract_crypto_cmc_ids(cb_base_names, cb_base_currencies)
    print("Total coinmarketcap currencies %d" % len(ids.keys()))
    print(ids)

    parameters = {
        'id': ','.join(list(map(lambda x: x[1], ids.values()))),
        'aux': 'num_market_pairs,cmc_rank,date_added,tags,platform,max_supply,circulating_supply,total_supply,'
               'market_cap_by_total_supply,volume_24h_reported,volume_7d,volume_7d_reported,volume_30d,'
               'volume_30d_reported,is_active,is_fiat'
    }
    print_crypto_prices('https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest',
                        'data_files/coinmarketcap_prices.json', parameters)
    db = mongodb_util.MongodbUtil()
    db.test_mongodb_setup()
    extract_top_cryptocurrencies('data_files/coinmarketcap_prices.json', db)
