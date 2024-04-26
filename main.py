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

def get_previous_losses(topic, blockHeight):
    url = f"{TRUTH_ADDRESS}/losses/{topic}/{blockHeight}"
    response = requests.get(url)
    return response.text

if __name__ == "__main__":
    # Your code logic with the parsed argument goes here
    try:
        if len(sys.argv) < 5:
            value = json.dumps({"error": f"Not enough arguments provided: {len(sys.argv)}, expected 4 arguments: topic_id, timestamp, timestampEval, default_arg"})
        else:
            topic_id = sys.argv[1]
            # extract topic_id , removing the suffix "/reputer"
            topic_id = topic_id.split("/")[0]
            blockHeight = sys.argv[2]
            blockHeightEval = sys.argv[3]
            timestamp = sys.argv[4]  # timestamp of the block

        response_gt = get_ground_truth(token_name=ETHUSD_TOKEN, timestamp=timestamp)
        json_gt = json.loads(response_gt)
        try:
            response_losses = get_previous_losses(topic_id, blockHeightEval)
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

