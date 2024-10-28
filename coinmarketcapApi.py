import csv
import logging
from operator import itemgetter

import backoff
import polling
import requests
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import json

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
def get_crypto_data(url: str):
    try:
        return requests.get(url, params=parameters, headers=headers, timeout=180, allow_redirects=False, verify=True)
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)


def print_crypto_data(url: str, filename: str) -> None:
    response = get_crypto_data(url)
    data = json.loads(response.text)

    json_formatted_str = json.dumps(data, indent=2)
    # print(json_formatted_str)
    with open(filename, "a") as outfile:
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


def print_crypto_prices(url, filename):
    response = get_crypto_data(url)
    data = json.loads(response.text)

    json_formatted_str = json.dumps(data, indent=2)
    # print(json_formatted_str)
    with open(filename, "w") as outfile:
        outfile.write(json_formatted_str)
    print(data)


def sorted_prices(currencies):
    # https://stackoverflow.com/questions/72899/how-to-sort-a-list-of-dictionaries-by-a-value-of-the-dictionary-in-python
    return sorted(currencies,
                  key=itemgetter('percent_change_1h', 'percent_change_24h', 'percent_change_7d', 'percent_change_30d',
                                 'percent_change_60d', 'percent_change_90d'), reverse=True)


def extract_top_cryptocurrencies(filename):
    top_cryptocurrencies = []
    prices_file = open("price_tracker.csv", 'w', newline='\n')
    with open(filename, "r") as f:
        prices = json.load(f)
        for idx, price in prices["data"].items():
            product = {"symbol": price["symbol"],
                       "name": price["name"],
                       "rank": price["cmc_rank"],
                       "id": price["id"],
                       }
            product.update(price["quote"]["USD"])
            top_cryptocurrencies.append(product)
    print(sorted_prices(top_cryptocurrencies))
    json_formatted_str = json.dumps(sorted_prices(top_cryptocurrencies), indent=2)
    # print(json_formatted_str)
    with open("price_tracker.json", "w") as outfile:
        outfile.write(json_formatted_str)
    csv_headers = top_cryptocurrencies[0].keys()
    writer = csv.DictWriter(prices_file, fieldnames=csv_headers)
    writer.writeheader()
    writer.writerows(sorted_prices(top_cryptocurrencies))


def extract_crypto_symbols() -> str:
    symbols: set = set()
    with open('products.json') as f:
        data = json.load(f)
        for product in data['products']:
            if not product['is_disabled'] and product['base_currency_id'] not in ['EUROC', 'PAX', 'RENDER', 'RONIN', 'TVK', 'GODS', 'XRP','FOX']:
                symbols.add(product['base_name'])
    # return ','.join(symbols)
    return symbols


def extract_crypto_cmc_ids(symbols) -> str:
    ids = {}
    with open('coinmarketcap_idmap.json') as f:
        assets = json.load(f)
        for currency in assets['data']:
            if currency['is_active'] == 1 and currency['name'] in symbols:
                ids[currency['symbol'].upper()] = (currency['rank'], str(currency['id']))
    # return ','.join(ids)
    return ids


if __name__ == '__main__':
    # print_crypto_data('https://pro-api.coinmarketcap.com/v1/cryptocurrency/map', 'coinmarketcap_idmap.json')
    # print_crypto_data('https://sandbox-api.coinmarketcap.com/v1/cryptocurrency/map')
    #  fetch CMC ID for use instead of cryptocurrency symbols to securely identify cryptocurrencies
    #  with our other endpoints.
    coinbase_symbols = extract_crypto_symbols()
    print("Total coinbase currencies %d" % len(coinbase_symbols))
    print(coinbase_symbols)

    ids = extract_crypto_cmc_ids(coinbase_symbols)
    print("Total coinmarketcap currencies %d" % len(ids.keys()))
    print(ids)

    print("Missing currencies in coinmarketcap")
    print(coinbase_symbols - ids.keys())
    print("Missing currencies in coinbase")
    print(ids.keys() - coinbase_symbols)

    parameters = {
        'id': ','.join(list(map(lambda x: x[1], ids.values()))),
        'aux': 'num_market_pairs,cmc_rank,date_added,tags,platform,max_supply,circulating_supply,total_supply,'
               'market_cap_by_total_supply,volume_24h_reported,volume_7d,volume_7d_reported,volume_30d,'
               'volume_30d_reported,is_active,is_fiat'
    }
    #print_crypto_prices('https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest','coinmarketcap_prices.json')
    extract_top_cryptocurrencies('coinmarketcap_prices.json')
