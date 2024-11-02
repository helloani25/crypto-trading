# This is a sample Python script.
import asyncio
import json
import threading
import time
from asyncio import create_task, as_completed
from datetime import timezone, datetime

from coinbase.websocket import (WSClient, WSClientConnectionClosedException,
                                WSClientException)
import mongodb_util
from crypto_price_tracker import fetch_top_cryptos_json

async def subscribe_level2_updates(symbols, wsclient):
    try:
        await wsclient.open_async()
        await wsclient.subscribe_async(product_ids=symbols, channels=["heartbeats", "level2"])
    except WSClientConnectionClosedException as e:
        print("Connection closed! Retry attempts exhausted.")
    except WSClientException as e:
        print("Error encountered!")

async def unsubscribe_level2_updates(symbols, wsclient):
    try:
        await wsclient.unsubscribe_async(product_ids=symbols, channels=["heartbeats", "level2"])
        await wsclient.close_async()
    except WSClientConnectionClosedException as e:
        print("Connection closed! Retry attempts exhausted.")
    except WSClientException as e:
        print("Error encountered!")

async def create_ws_client_sub_instance(db):
    def on_open():
        print("Connection opened!")

    def on_message(message):
        data = json.loads(message)
        print(data)
        if data["channel"] in ["level2"]:
            #with open("Output1.txt", "a") as f:
            #    f.write(json.dumps(data, indent=2) + "\n")
            for event in data['events'][0]['updates']:
                #  c = dict(a, **b) this method fails in Python 3 when keys are not strings.
                order = dict({'product_id': data['events'][0]['product_id']}, **event)
                db.util_insert_one(order, "order_book")

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

def end_event_loop(ws_clients, top_crypto_symbols,  loop, thread):
    for symbol in top_crypto_symbols:
        ws_clients[symbol].close_async()
    loop.call_soon_threadsafe(loop.stop)
    thread.join()
    loop.close()


async def execute_price_tracker(db):
    print(f"started at {time.strftime('%X')}")
    cursor = db.util_fetch_collection_last_inserted('top_cryptos', 'candles')
    start_time = datetime.now(timezone.utc)
    result = cursor[0]
    data = {'symbols': result['symbols'], 'timestamp': start_time, 'channel': 'level2'}
    db.util_insert_one(data, 'top_cryptos')
    print(f"finished at {time.strftime('%X')}")
    with open("data_files/top_cryptos_level2.json", "w") as outfile:
        outfile.write(result['symbols'])
    print(result['symbols'].split(","))
    return result['symbols'].split(",")

async def subscribe_ws_client_level2(ws_clients, top_crypto_symbols, db):
    tasks = []
    for symbol in top_crypto_symbols:
        print(symbol)
        ws_clients[symbol] = await create_ws_client_sub_instance(db)
        tasks.append(create_task(subscribe_level2_updates([symbol], ws_clients[symbol])))
    for task in as_completed(tasks):
        await task

async def unsubscribe_ws_client_level2(ws_clients, top_crypto_symbols, db):
    tasks = []
    remove_cryptos = check_crypto_prices_down(top_crypto_symbols)
    for symbol in remove_cryptos:
        print(symbol)
        tasks.append(create_task(unsubscribe_level2_updates([symbol], ws_clients[symbol])))
    for task in as_completed(tasks):
        await task


# Press the green button in the gutter to run the script.
def main():
    """
        track websocket client and crypto currency channel and close if too old or prices are falling.
        Use a hash [currency] => ws_client and check if the connection already exists before creating a new
        process.
        Close the websocket client client.close()
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
            future = asyncio.run_coroutine_threadsafe(execute_price_tracker(db), loop)
            top_crypto_symbols = future.result()
            top_crypto_symbols.append("BTC-USD")
            # print(top_crypto_symbols)
            asyncio.run_coroutine_threadsafe(subscribe_ws_client_level2(ws_clients, top_crypto_symbols, db), loop)
            asyncio.run_coroutine_threadsafe(unsubscribe_ws_client_level2(ws_clients, top_crypto_symbols, db), loop)
            time.sleep(900) # sleep for 15 minutes
    # loop forever logic must end here
    except Exception as e:
        print(f"Exception: {e}")
    finally:
        end_event_loop(ws_clients, top_crypto_symbols, loop, thread)


if __name__ == "__main__":
    main()
