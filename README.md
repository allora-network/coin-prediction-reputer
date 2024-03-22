# Coin Price Reputer

An example application: a node to repute and provide ground truth for ETH predictions.

This is an example of a setup for running an Allora Network reputer node for providing ground truth and reputation, where the Allora Network node defers the requests to another container which is responsible for providing the ground truth, which is run in a separate container.
It also provides a means of updating the internal database of the ground truth provider.

One of the goals of this repo is to show how to create a basic reputer providing ground truth for the network as a side container to use it for providing inferences to the Allora Network setup. More complex setups for finer-grained control are recommended for production.

# Components

* **worker**: The node that will respond to reputer requests from the Allora Network heads.
* **head**: An Allora Network head node. This is not required for running your node in the Allora Network, but it will help for testing your node emulating a network.
* **truth**: A container that performs reputation, keeps state of the model and responds to requests for reputation through a simple Flask application to be managed internally. It fetches data from CoinGecko.


# docker

## Structure

- head and worker nodes are built upon `Dockerfile_b7s` file

The `Dockerfile_b7s` file is functional but simple, so you may want to change it to fit your needs, if you attempt to expand upon the current setup.

For further details, please check the base repo [allora-inference-base](https://github.com/allora-network/allora-inference-base).

###  Application path

By default, the application runtime lives under `/app`, as well as the Python code the worker provides (`/app/main.py`). The current user needs to have write permissions on `/app/runtime`.

### Data volume and permissions

It is recommended to mount `/data` as a volume, to persist the node databases of peers, functions, etc. which are defined in the flags passed to the worker.
You can create this folder e.g. `mkdir data` in the repo root directory.

It is recommended to set up two different `/data` volumes. It is suggested to use `worker-data` for the worker, `head-data` for the head.

Troubleshooting: A conflict may happen between the uid/gid of the user inside the container(1001) with the permissions of your own user.
To make the container user have permissions to write on the `/data` volume, you may need to set the UID/GID from the user running the container. You can get those in linux/osx via `id -u` and `id -g`.
The current `docker-compose.yml` file shows the `worker` service setting UID and GID. As well, the `Dockerfile` also sets UID/GID values.


# Docker-Compose Setup
A full working example is provided in the `docker-compose.yml` file.


## Setup

1. **Generate keys**: Create a set of keys for your head and worker nodes. These keys will be used in the configuration of the head and worker nodes.

**Create head keys:**
```
docker run -it --entrypoint=bash -v ./head-data:/data alloranetwork/allora-inference-base:latest -c "mkdir -p /data/keys && (cd /data/keys && allora-keys)"
```

**Create worker keys**
```
docker run -it --entrypoint=bash -v ./worker-data:/data alloranetwork/allora-inference-base:latest -c "mkdir -p /data/keys && (cd /data/keys && allora-keys)"
```

Important note: If no keys are specified in the volumes, new keys will be automatically created inside `head-data/keys` and `worker-data/keys` when first running step 4.

2. **Connect the worker node to the head node**:

At this step, both worker and head nodes identities are generated inside `head-data/keys` and `worker-data/keys`.
To instruct the worker node to connect to the head node:
- run `cat head-data/keys/identity` to extract the head node's peer_id 
- copy this printed peer_id to replace the `head-id` placeholder value specified inside the docker-compose.yml file (or docker-compose.arm64.yml based on your configuration) when running the worker service: `--boot-nodes=/ip4/172.22.0.100/tcp/9010/p2p/head-id`

3. **Run setup**

Once all the above is set up, run `docker compose up`
This will bring up the head, the worker and the truth nodes (which will run an initial update). 

4. **Keep it updated**

You can keep the state updated by hitting the url: 

```
http://localhost:8000/update/<token-name>/<token-from>/<token-to>
```
where:
token-name: the name of the token on internal database, e.g. ETHUSD
token-from: the name of the token on Coingecko naming, e.g. ethereum
token-to: the name of the token on Coingecko naming, e.g. usd

It is expected that this endpoint is hit periodically, being crucial for maintaining the accuracy of the ground truth provided.

## Testing docker-compose setup

The head node has the only open port, and responds to requests in port 6000.

Example request:
```
curl --location 'http://localhost:6000/api/v1/functions/execute' --header 'Accept: application/json, text/plain, */*' --header 'Content-Type: application/json;charset=UTF-8' --data '{
    "function_id": "bafybeigpiwl3o73zvvl6dxdqu7zqcub5mhg65jiky2xqb4rdhfmikswzqm",
    "method": "allora-inference-function.wasm",
    "parameters": null,
    "topic": "1",
    "config": {
        "env_vars": [
            {                              
                "name": "BLS_REQUEST_PATH",
                "value": "/api"
            },
            {                              
                "name": "ALLORA_ARG_PARAMS",
                "value": "1711064725"
            }
        ],
        "number_of_nodes": -1,
        "timeout" : 2
    }
}'
```


# Testing ground truth only

This setup allows to develop your model without need for bringing up the head and worker.
To only test the ground truth model, you can simply follow these steps:
- Run `docker compose up --build truth` and wait for the initial data load.
- Requests can now be sent, e.g. request ETH price ground truths as in: 
  ```
    $ curl http://localhost:8000/get/ETHUSD/1711105645
    {"value":"3227.311942291347"}
  ```
  or add a new data point:
  ```
    $ curl http://localhost:8000/update/ETHUSD/ethereum/usd
  ```


## Connecting to the Allora network
 In order to connect to the Allora network, both the head and the worker need to register against it.  More details on [allora-inference-base](https://github.com/allora-network/allora-inference-base) repo.
The following optional flags are used in the `command:` section of the `docker-compose.yml` file to define the connectivity with the Allora network.

```
--allora-chain-key-name=index-provider  # your local key name in your keyring
--allora-chain-restore-mnemonic='pet sock excess ...'  # your node's Allora address mnemonic
--allora-node-rpc-address=  # RPC address of a node in the chain
--allora-chain-topic-id=  # The topic id from the chain that you want to provide predictions for
```
In order for the nodes to register with the chain, a funded address is needed first.
If these flags are not provided, the nodes will not register to the appchain and will not attempt to connect to the appchain.


