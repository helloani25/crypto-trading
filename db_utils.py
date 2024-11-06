import mongodb_util


def execute_price_tracker(db):
    cursor = db.util_fetch_collection_last_inserted('top_cryptos', 'candles')
    result = cursor[0]
    print(result['symbols'].split(","))
    return result['symbols'].split(", ")

def drop_candles(symbols, db):
    for symbol in symbols:
        print('candles_ts_15min_'+symbol)
        print('candles_ts_1w_'+symbol)
        db.util_drop_collection('candles_ts_15min_'+symbol)
        db.util_drop_collection('candles_ts_1w_'+symbol)
        db.util_drop_collection('candles_ts_30min_' + symbol)

def main():
    db = mongodb_util.MongodbUtil()
    db.test_mongodb_setup()
    symbols = execute_price_tracker(db)
    drop_candles(symbols, db)


if __name__ == "__main__":
    main()