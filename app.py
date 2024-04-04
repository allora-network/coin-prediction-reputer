from flask import Flask, jsonify
import requests
import sqlite3
from datetime import datetime, timedelta
import retrying
import os 


ETHUSD_TOKEN = "ETHUSD"
API_PORT = int(os.environ.get('TRUTH_API_PORT', 5000))
ALLORA_VALIDATOR_API_URL = str(os.environ.get('ALLORA_VALIDATOR_API_URL','http://localhost:1317/emissions/v1/network_loss/'))
app = Flask(__name__)

DATABASE_PATH = 'prices.db'


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
    print("Table created successfully")


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
        token = token_name.upper()
        
        # Save price into database
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO prices (timestamp, token, price) VALUES (?, ?, ?)", (timestamp, token, price))
        conn.commit()
        conn.close()
        
        print(f"inserting data point {timestamp} : {price}" )
        return jsonify({'message': f'{token} price updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': f'Failed to update {token_name} price: {str(e)}'}), 500


@app.route('/gt/<token>/<timestamp>')
def get_eth_price(token, timestamp):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, price FROM prices WHERE token=? AND timestamp <= ? ORDER BY timestamp DESC LIMIT 1", (token, timestamp))
    result = cursor.fetchone()
    conn.close()
    if result:
        return str('"' + str(result[1]) + '"'), 200
    else:
        return jsonify({'error': 'No price data found for the specified token and timestamp'}), 404


def init_price_token(token_name, token_from, token_to):
    try:
        check_create_table()
        # Check if there is any existing data for the specified token
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM prices WHERE token=? LIMIT 1", (token_name.upper(),))
        count = cursor.fetchone()[0]
        conn.close()
        
        if count > 0:
            print(f'Data already exists for {token_name} token')
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
            cursor.execute("INSERT INTO prices (timestamp, token, price) VALUES (?, ?, ?)", (timestamp, token_name.upper(), price))
            print(f"inserting data point {timestamp} : {price}" )
        conn.commit()
        conn.close()
        
        print(f'Data initialized successfully for {token_name} token')
    except Exception as e:
        print(f'Failed to initialize data for {token_name} token: {str(e)}')
        raise e 


def get_test_data():
    test_data = '{"networkInference":"1234.56","inferrerInferences":[{"node":"allo1inf1","value":"1234.01"},{"node":"allo1inf2","value":"1235.01"},{"node":"allo1inf0000","value":"1234.61"}],"forecasterInferences":[{"node":"allo1inf1","value":"1234.20"},{"node":"allo1inf2","value":"1235.70"},{"node":"allo1inf1111","value":"1234.52"}],"naiveNetworkInference":"1234.30","oneOutNetworkInferences":[{"node":"allo1inf1","value":"1234.20"},{"node":"allo1inf2","value":"1234.70"},{"node":"allo1inf0000","value":"1235.45"}],"oneInNetworkInferences":[{"node":"allo1inf1","value":"1234.20"},{"node":"allo1inf2","value":"1234.70"},{"node":"allo1inf1111","value":"1235.45"}]}'
    return test_data, 200

def get_losses_data(topic):
    try:
        response = requests.get(ALLORA_VALIDATOR_API_URL + topic)
        response.raise_for_status()  # Raise exception if request fails
        return response.json(), 200
    except Exception as e:
        print(f'Failed to get data for {topic} token: {str(e)}')
        print(f'Not providing last losses for {topic} token')
        return '{}', 200

@app.route('/losses/<topic>')
def get_losses(topic):
    print(f"Getting losses for {topic}")
    try:
        # Change this when real data is available
        # get losses data(topic)
        return get_test_data()
    
    except Exception as e:
        print(f'Failed to get data for {topic} token: {str(e)}')
        print(f'Not providing last losses for {topic} token')
        return '{}', 200

if __name__ == '__main__':
    init_price_token(ETHUSD_TOKEN, 'ethereum', 'usd')
    app.run(host='0.0.0.0', port=API_PORT)

