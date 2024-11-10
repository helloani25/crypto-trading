# This is a sample Python script.
import asyncio
import json
import threading
import time
from asyncio import create_task, as_completed
from datetime import timezone, datetime

from coinbase.rest import RESTClient
from coinbase.websocket import (WSClient, WSClientConnectionClosedException,
                                WSClientException)
from json import dumps
import mongodb_util
from crypto_price_tracker import fetch_top_cryptos_json


async def rest_client(db):
    client = RESTClient(key_file="coinbase_cloud_api_key_cdp.json")
    #accounts = client.get_accounts()
    #print(dumps(accounts, indent=2))
    products = client.get_products()
    products_json =  json.dumps(products, default=lambda x: x.__dict__, indent = 2)
    print(products_json)
    db.util_drop_collection("products")
    products_deserialized = list(map(vars, products['products']))
    db.util_insert_many(products_deserialized, "products")
    with open("data_files/products.json", "w+") as outfile:
        outfile.write(products_json)


async def subscribe_candle_updates(symbols, wsclient):
    try:
        await wsclient.open_async()
        await wsclient.subscribe_async(product_ids=symbols, channels=["heartbeats", "candles"])
    except WSClientConnectionClosedException as e:
        print("Connection closed! Retry attempts exhausted.",e)
    except WSClientException as e:
        print("Error encountered!",e)


async def create_ws_client_candle_instance(db):
    def on_open():
        print("Connection opened!")

    def on_message(msg):
        print("********")
        print(msg)
        channel_json = (dumps(msg, indent=2))
        print(channel_json)
        # with open("websocket_feed.json", "a") as outfile:
        #    outfile.write(msg)
        channel_json = json.loads(msg)
        # candles granularity 5 min
        if channel_json["channel"] in ["candles"]:
            db.util_insert_one_candle_ts(channel_json)


    def on_close():
        print("Connection closed!")

    wsclient = WSClient(key_file="coinbase_cloud_api_key_cdp.json", on_message=on_message, on_open=on_open,
                        on_close=on_close, verbose=True)
    return wsclient


async def aggregate_candles_ts(db_handle, symbol):
    print("Ran aggregation on candles")
    db_handle.create_timeseries_collection_buckets('candles_ts_5m_'+symbol, 'candles_ts_1h_'+symbol, '1h')
    db_handle.create_timeseries_collection_buckets('candles_ts_5m_'+symbol, 'candles_ts_1d_'+symbol, '1d')
    db_handle.create_timeseries_collection_buckets('candles_ts_5m_'+symbol, 'candles_ts_1mo_'+symbol, '1mo')
    db_handle.create_timeseries_collection_buckets_datetrunc('candles_ts_5m_'+symbol, 'candles_ts_15min_'+symbol, '15min')
    db_handle.create_timeseries_collection_buckets_datetrunc('candles_ts_5m_'+symbol, 'candles_ts_1w_'+symbol, '1w')
    db_handle.create_timeseries_collection_buckets_datetrunc('candles_ts_5m_'+symbol, 'candles_ts_2h_'+symbol, '2h')
    db_handle.create_timeseries_collection_buckets_datetrunc('candles_ts_5m_'+symbol, 'candles_ts_4h_'+symbol, '4h')




def start_background_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def end_event_loop(ws_clients, top_crypto_symbols,  loop, thread):
    for symbol in top_crypto_symbols:
        ws_clients[symbol].close_async()
    loop.call_soon_threadsafe(loop.stop)
    thread.join()
    loop.close()


async def execute_price_tracker(db):
    print(f"started at {time.strftime('%X')}")
    result = await fetch_top_cryptos_json()
    print(f"finished at {time.strftime('%X')}")
    print(result)
    with open("data_files/top_cryptos_candles.json", "w") as outfile:
        outfile.write('\n'.join(result))
    start_time = datetime.now(timezone.utc)
    data = {'symbols': ', '.join(result), 'timestamp': start_time, 'channel': 'candles'}
    db.util_insert_one(data, 'top_cryptos')
    return result

async def unsubscribe_candle_updates(symbols, wsclient):
    try:
        await wsclient.unsubscribe_async(product_ids=symbols, channels=["heartbeats", "candles"])
        await wsclient.close_async()
    except WSClientConnectionClosedException as e:
        print("Connection closed! Retry attempts exhausted.",e)
    except WSClientException as e:
        print("Error encountered!",e)

async def unsubscribe_ws_clients_candles(ws_clients, top_crypto_symbols):
    tasks = []
    remove_cryptos = check_crypto_prices_down(top_crypto_symbols)
    for symbol in remove_cryptos:
        print(symbol)
        tasks.append(create_task(unsubscribe_candle_updates([symbol], ws_clients[symbol])))
    for task in as_completed(tasks):
        await task

async def subscribe_ws_clients_candles(ws_clients, top_crypto_symbols, db):
    tasks = []
    for symbol in top_crypto_symbols:
        print(symbol)
        ws_clients[symbol] = await create_ws_client_candle_instance(db)
        tasks.append(create_task(subscribe_candle_updates([symbol], ws_clients[symbol])))
    for task in as_completed(tasks):
        await task

async def aggregate_all_candles(top_crypto_symbols, db):
    tasks = []
    for symbol in top_crypto_symbols:
        print(symbol)
        tasks.append(create_task(aggregate_candles_ts(db, symbol)))
    for task in as_completed(tasks):
        await task

def check_crypto_prices_down(top_cryptos):
    # TODO: add logic to remove cryptos
    return []

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
    top_crypto_symbols = []
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=start_background_loop, args=(loop,), daemon=True)
    thread.start()
    # loop forever logic must start here
    try:
        while True:
            asyncio.run_coroutine_threadsafe(rest_client(db), loop)
            future = asyncio.run_coroutine_threadsafe(execute_price_tracker(db), loop)
            top_crypto_symbols = future.result()
            top_crypto_symbols.append("BTC-USD")
            # print(top_crypto_symbols)
            asyncio.run_coroutine_threadsafe(subscribe_ws_clients_candles(ws_clients, top_crypto_symbols, db), loop)
            asyncio.run_coroutine_threadsafe(aggregate_all_candles(top_crypto_symbols, db), loop)
            asyncio.run_coroutine_threadsafe(unsubscribe_ws_clients_candles(ws_clients, top_crypto_symbols), loop)
            time.sleep(900) # sleep for 15 minutes
    # loop forever logic must end here
    except Exception as e:
        print(f"Exception: {e}")
    finally:
        end_event_loop(ws_clients, top_crypto_symbols, loop, thread)


if __name__ == "__main__":
    main()
