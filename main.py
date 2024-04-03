import os
import requests
import sys
import json


ETHUSD_TOKEN = "ETHUSD"
TRUTH_ADDRESS = os.environ['TRUTH_API_ADDRESS']

def get_ground_truth(token_name, timestamp):
    url = f"{TRUTH_ADDRESS}/gt/{token_name}/{timestamp}"
    response = requests.get(url)
    return response.text

def get_previous_losses(topic):
    url = f"{TRUTH_ADDRESS}/losses/{topic}"
    response = requests.get(url)
    return response.text

if __name__ == "__main__":
    # Your code logic with the parsed argument goes here
    try:
        # Not using to discriminate by topicId for simplicity.
        topic_id = sys.argv[1]
        if len(sys.argv) >= 3:
            timestamp = sys.argv[2]
        response_gt = get_ground_truth(token_name=ETHUSD_TOKEN, timestamp=timestamp)
        json_gt = json.loads(response_gt)
        try:
            response_losses = get_previous_losses(topic=topic_id)
            json_losses = json.loads(response_losses)
            response_dict = {"gt": json_gt, "losses": json_losses}
            # Serialize as JSON
            value = json.dumps(response_dict)
        except Exception as e:
            # Print only ground truth if losses are not available
            response_dict = {"gt": json_gt}
            value = json.dumps(response_dict)
    except Exception as e:
        # No gt, no value - error
        value = json.dumps({"error": {str(e)}})
    print(value)
