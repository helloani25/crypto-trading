import json
import os

async def fetch_top_cryptos_json():
    top_cryptos = []
    if not os.path.isfile("./price_tracker.json"):
        return
    with open("price_tracker.json", "r") as f:
        data = json.load(f)
        idx = 0
        for product in data:
            if idx == 25:
                break
            symbol = product['symbol']
            if product['volume_24h'] > 50000000 or product['rank'] < 150 :
                if (product['percent_change_1h'] >= 2 or product['percent_change_24h'] >= 3
                    or product['percent_change_7d'] > 6) and \
                        (product['percent_change_30d'] >= 15 or product['percent_change_60d'] > 30
                         or product['percent_change_90d'] > 40):
                    top_cryptos.append(symbol)
                    idx = idx + 1
                elif product['percent_change_30d'] >= 25 or product['percent_change_60d'] > 45 or product[
                    'percent_change_90d'] > 60:
                    top_cryptos.append(symbol)
                    idx = idx + 1
                elif product['percent_change_1h'] >= 5 and product['percent_change_7d'] > 15:
                    top_cryptos.append(symbol)
                    idx = idx + 1

    print("############# Top crypto prices coinmarketcap #################")
    print([top_cryptos[i] for i in range(len(top_cryptos))])
    return top_cryptos
