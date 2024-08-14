from flask import Flask, jsonify
import requests
import sqlite3
from datetime import datetime, timedelta
import retrying
import os

# Configuration and Constants
TOKEN = os.environ['TOKEN']
TOKEN_CG_ID = os.environ['TOKEN_CG_ID']
TOKEN_NAME = f"{TOKEN}USD"
API_PORT = int(os.environ.get('API_PORT', 5000))
ALLORA_VALIDATOR_API_URL = os.environ.get('ALLORA_VALIDATOR_API_URL', 'http://localhost:1317/')
DATABASE_PATH = os.environ.get('DATABASE_PATH', 'prices.db')
BLOCK_TIME_SECONDS = 5
CGC_API_KEY = os.environ.get('CGC_API_KEY', '')

# Endpoint for querying the latest block
URL_QUERY_LATEST_BLOCK = "cosmos/base/tendermint/v1beta1/blocks/latest"

# HTTP Response Codes
HTTP_RESPONSE_CODE_200 = 200
HTTP_RESPONSE_CODE_400 = 400
HTTP_RESPONSE_CODE_404 = 404
HTTP_RESPONSE_CODE_500 = 500

app = Flask(__name__)

# Retry decorator for network requests
@retrying.retry(wait_exponential_multiplier=1000, wait_exponential_max=10000, stop_max_attempt_number=5)
def fetch_cg_data(url):
    headers = {
        "accept": "application/json",
        "x-cg-demo-api-key": CGC_API_KEY
    }
    return fetch_data(url, headers)

def fetch_data(url, headers={}):
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Raise exception if request fails
    return response.json()

def check_create_table():
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS prices
                          (block_height INTEGER, token TEXT, price REAL,
                          PRIMARY KEY (block_height, token))''')
    print("Prices table created successfully.")

@app.route('/update/<token_name>/<token_from>/<token_to>', methods=['GET'])
@app.route('/update', methods=['GET'])
def update_price(token_name=TOKEN_NAME, token_from=TOKEN_CG_ID, token_to='usd'):
    try:
        # Attempt to initialize token data if not already present
        init_price_token(token_name, token_from, token_to)
    except Exception as e:
        print(f"Initialization failed: {e}")

    try:
        # Construct Coingecko API URL
        url = f'https://api.coingecko.com/api/v3/simple/price?ids={token_from}&vs_currencies={token_to}'
        prices = fetch_cg_data(url)
        
        if token_from.lower() in prices:
            price = prices[token_from.lower()][token_to.lower()]
        else:
            return jsonify({'error': 'Invalid token ID'}), HTTP_RESPONSE_CODE_400
        
        # Get current block height
        block_data = get_latest_network_block()
        latest_block_height = block_data['block']['header']['height']
        token = token_name.lower()
        
        # Save price into the database
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO prices (block_height, token, price) VALUES (?, ?, ?)",
                (latest_block_height, token, price)
            )
            cursor.execute("SELECT count(*) FROM prices WHERE token=?", (token,))
            result = cursor.fetchone()[0]

        print(f"Inserted data point {latest_block_height} : {price}")
        return jsonify({'message': f'{token} price updated successfully, {str(result)}'}), HTTP_RESPONSE_CODE_200
    except Exception as e:
        return jsonify({'error': f'Failed to update {token_name} price: {str(e)}'}), HTTP_RESPONSE_CODE_500

@app.route('/gt/<token>/<block_height>', methods=['GET'])
def get_price(token, block_height):
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT block_height, price 
                FROM prices 
                WHERE token=? AND block_height <= ? 
                ORDER BY ABS(block_height - ?) LIMIT 1
            """, (token.lower(), block_height, block_height))
            result = cursor.fetchone()

        if result:
            return jsonify({'block_height': result[0], 'price': result[1]}), HTTP_RESPONSE_CODE_200
        else:
            return jsonify({'error': 'No price data found for the specified token and block_height'}), HTTP_RESPONSE_CODE_404
    except Exception as e:
        return jsonify({'error': str(e)}), HTTP_RESPONSE_CODE_500

def init_price_token(token_name, token_from, token_to):
    try:
        check_create_table()

        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM prices WHERE token=?", (token_name.lower(),))
            count = cursor.fetchone()[0]

        if count > 0:
            print(f'Data already exists for {token_name} token, {count} entries')
            return

        # Fetch historical data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        block_data = get_latest_network_block()
        latest_block_height = block_data['block']['header']['height']

        # Convert to epoch timestamps
        end_date_epoch = int(end_date.timestamp())
        start_date_epoch = int(start_date.timestamp())
        url = f'https://api.coingecko.com/api/v3/coins/{token_from}/market_chart/range?vs_currency={token_to}&from={start_date_epoch}&to={end_date_epoch}'
        print("Fetching historical data from:", url)
        response = fetch_cg_data(url)
        historical_data = response['prices']

        # Insert historical data into the database
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            for data_point in historical_data:
                price_timestamp = data_point[0]
                blocks_diff = (end_date_epoch - (price_timestamp / 1000)) / BLOCK_TIME_SECONDS
                block_height = int(latest_block_height - blocks_diff)

                if block_height < 1:
                    continue
                
                price = data_point[1]
                cursor.execute("INSERT OR REPLACE INTO prices (block_height, token, price) VALUES (?, ?, ?)", (block_height, token_name.lower(), price))
                print(f"Inserted data point - block {block_height} : {price}")

        print(f'Data initialized successfully for {token_name} token')
    except Exception as e:
        print(f'Failed to initialize data for {token_name} token: {str(e)}')
        raise e 

def get_latest_network_block():
    try:
        url = f"{ALLORA_VALIDATOR_API_URL}{URL_QUERY_LATEST_BLOCK}"
        print(f"Fetching latest network block from: {url}")
        response = fetch_data(url)

        # Handle case where the response might be a list or dictionary
        if isinstance(response, list):
            block_data = response[0]  # Assume it's a list, get the first element
        else:
            block_data = response  # Assume it's already a dictionary

        # Safely accessing block height
        try:
            latest_block_height = int(block_data['block']['header']['height'])
        except KeyError:
            print("Error: Missing expected keys in block data.")
            latest_block_height = 0  # Handle the error appropriately

        return {'block': {'header': {'height': latest_block_height}}}
    except Exception as e:
        print(f'Failed to get block height: {str(e)}')
        return {}

if __name__ == '__main__':
    try:
        init_price_token(TOKEN_NAME, TOKEN_CG_ID, 'usd')
    except Exception as e:
        print(f"Error initializing token data: {str(e)}")
    app.run(host='0.0.0.0', port=API_PORT)
