# Setting up the Env

## Installing coinbase api module

### Inside the PyCharm IDE Terminal install
```
pip3 install coinbase-advanced-py 
```
### Activating the virtual environment outside the IDE in the Terminal

```
 % source ./crypto-trading/venv/bin/activate 
(venv)  % pip3 list  
Package              Version
-------------------- --------
argcomplete          3.2.3
backoff              2.2.1
certifi              2024.2.2
cffi                 1.16.0
charset-normalizer   3.3.2
click                8.1.7
coinbase-advanced-py 1.2.0
cryptography         42.0.5
idna                 3.6
packaging            24.0
pip                  23.2.1
pipx                 1.4.3
platformdirs         4.2.0
pycparser            2.21
PyJWT                2.8.0
requests             2.31.0
urllib3              2.2.1
userpath             1.9.2
websockets           12.0

```

### Set the Interpreter to the venv python 13.2
Under settings set the interpreter

## TRADING KEY

* Creating Trading Keys
* Log into Coinbase Cloud.
* Navigate to Access => API keys.
* Click Create API key, select Trading key, and click Next.
* In the Create trading API key dialog, configure:
  1. API key nickname.
  2. Portfolio (e.g., Default).
  3. Permission level (View, Trade, Transfer).
  4. Allowlist IPs.
  5. Click Create & Download.
  6. Click Complete 2-factor authentication and enter your Coinbase Cloud 2FA code. The key automatically downloads as a JSON file.
  In the final popup, you can optionally copy the API Key Name and Private Key (which are also in the JSON download). Read the warning and click Got it to finish.

### Export tradingkey and private key
```
export COINBASE_API_KEY="organizations/dsfddf23132"
export COINBASE_API_SECRET="-----BEGIN EC PRIVATE KEY-----\n<<<<<<<<<<<<Actual Key>>>>>>>>>>>>>>\n-----END EC PRIVATE KEY-----\n"
```
## Setting up coinmarketcap api
Signup for coinmarketcap API and choose basic plan

**Test Cred API_KEY**
```
'b54bcf4d-1bca-4e8e-9a24-22ff2c3d462c'
```

```
headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': '------------KEY------------',
    'Accept-Encoding': 'deflate, gzip'
}
```
**copy the code and setup backoff**
https://coinmarketcap.com/api/documentation/v1/#section/Quick-Start-Guide


https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-os-x/

# Installing MongoDB 8.0 Community Edition
'''
brew tap mongodb/brew
brew update
brew install mongodb-community@8.0
'''


## The installation includes the following binaries:

* The mongod server

* The mongos sharded cluster query router

* The MongoDB Shell, mongosh

## Brew Managed MongoDB
#### To run MongoDB (i.e. the mongod process) as a macOS service, run:
```
brew services start mongodb-community@8.0
```
#### To stop a mongod running as a macOS service, use the following command as needed:
```
brew services stop mongodb-community@8.0
```
#### If you started MongoDB as a macOS service:
```
brew services list
```
## Manually Running MongoDB
#### To run mongod manually as a background process using a config file, run:
```
mongod --config /usr/local/etc/mongod.conf --fork
```
#### If you started MongoDB manually as a background process:
```
ps aux | grep -v grep | grep mongod
```

## Connect and Use MongoDB
To begin using MongoDB, connect mongosh to the running instance. From a new terminal, issue the following:
```
mongosh
```
## File Locations for Installation
#### configuration file
/usr/local/etc/mongod.conf
#### log directory
/usr/local/var/log/mongodb
#### data directory
/usr/local/var/mongodb

## Uninstall
* Remove the downloaded .tgz archive.

* Retap the formula.
```
brew untap mongodb/brew && brew tap mongodb/brew
```
* Retry the install.
```
brew install mongodb-community@8.0
```


### Connect to a Local Deployment on the Default Port
To connect to a MongoDB deployment running on localhost with default port 27017, run mongosh without any options:
```
mongosh
```
This is equivalent to the following command:
```
mongosh "mongodb://localhost:27017"
```

```
$ mongosh
Current Mongosh Log ID:	671fc9618933631edf01ada8
Connecting to:		mongodb://127.0.0.1:27017/?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+2.2.2
Using MongoDB:		7.0.2
Using Mongosh:		2.2.2

```
### Connect to a Local Deployment on a Non-Default Port
To specify a port to connect to on localhost, you can use either:

A connection string with the chosen port

The --port command-line option

For example, the following commands connect to a deployment running on localhost port 28015:
```
mongosh "mongodb://localhost:28015"

mongosh --port 28015
```

### CronTab CoinMarketCap API fetch cryptos
crontab -l



5 * * * * cd /Users/<user_name>/PycharmProjects/crypto-trading; venv/bin/python '/Users/<user_name>/PycharmProjects/crypto-trading/coinmarketcapApi.py'
