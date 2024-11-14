from flask import Flask, jsonify
import requests
import sqlite3
from datetime import datetime, timedelta
import retrying
import os
import json
import random


TOKEN = os.environ['TOKEN']
TOKEN_CG_ID = os.environ['TOKEN_CG_ID']
TOKEN_NAME = f"{TOKEN}USD"

URL_QUERY_LATEST_BLOCK="cosmos/base/tendermint/v1beta1/blocks/latest"

API_PORT = int(os.environ.get('API_PORT', 5000))
ALLORA_VALIDATOR_API_URL = str(os.environ.get('ALLORA_VALIDATOR_API_URL','https://allora-api.testnet.allora.network/'))
DATABASE_PATH = os.environ.get('DATABASE_PATH', 'prices.db')

BLOCK_TIME_SECONDS = 10
HTTP_RESPONSE_CODE_200 = 200
HTTP_RESPONSE_CODE_404 = 404
HTTP_RESPONSE_CODE_500 = 500

app = Flask(__name__)

# Define retry decorator
@retrying.retry(wait_exponential_multiplier=1000, wait_exponential_max=10000, stop_max_attempt_number=5)
def fetch_prices(url):
    response = requests.get(url)
    response.raise_for_status()  # Raise exception if request fails
    return response.json()


def check_create_table():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS prices
                      (block_height INTEGER, token TEXT, price REAL, timestamp INTEGER,
                      PRIMARY KEY (block_height, token))''')
    conn.commit()
    conn.close()


@app.route('/update/<token_name>/<token_from>/<token_to>')
@app.route('/update')
def update_price(token_name=TOKEN_NAME, token_from=TOKEN_CG_ID, token_to='usd'):
    # Attempt initializing the token data if not already
    try:
        init_price_token(token_name, token_from, token_to)
    except:
        pass
    # update data
    try:
        # Construct Coingecko API URL
        url = f'https://api.coingecko.com/api/v3/simple/price?ids={token_from}&vs_currencies={token_to}'
        prices = fetch_prices(url)
        
        if token_from.lower() in prices:
            price = prices[token_from.lower()][token_to.lower()]
        else:
            return jsonify({'error': 'Invalid token ID'}), 400
        
        # Get current block height
        block_data = get_latest_network_block()
        block_height = block_data[0]['block']['header']['height']
        token = token_name.lower()
        
        # Get current timestamp
        current_timestamp = int(datetime.now().timestamp())
        
        # Save price into database
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO prices (block_height, token, price, timestamp) VALUES (?, ?, ?, ?)", 
                      (block_height, token, price, current_timestamp))
        cursor.close()

        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM prices WHERE token=? ", (token,))
        result = cursor.fetchone()[0]

        conn.commit()
        conn.close()
        print(f"inserting data point {block_height} : {price}" )
        return jsonify({'message': f'{token} price updated successfully, {str(result)}'}), HTTP_RESPONSE_CODE_200
    except Exception as e:
        return jsonify({'error': f'Failed to update {token_name} price: {str(e)}'}), HTTP_RESPONSE_CODE_500


@app.route('/gt/<token>/<block_height>/<timeframe_minutes>')
def get_price(token, block_height, timeframe_minutes):
    try:
        # First, get the timestamp for the given block height (nonce)
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Get the timestamp for the reference block height
        cursor.execute("""
            SELECT timestamp 
            FROM prices 
            WHERE token=? AND block_height <= ? 
            ORDER BY ABS(block_height - ?) LIMIT 1
        """, (
            token.lower(), 
            block_height,
            block_height
        ))
        base_timestamp_result = cursor.fetchone()
        print(f"Reference time: {datetime.fromtimestamp(base_timestamp_result[0]).strftime('%Y-%m-%d %H:%M:%S')}")
        
        if not base_timestamp_result:
            return jsonify({'error': 'No reference timestamp found for the specified block height'}), HTTP_RESPONSE_CODE_404
            
        # Calculate target timestamp (base timestamp + timeframe_minutes)
        target_timestamp = base_timestamp_result[0] + (int(timeframe_minutes) * 60)
        print(f"Target time: {datetime.fromtimestamp(target_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Find the price closest to the target timestamp
        cursor.execute("""
            SELECT price 
            FROM prices 
            WHERE token=? AND timestamp <= ? 
            ORDER BY ABS(timestamp - ?) LIMIT 1
        """, (
            token.lower(), 
            target_timestamp,
            target_timestamp
        ))
        result = cursor.fetchone()
        conn.close()

        if result:
            print(f"Found price: {result[0]}")
            return str('"' + str(result[0]) + '"'), 200
        else:
            return jsonify({'error': 'No price data found for the calculated timestamp'}), HTTP_RESPONSE_CODE_404
            
    except Exception as e:
        return jsonify({'error': f'Error retrieving price: {str(e)}'}), HTTP_RESPONSE_CODE_500


def init_price_token(token_name, token_from, token_to):
    try:
        check_create_table()
        # Check if there is any existing data for the specified token
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM prices WHERE token=? ", (token_name.lower(),))
        count = cursor.fetchone()[0]
        conn.close()
        
        if count > 0:
            print(f'Data already exists for {token_name} token, {count} entries')
            return

        # Fetch historical data for the current year from Coingecko
        end_date = datetime.now()
        start_date = datetime.now() - timedelta(days=30)

        # Fetch latest block height
        block_data = get_latest_network_block()
        latest_block_height = int(block_data[0]['block']['header']['height'])

        # Convert to epoch timestamp
        end_date_epoch = int(end_date.timestamp())
        start_date_epoch = int(start_date.timestamp())
        url = f'https://api.coingecko.com/api/v3/coins/{token_from}/market_chart/range?vs_currency={token_to}&from={start_date_epoch}&to={end_date_epoch}'
        print("Historical data URL: ", url)
        response = requests.get(url)
        response.raise_for_status()  # Raise exception if request fails
        historical_data = response.json()['prices']
        
        # Parse and insert historical data into the database
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        for data_point in historical_data:
            price_timestamp = int(data_point[0] / 1000)  # Convert milliseconds to seconds
            # Convert timestamp to block height
            blocks_diff = (end_date_epoch - price_timestamp) / BLOCK_TIME_SECONDS
            block_height = int(latest_block_height - blocks_diff)

            if (block_height < 1):
                continue
            
            price = data_point[1]
            cursor.execute("INSERT OR REPLACE INTO prices (block_height, token, price, timestamp) VALUES (?, ?, ?, ?)", 
                          (block_height, token_name.lower(), price, price_timestamp))
            print(f"inserting data point - block {block_height} : {price}" )
        conn.commit()
        conn.close()
        
        print(f'Data initialized successfully for {token_name} token')
    except Exception as e:
        print(f'Failed to initialize data for {token_name} token: {str(e)}')
        raise e 


def get_latest_network_block():
    try:
        url = ALLORA_VALIDATOR_API_URL + URL_QUERY_LATEST_BLOCK
        print(f"latest network block url: {url}")
        response = requests.get(url)
        response.raise_for_status()  # Raise exception if request fails
        return response.json(), HTTP_RESPONSE_CODE_200
    except Exception as e:
        print(f'Failed to get block height: {str(e)}')
        return '{}', HTTP_RESPONSE_CODE_500

if __name__ == '__main__':
    init_price_token(TOKEN_NAME, TOKEN_CG_ID, 'usd')
    app.run(host='0.0.0.0', port=API_PORT)

