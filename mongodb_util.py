from datetime import datetime
from typing import Any, Mapping

import pymongo
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import constants

MAX_POOL_SIZE = 12  # DB thread pool size for MongoDB


class MongodbUtil:
    client = MongoClient(constants.localhost_uri, server_api=ServerApi('1'), maxPoolSize=MAX_POOL_SIZE, compressors='zstd',
                         zlibCompressionLevel=9)

    def test_mongodb_setup(self):
        # Send a ping to confirm a successful connection
        try:
            MongodbUtil.client.admin.command('ping')
            print("Pinged your deployment. You successfully connected to MongoDB!")
        except Exception as e:
            print(e)

    def create_database(self, database_name) -> Database[Mapping[str, Any] | Any]:
        return MongodbUtil.client[database_name]

    def create_timeseries_collection(self, collection_name):
        collection_exists = self.create_database("CryptoTrading").list_collection_names().__contains__(
            collection_name)
        db = self.create_database("CryptoTrading")
        if not collection_exists:
            db.create_collection(
                name=collection_name,
                timeseries={
                    "timeField": "start",
                    "granularity": "seconds"  # seconds, minutes or hours
                }
            )
        db[collection_name].create_index([("start", pymongo.DESCENDING)])
        return db[collection_name]

    # https://www.mongodb.com/docs/manual/reference/operator/aggregation-pipeline/
    # https://www.mongodb.com/docs/manual/core/timeseries/timeseries-procedures/
    def create_timeseries_collection_buckets(self, source_collection_name, target_collection_name, granularity):
        db = self.create_database("CryptoTrading")
        conversion_stage = {
            '$addFields': {
                'convertedLow': {'$toDecimal': "$low"},
                'convertedHigh': {'$toDecimal': "$high"},
                'convertedOpen': {'$toDecimal': "$open"},
                'convertedClose': {'$toDecimal': "$close"},
                'convertedVolume': {'$toDouble': "$volume"}
            }
        }
        date_granularity = {
            'year': "$date.year",
            'month': "$date.month"
        }
        if granularity == '1d':
            date_granularity['day'] = "$date.day"
        if granularity == '1h':
            date_granularity['day'] = "$date.day"
            date_granularity['hour'] = "$date.hour"
        db[source_collection_name].aggregate([
            conversion_stage,
            {
                '$project': {
                    'date': {
                        '$dateToParts': {'date': "$start"}
                    },
                    "start": 1,
                    "convertedLow": 1,
                    "convertedHigh": 1,
                    "convertedOpen": 1,
                    "convertedClose": 1,
                    "convertedVolume": 1
                }
            },
            {
                '$group': {
                    '_id': {
                        'date': date_granularity
                    },
                    'sumVolume': {'$sum': "$convertedVolume"},
                    'minLow': {'$min': "$convertedLow"},
                    'maxHigh': {'$max': "$convertedHigh"},
                    'firstOpen': {'$first': "$convertedOpen"},
                    'lastClose': {'$last': "$convertedClose"},
                }
            },
            {
                '$merge': {
                    'into': target_collection_name,
                    'on': "_id",
                    'whenMatched': "replace",
                    'whenNotMatched': "insert"
                }
            },
        ])
        print(f'Aggregated for the  {granularity}')

    # {"start":"1712046600",
    # "high":"66733.12",
    # "low":"66595.24",
    # "open":"66595.24",
    # "close":"66631.26",
    # "volume":"36.281617",
    # "product_id":"BTC-USD"}
    '''
    * Use in $project Stage  
    * get bucket aggregation with  bucketMaxSpanSeconds
    https://www.mongodb.com/docs/manual/reference/operator/aggregation/
    https://www.mongodb.com/developer/products/mongodb/bucket-pattern/
    
    https://stackoverflow.com/questions/26787709/mongo-aggregate-query-pulling-out-last-7-days-worth-of-data-node-js
    https://www.mongodb.com/docs/manual/reference/operator/aggregation/locf/
    https://medium.com/data-reply-it-datatech/time-series-with-mongodb-dd60f8d6acd6
    
    To create an On-Demand Materialized view, use the $merge aggregation pipeline stage to transform and store your data:
    https://www.mongodb.com/docs/manual/core/timeseries/timeseries-build-materialized-views/#build-materialized-views-on-top-of-time-series-data
    '''

    def util_insert_one_candle_ts(self, data):
        for candle in data["events"][0]["candles"]:
            db = self.create_timeseries_collection("candles_ts_5m_" + candle["product_id"])
            candle = {
                "start": datetime.fromtimestamp(int(candle["start"])),
                "low": candle["low"],
                "high": candle["high"],
                "open": candle["open"],
                "close": candle["close"],
                "volume": candle["volume"]
            }
            if db.find_one({"start": candle["start"]}) is None:
                db.insert_one(candle)
            print("Inserted one documents")

    def fetch_db_collection(self, document_name) -> Collection:
        db = self.create_database("CryptoTrading")
        return db[document_name]

    def util_insert_many(self, data, document_name):
        db_collection = self.fetch_db_collection(document_name)
        db_collection.insert_many(data)
        print("Inserted many documents")

    def util_insert_one(self, data, document_name):
        db_collection = self.fetch_db_collection(document_name)
        db_collection.insert_one(data)
        print("Inserted one documents")

    def util_delete_many(self, filter_name, filter_value, document_name):
        db_collection = self.fetch_db_collection(document_name)
        db_collection.delete_many({filter_name: filter_value})
        print("Deleted many documents")


    def util_drop_collection(self, document_name):
        db_collection = self.fetch_db_collection(document_name)
        db_collection.drop()
        print("Dropped collection")

    def util_fetch_collection_last_inserted(self, document_name, channel):
        db_collection = self.fetch_db_collection(document_name)
        size = db_collection.count_documents({'channel': channel})
        return db_collection.find({'channel': channel}).skip(size - 1)

    def util_fetch_one(self, document_name, filter_name, filter_value):
        db_collection = self.fetch_db_collection(document_name)
        return db_collection.find_one({filter_name: filter_value})



