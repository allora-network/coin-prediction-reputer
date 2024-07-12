import os
import sys
import requests

def main():
    DATA_PROVIDER_API_ADDRESS = os.environ['DATA_PROVIDER_API_ADDRESS']
    url = f"{DATA_PROVIDER_API_ADDRESS}/update"

    response = requests.get(url)
    if response.status_code == 200:
        # Request was successful
        print(response.text)
        sys.exit(0)
    else:
        # Request failed
        print(f"Request failed with status code: {response.status_code}")
        print("Error: ", response.text)
        sys.exit(0) # Exit with code 0 to not trigger an error

if __name__ == "__main__":
    main()
