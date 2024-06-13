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

API_PORT = int(os.environ.get('API_PORT', 5000))
ALLORA_VALIDATOR_API_URL = str(os.environ.get('ALLORA_VALIDATOR_API_URL','http://localhost:1317/emissions/v1/network_loss/'))
app = Flask(__name__)

DATABASE_PATH = os.environ.get('DATABASE_PATH', 'prices.db')
GEN_TEST_DATA = bool(os.environ.get('GEN_TEST_DATA', False))
WORKER_ADDRESS_TEST_1 = str(os.environ.get('WORKER_ADDRESS_TEST_1', "allo1tvh6nv02vq6m4mevsa9wkscw53yxvfn7xt8rud"))

TOKEN_NAME = f"{TOKEN}USD"

HTTP_RESPONSE_CODE_200 = 200
HTTP_RESPONSE_CODE_400 = 400
HTTP_RESPONSE_CODE_404 = 404
HTTP_RESPONSE_CODE_500 = 500

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
                      (timestamp INTEGER PRIMARY KEY, token TEXT, price REAL)''')
    conn.commit()
    conn.close()


@app.route('/update/<token_name>/<token_from>/<token_to>')
def update_price(token_name, token_from, token_to):
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
        
        timestamp = int(datetime.now().timestamp())
        token = token_name.lower()
        
        # Save price into database
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO prices (timestamp, token, price) VALUES (?, ?, ?)", (timestamp, token, price))
        cursor.close()

        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM prices WHERE token=? ", (token,))
        result = cursor.fetchone()[0]

        conn.commit()
        conn.close()
        print(f"inserting data point {timestamp} : {price}" )
        return jsonify({'message': f'{token} price updated successfully, {str(result)}'}), HTTP_RESPONSE_CODE_200
    except Exception as e:
        return jsonify({'error': f'Failed to update {token_name} price: {str(e)}'}), HTTP_RESPONSE_CODE_500


@app.route('/gt/<token>/<timestamp>')
def get_price(token, timestamp):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, price FROM prices WHERE token=? ORDER BY ABS(timestamp - ?) LIMIT 1", (token.lower(), timestamp,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return str('"' + str(result[1]) + '"'), 200
    else:
        return jsonify({'error': 'No price data found for the specified token and timestamp'}), HTTP_RESPONSE_CODE_404


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
            timestamp = int(data_point[0] / 1000)  # Convert milliseconds to seconds
            price = data_point[1]
            cursor.execute("INSERT INTO prices (timestamp, token, price) VALUES (?, ?, ?)", (timestamp, token_name.lower(), price))
            print(f"inserting data point {timestamp} : {price}" )
        conn.commit()
        conn.close()
        
        print(f'Data initialized successfully for {token_name} token')
    except Exception as e:
        print(f'Failed to initialize data for {token_name} token: {str(e)}')
        raise e 


def get_test_losses_data():
    combined_value = random.uniform(100, 200)
    naive_value = random.uniform(100, 200)
    inferer_value = random.uniform(100, 200)
    one_out_inferer_value = random.uniform(100, 200)
    forecaster_value = random.uniform(100, 200)
    out_out_forecaster_value = random.uniform(100, 200)
    out_in_forecaster_value =  random.uniform(100, 200)
    test_data = '{"combined_value":"' + str(combined_value) + '","inferer_values":[{"worker":"' + WORKER_ADDRESS_TEST_1 + '","value":"' + str(inferer_value) + '"}],"forecaster_values":[{"worker":"' + WORKER_ADDRESS_TEST_1 + '","value":"' + str(forecaster_value) + '"}],"naive_value":"' + str(naive_value) + '","one_out_inferer_values":[{"worker":"' + WORKER_ADDRESS_TEST_1 + '","value":"' + str(one_out_inferer_value) + '"}],"one_out_forecaster_values":[{"worker":"' + WORKER_ADDRESS_TEST_1 + '","value":"' + str(out_out_forecaster_value) + '"}],"one_in_forecaster_values":[{"worker":"' + WORKER_ADDRESS_TEST_1 + '","value":"' + str(out_in_forecaster_value) + '"}]}'
    return test_data, HTTP_RESPONSE_CODE_200


def get_losses_data(topic, blockHeight):
    try:
        url = ALLORA_VALIDATOR_API_URL + topic + "/" + blockHeight
        print(f"url: {url}")
        response = requests.get(url)
        response.raise_for_status()  # Raise exception if request fails
        return response.json(), HTTP_RESPONSE_CODE_200
    except Exception as e:
        print(f'Failed to get data for {topic} topic for url: {url}: {str(e)}')
        return '{}', HTTP_RESPONSE_CODE_500


@app.route('/losses/<topic>/<blockHeight>')
def get_losses(topic, blockHeight):
    print(f"Getting losses for {topic} , {blockHeight}")
    if GEN_TEST_DATA:
        print("Generating test data for topic " + topic + " and block height " + blockHeight)
        test_data = get_test_losses_data()
        print("Test data: " + str(test_data))
        return test_data
    else:
        try:
            losses_data = get_losses_data(topic, blockHeight)
            # Check if the response contains an error code. Any will do.
            losses_data_json = json.loads(losses_data)
            if losses_data_json.get('code'):
                error_dict = {"error": losses_data_json.get('message')}
                print("Error in fetching losses data: ", error_dict)
                return jsonify(error_dict), HTTP_RESPONSE_CODE_500
            else:
                return jsonify(losses_data_json), HTTP_RESPONSE_CODE_200

        except Exception as e:
            print(f'Failed to get data for {topic} topic: {str(e)}')
            return '{}', HTTP_RESPONSE_CODE_500

if __name__ == '__main__':
    init_price_token(TOKEN_NAME, TOKEN_CG_ID, 'usd')
    app.run(host='0.0.0.0', port=API_PORT)

