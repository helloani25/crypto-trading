# This is a sample Python script.
import asyncio
import json
import threading
import time
from asyncio import create_task, as_completed

from coinbase.websocket import (WSClient, WSClientConnectionClosedException,
                                WSClientException)
import mongodb_util
from coinbase.rest import RESTClient
from json import dumps, loads


def get_default_portfolio(rest_client, db):
    portfolios = rest_client.get_portfolios()
    portfolios_deserialized = list(map(vars, portfolios['portfolios']))
    print(portfolios_deserialized)

    portfolios_json =  dumps(portfolios, default=lambda x: x.__dict__, indent = 2)
    with open("data_files/portfolios.json", "w+") as outfile:
        outfile.write(portfolios_json)
    db.util_insert_many(portfolios_deserialized, "portfolios")
    return portfolios['portfolios'][0]['uuid']


def get_crypto_positions(rest_client, portfolio_uuid):
    portfolio_breakdown = rest_client.get_portfolio_breakdown(portfolio_uuid=portfolio_uuid, currency='USD')
    asset_positions = []
    total_balance = portfolio_breakdown['breakdown']['portfolio_balances']['total_balance']['value']
    for spot_position in portfolio_breakdown['breakdown']['spot_positions']:
        if spot_position['available_to_trade_fiat'] > 0:
            asset_positions.append({
                        'symbol' :  spot_position['asset'],
                        'cash_value': float(spot_position['available_to_trade_fiat']),
                        'quantity_available': float(spot_position['total_balance_crypto']),
                        'cost' : float(spot_position['cost_basis']['value'])
            })
    spot_json = dumps(portfolio_breakdown['breakdown']['spot_positions'], default=lambda x: x.__dict__, indent = 2)
    print(spot_json)
    with open("spot.json", "w+") as outfile:
        outfile.write(spot_json)
    return asset_positions, total_balance

async def subscribe_ticker_batch_updates(symbols, wsclient):
    try:
        await wsclient.open_async()
        await wsclient.subscribe_async(product_ids=symbols, channels=["heartbeats", "ticker_batch"])
    except WSClientConnectionClosedException as e:
        print("Connection closed! Retry attempts exhausted.",e)
    except WSClientException as e:
        print("Error encountered!",e)

async def unsubscribe_ticker_batch_updates(symbols, wsclient):
    try:
        await wsclient.unsubscribe_async(product_ids=symbols, channels=["heartbeats", "ticker_batch"])
        await wsclient.close_async()
    except WSClientConnectionClosedException as e:
        print("Connection closed! Retry attempts exhausted.",e)
    except WSClientException as e:
        print("Error encountered!",e)

async def create_ws_client_sub_instance(db):
    def on_open():
        print("Connection opened!")

    def on_message(message):
        data = json.loads(message)
        print(data)
        # if data["channel"] in ["ticker_batch"]:
        #     #with open("Output1.txt", "a") as f:
        #     #    f.write(json.dumps(data, indent=2) + "\n")
        #     for event in data['events'][0]['ticker_batch']:
        #         #  c = dict(a, **b) this method fails in Python 3 when keys are not strings.
        #         order = dict({'product_id': data['events'][0]['product_id']}, **event)
        #         db.util_insert_one(order, "order_book")

    def on_close():
        print("Connection closed!")

    wsclient = WSClient(key_file="coinbase_cloud_api_key_cdp.json", on_message=on_message, on_open=on_open,
                        on_close=on_close, verbose=True)
    return wsclient

def start_background_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()

def check_crypto_prices_down(top_cryptos):
    # TODO: add logic to remove cryptos
    return []

def end_event_loop(ws_clients, crypto_symbols,  loop, thread):
    for symbol in crypto_symbols:
        ws_clients[symbol].close_async()
    loop.call_soon_threadsafe(loop.stop)
    thread.join()
    loop.close()


async def subscribe_ws_client_ticker_batch(ws_clients, crypto_symbols, db):
    tasks = []
    for symbol in crypto_symbols:
        print(symbol)
        ws_clients[symbol] = await create_ws_client_sub_instance(db)
        tasks.append(create_task(subscribe_ticker_batch_updates([symbol+'-USD'], ws_clients[symbol])))
    for task in as_completed(tasks):
        await task

async def unsubscribe_ws_client_ticker_batch(ws_clients, crypto_symbols):
    tasks = []
    remove_cryptos = check_crypto_prices_down(crypto_symbols)
    for symbol in remove_cryptos:
        print(symbol)
        tasks.append(create_task(unsubscribe_ticker_batch_updates([symbol], ws_clients[symbol])))
    for task in as_completed(tasks):
        await task


# Press the green button in the gutter to run the script.
def main():
    """
        track websocket client and crypto currency channel and close if too old or prices are falling.
        Use a hash [currency] => ws_client and check if the connection already exists before creating a new
        process.
        Close the websocket  client.close()
        Terminate the existing process for connection to the websocket process.shutdown()
        remove currency from hash
    """
    db = mongodb_util.MongodbUtil()
    db.test_mongodb_setup()
    ws_clients = {}
    rest_client = RESTClient(key_file="coinbase_cloud_api_key_cdp.json", timeout=5, rate_limit_headers=True, verbose=True)
    portfolio_uuid = get_default_portfolio(rest_client, db)
    asset_positions, total_balance = get_crypto_positions(rest_client, portfolio_uuid)
    crypto_symbols = list(map(lambda a: a['symbol'], asset_positions))
    crypto_symbols.remove('USD')

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=start_background_loop, args=(loop,), daemon=True)
    thread.start()
    # loop forever logic must start here
    try:
        while True:
            #future = asyncio.run_coroutine_threadsafe(execute_price_tracker(db), loop)
            #top_crypto_symbols = future.result()
            asyncio.run_coroutine_threadsafe(subscribe_ws_client_ticker_batch(ws_clients, crypto_symbols, db), loop)
            asyncio.run_coroutine_threadsafe(unsubscribe_ws_client_ticker_batch(ws_clients, crypto_symbols), loop)
            time.sleep(900) # sleep for 15 minutes
    # loop forever logic must end here
    except Exception as e:
        print(f"Exception: {e}")
    finally:
        end_event_loop(ws_clients, crypto_symbols, loop, thread)


if __name__ == "__main__":
    main()
