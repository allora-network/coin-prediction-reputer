import os
import requests
import sys
import json
import logging


def config_logging(log_file):
    # Remove the default handler from the root logger
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.handlers.clear()

    # Configure logging to only log to file
    logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

ETHUSD_TOKEN = "ETHUSD"
DATA_PROVIDER_API_ADDRESS = os.environ['DATA_PROVIDER_API_ADDRESS']
LOG_FILE = os.environ.get('LOG_FILE', '/tmp/app.log')
config_logging(LOG_FILE)

def get_ground_truth(token_name, timestamp):
    url = f"{DATA_PROVIDER_API_ADDRESS}/gt/{token_name}/{timestamp}"
    response = requests.get(url)
    return response.text

def get_previous_losses(topic, blockHeight):
    url = f"{DATA_PROVIDER_API_ADDRESS}/losses/{topic}/{blockHeight}"
    response = requests.get(url)
    return response.text

if __name__ == "__main__":
    logging.info('Starting application...')
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
        logging.info(f"Arguments: {topic_id}, {blockHeight}, {blockHeightEval}, {timestamp}")
        response_gt = get_ground_truth(token_name=ETHUSD_TOKEN, timestamp=timestamp)
        json_gt = json.loads(response_gt)
        try:
            response_losses = get_previous_losses(topic_id, blockHeightEval)
            json_losses = json.loads(response_losses)
            response_dict = {"gt": json_gt, "losses": json_losses}
        except Exception as e:
            # Print only ground truth if losses are not available
            response_dict = {"gt": json_gt}
        value = json.dumps(response_dict)
    except Exception as e:
        # No gt, no value - error
        value = json.dumps({"error": {str(e)}})
    logging.info(f"Response: {value}")
    print(value)

