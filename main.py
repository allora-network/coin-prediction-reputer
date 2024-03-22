import os
import requests
import sys
import json


ETHUSD_TOKEN = "ETHUSD"
TRUTH_ADDRESS = os.environ['TRUTH_API_ADDRESS']

def process(token_name, timestamp):
    url = f"{TRUTH_ADDRESS}/get/{token_name}/{timestamp}"
    response = requests.get(url)
    return response.text
    

if __name__ == "__main__":
    # Your code logic with the parsed argument goes here
    try:
        # Not using to discriminate by topicId for simplicity.
        # topic_id = sys.argv[1]
        if len(sys.argv) >= 3:
            timestamp = sys.argv[2]
        response = process(token_name=ETHUSD_TOKEN, timestamp=timestamp)

    except Exception as e:
        response = json.dumps({"error": {str(e)}})
    print(response)
