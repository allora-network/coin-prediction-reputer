# Coin Price Reputer

An example application: a node to repute and provide reputation for ETH predictions.

This is an example of a setup for running an Allora Network reputer node for providing ground truth and reputation, where the Allora Network node defers the requests to another container which is responsible for providing the ground truth, which is run in a separate container.
It also provides a means of updating the internal database of the ground truth provider.

One of the goals of this repo is to show how to create a basic reputer providing ground truth for the network as a side container to use it for providing inferences to the Allora Network setup. More complex setups for finer-grained control are recommended for production.

## Components

- **Reputer**: The node that responds to reputer requests from the Allora Network.
- **Truth**: A container that performs reputation tasks, maintains the state of the model, and responds to reputation requests via a simple Flask application. It fetches data from CoinGecko.
- **Updater**: A cron-like container designed to periodically trigger the Truth node's data updates.

Check the `docker-compose.yml` file for the detailed setup of each component.

## Docker-Compose Setup

A complete working example is provided in the `docker-compose.yml` file.

### Steps to Setup

1. **Clone the Repository**

    ```sh
    git clone <repository_url>
    cd <repository_directory>
    ```

2. **Copy and Populate Configuration**

    Copy the example configuration file and populate it with your variables:
    ```sh
    cp config.example.json config.json
    ```

3. **Initialize Reputer**

    Run the following commands from the project's root directory to initialize the reputer:
    ```sh
    chmod +x init.docker
    ./init.docker
    ```
    These commands will:
    - Automatically create Allora keys for your reputer.
    - Export the needed variables from the created account to be used by the reputer node, bundle them with your provided `config.json`, and pass them to the node as environment variables.

4. **Faucet Your Reputer Node**
    
    You can find the offchain reputer node's address in `./worker-data/env_file` under `ALLORA_OFFCHAIN_ACCOUNT_ADDRESS`. [Add faucet funds](https://docs.allora.network/devs/get-started/setup-wallet#add-faucet-funds) to your reputer's wallet before starting it.

5. **Start the Services**

    Run the following command to start the reputer, truth, and updater nodes:
    ```sh
    docker compose up --build
    ```
    To confirm that the reputer successfully sends data to the chain, look for the following log:
    ```json
    {"level":"debug","msg":"Send Reputer Data to chain","txHash":"<tx-hash>","time":"<timestamp>","message":"Success"}
    ```

## Testing Ground Truth Only

This setup allows you to develop your model without the need to bring up the offchain node or the updater. To test the ground truth model only:

1. **Start the Ground Truth Node**

    ```sh
    docker compose up --build truth
    ```
    Wait for the initial data load.

2. **Send Requests**

    - Request ETH price ground truths:
      ```sh
      curl http://127.0.0.1:8000/gt/ETHUSD/1200
      ```
      Expected response:
      ```json
      {"value":"2564.021586281073"}
      ```
    - Add a new data point:
      ```sh
      curl http://127.0.0.1:8000/update/ETHUSD/ethereum/usd
      ```