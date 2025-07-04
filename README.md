# {repo_name}

A simulation of a robust event listener component for a cross-chain bridge. This system is designed to monitor a smart contract on a source blockchain for specific events (e.g., `TokensLocked`), parse them, and relay the data to a destination service, mimicking the core function of a bridge relayer node.

## Concept

Cross-chain bridges allow users to transfer assets or data from one blockchain to another. A common mechanism involves locking assets in a smart contract on the source chain, which triggers the minting of equivalent wrapped assets on the destination chain.

This process requires a reliable off-chain component, often called a **relayer** or **oracle**, to watch for the lock events on the source chain and securely submit a corresponding transaction on the destination chain. This script simulates the 'listening' and 'relaying' part of that process.

It connects to a source chain (e.g., Ethereum) via a WebSocket, listens for a specific `TokensLocked` event from a bridge contract, and upon receiving an event, it parses the data and POSTs it to a mock relayer API endpoint for the destination chain.

## Code Architecture

The script is designed with a modular, object-oriented architecture to separate concerns and enhance maintainability.

- **`BlockchainConnector`**: This class is responsible for all direct interactions with the source blockchain. It manages the WebSocket connection using `web3.py`, handles connection establishment and health checks, and provides an interface to get contract instances.

- **`EventParser`**: A utility class that takes raw event logs from the blockchain and decodes them into a structured, human-readable Python dictionary. It uses the contract's ABI to understand the event's data structure, ensuring correct interpretation of topics and data payloads.

- **`RelayerService`**: This class simulates the action of relaying information to the destination chain. It takes the parsed event data and makes an HTTP POST request to a configured API endpoint. It includes robust error handling and a retry mechanism (using `requests` and `Retry`) to cope with transient network failures.

- **`BridgeEventListener`**: The core orchestrator of the system. It initializes and coordinates the other components. Its main `start_listening` method contains the primary loop that:
    1. Establishes the blockchain connection.
    2. Creates a filter to watch for new `TokensLocked` events.
    3. Polls for new events periodically.
    4. Passes any new events to the `EventParser` and then to the `RelayerService`.
    5. Handles connection drops and attempts to reconnect automatically.

- **`main()` function**: The entry point of the script. It loads configuration from environment variables, validates them, instantiates the `BridgeEventListener`, and starts the listening process. It also includes a graceful shutdown mechanism for `KeyboardInterrupt`.

### Data Flow
```
+-----------------------+      +---------------------------+      +------------------+      +---------------------------+
| Source Chain Node     | <--> |   BlockchainConnector     |      |   EventParser    |      |     RelayerService        |
| (e.g., Infura WSS)    |      | (Connects & Gets Logs)    |----->| (Decodes Log)    |----->| (POSTs to Destination API)|
+-----------------------+      +---------------------------+      +------------------+      +---------------------------+
          ^                                        |
          |                                        |
          |           +----------------------------v-----------+
          +-----------|         BridgeEventListener            |
                      | (Orchestrates, Polls, Handles Errors)  |
                      +----------------------------------------+
```

## How it Works

1.  **Configuration**: The script starts by loading necessary configuration from a `.env` file. This includes the WebSocket URL for the source chain node, the address of the bridge smart contract, and the API endpoint for the destination relayer.
2.  **Connection**: The `BlockchainConnector` establishes a persistent WebSocket connection to the source chain. This is more efficient for listening to real-time events than polling via HTTP.
3.  **Filter Creation**: The `BridgeEventListener` uses the `web3.py` library to create an event filter on the bridge contract. This filter is specifically configured to watch for the `TokensLocked` event from the latest block onwards.
4.  **Event Loop**: The script enters an infinite loop, periodically (e.g., every 5 seconds) querying the event filter for new entries using `filter.get_new_entries()`.
5.  **Event Handling**: When a new event log is detected, it is passed to a handler function.
6.  **Parsing**: The `EventParser` decodes the raw log data. The event's indexed `topics` and non-indexed `data` are converted into a clean dictionary containing details like the recipient's address, the amount transferred, and the destination chain ID.
7.  **Relaying**: The `RelayerService` takes this parsed data and sends it as a JSON payload in an HTTP POST request to the destination API endpoint. This simulates the relayer informing the destination chain's logic about the lock event.
8.  **Resilience**: The entire process is wrapped in error handling blocks. If the WebSocket connection drops, the main loop will catch the exception, wait for a specified interval, and attempt to reconnect, ensuring the listener is resilient to network disruptions.

## Usage Example

### 1. Prerequisites
- Python 3.8+
- `pip` package installer

### 2. Installation

Clone the repository and install the required dependencies:
```bash
git clone https://github.com/your-username/{repo_name}.git
cd {repo_name}
pip install -r requirements.txt
```

### 3. Configuration

Create a file named `.env` in the root directory of the project and add the following configuration. You will need to provide your own values.

```ini
# .env file

# WebSocket URL for the source chain node (e.g., from Infura, Alchemy).
# Example for Ethereum Sepolia testnet:
SOURCE_CHAIN_WSS_URL="wss://sepolia.infura.io/ws/v3/YOUR_INFURA_PROJECT_ID"

# The address of the deployed bridge smart contract to monitor.
BRIDGE_CONTRACT_ADDRESS="0x........................................"

# The API endpoint of the destination chain's relayer service.
# You can use a mock service like httpbin.org for testing.
DESTINATION_RELAYER_API_URL="https://httpbin.org/post"
```

**Note**: Replace `YOUR_INFURA_PROJECT_ID` and the contract address with actual values.

### 4. Running the Script

Execute the script from your terminal:

```bash
python script.py
```

The script will start, connect to the blockchain, and begin listening for events. 

### Expected Output

When the script is running, you will see logs like this:
```
2023-10-27 14:30:00 - INFO - main - Attempting to connect to blockchain node at wss://sepolia.infura.io/ws/v3/...
2023-10-27 14:30:02 - INFO - main - Successfully connected to chain ID: 11155111
2023-10-27 14:30:02 - INFO - main - Starting to listen for 'TokensLocked' events on contract 0x........................................
```

When a `TokensLocked` event is emitted by the target contract on the source chain, the listener will detect it and you will see:

```
2023-10-27 14:35:10 - INFO - main - Received new event log for transaction: 0x[...tx_hash...]
2023-10-27 14:35:10 - INFO - main - Relaying event data to https://httpbin.org/post...
2023-10-27 14:35:11 - INFO - main - Successfully relayed transaction 0x[...tx_hash...]. Response: { ...httpbin_response... }
```
