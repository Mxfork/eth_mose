# {repo_name}: Cross-Chain Bridge Event Listener Simulation

This repository contains a Python-based simulation of a critical backend component for a cross-chain bridge. It acts as an event listener, or oracle, that monitors a bridge contract on a source blockchain (e.g., Ethereum Sepolia), validates deposit events, and simulates the process of initiating a corresponding token mint transaction on a destination blockchain (e.g., Polygon Mumbai).

This script is designed as an architectural showcase, demonstrating a robust, multi-class structure, error handling, and separation of concerns suitable for a real-world decentralized application backend.

## Concept

Cross-chain bridges allow users to transfer assets from one blockchain to another. A common mechanism is the "lock-and-mint" model:
1.  A user **deposits** (locks) tokens into a bridge contract on the source chain.
2.  The bridge contract emits an event (e.g., `DepositMade`) containing details of the deposit.
3.  Off-chain services (listeners/oracles) detect this event.
4.  After validating the event, these services trigger a transaction on the destination chain to **mint** an equivalent amount of a wrapped token and send it to the user's recipient address.

This script simulates the off-chain listener (steps 3 and 4), which is the backbone of the bridge's operation, ensuring that locked assets on one chain are correctly represented on the other.

## Code Architecture

The application is designed with a clear separation of responsibilities, encapsulated within distinct classes:

-   `BlockchainConnector`: Manages the connection to a blockchain via a Web3 RPC endpoint. It abstracts away the details of instantiating the `Web3` object and is used by other components to interact with both the source and destination chains.

-   `EventScanner`: Its sole purpose is to scan the source chain's bridge contract for new `DepositMade` events. It operates in block ranges, manages a chunk-based scanning approach to avoid overwhelming RPC nodes, and formats raw event logs into a clean, usable dictionary.

-   `TransactionValidator`: This crucial security component validates each detected event. It performs a series of checks:
    -   **Replay Protection**: Ensures a unique event nonce has not been processed before.
    -   **Business Rules**: Checks if the deposit amount is within predefined limits.
    -   **Data Integrity**: Verifies that addresses are in the correct format.
    -   **External Checks**: Simulates an API call to a hypothetical external risk-assessment service (e.g., for checking against blacklisted addresses).

-   `TransactionProcessor`: If an event passes validation, this class takes over. It is responsible for constructing and (in this simulation) logging the details of the corresponding `mintTokens` transaction that would be sent to the destination chain's bridge contract.

-   `BridgeOrchestrator`: The central controller that ties all the other components together. It contains the main application loop, manages state (like the last block scanned and the set of processed nonces), and orchestrates the flow of data from scanning to validation to processing. It also includes top-level error handling and resilience logic.

## How it Works

The operational flow of the script is as follows:

1.  **Initialization**: The `BridgeOrchestrator` is instantiated. It initializes connectors for both chains, creates instances of the scanner, validator, and processor, and determines the starting block from which to scan.

2.  **Main Loop**: The orchestrator enters a continuous polling loop.

3.  **Check for New Blocks**: It checks the latest block number on the source chain.

4.  **Event Scanning**: If new blocks have been produced, the `EventScanner` is invoked to query for `DepositMade` events within the new block range. A 6-block confirmation delay is used to reduce the risk of processing events from chain reorganizations.

5.  **Validation**: Each detected event is passed to the `TransactionValidator`. If any validation check fails, the event is logged and discarded.

6.  **Processing**: Valid events are handed off to the `TransactionProcessor`, which simulates the creation of the minting transaction on the destination chain.

7.  **State Update**: If the transaction is successfully processed, the event's nonce is added to the `processed_nonces` set to prevent replay attacks, and the orchestrator updates the `last_scanned_block` number in its state.

8.  **Wait**: The loop then sleeps for a configured interval (`POLLING_INTERVAL_SECONDS`) before repeating the process.

## Usage Example

### 1. Prerequisites
- Python 3.8+
- Access to RPC endpoints for an Ethereum testnet (e.g., Sepolia) and a Polygon testnet (e.g., Mumbai). You can get these from services like [Infura](https://infura.io), [Alchemy](https://www.alchemy.com), or [Ankr](https://www.ankr.com/rpc/).

### 2. Setup

First, clone the repository:
```bash
git clone https://github.com/your-username/{repo_name}.git
cd {repo_name}
```

Create and activate a Python virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

Install the required dependencies:
```bash
pip install -r requirements.txt
```

### 3. Configuration

The script requires RPC URLs for both the source and destination chains. You can provide them as environment variables.

#### Option 1: Export Environment Variables

Export the variables in your terminal session before running the script:
```bash
export SOURCE_CHAIN_RPC_URL='https://rpc.ankr.com/eth_sepolia'
export DESTINATION_CHAIN_RPC_URL='https://rpc.ankr.com/polygon_mumbai'
```

#### Option 2: Use a `.env` File (Recommended for local development)

Alternatively, you can create a `.env` file in the project's root directory:
```dotenv
# .env
SOURCE_CHAIN_RPC_URL='https://rpc.ankr.com/eth_sepolia'
DESTINATION_CHAIN_RPC_URL='https://rpc.ankr.com/polygon_mumbai'
```
*Note: If you use this method, ensure your script is configured to load these variables (e.g., using the `python-dotenv` library) and add `.env` to your `.gitignore` file.*

Using your own private RPC URLs from a dedicated provider is highly recommended for stability and performance.

### 4. Running the Script

Execute the main script:

```bash
python script.py
```

The application will start and begin polling for events. The output will look similar to this:

```
Starting the Cross-Chain Bridge Event Listener Simulation.
This script will poll for 'DepositMade' events on the source chain...
Press Ctrl+C to stop.
2023-10-27 10:30:00,123 - BridgeOrchestrator - INFO - Bridge Orchestrator started. Initial scan block: 4750100
2023-10-27 10:30:35,456 - EventScanner - INFO - Scanning for 'DepositMade' events from block 4750101 to 4750105.
2023-10-27 10:30:37,789 - BridgeOrchestrator - INFO - Scan complete. Last scanned block is now 4750105
... (if an event is found) ...
2023-10-27 10:31:10,112 - EventScanner - INFO - Found 1 events in blocks 4750106-4750110.
2023-10-27 10:31:10,115 - TransactionValidator - INFO - Successfully validated event from tx 0x... with nonce 12345.
2023-10-27 10:31:10,118 - TransactionProcessor - INFO - Processing mint for recipient 0x... with amount 500000000000000000 (from source tx 0x...).
2023-10-27 10:31:10,120 - TransactionProcessor - INFO - [SIMULATION] Would call 'mintTokens' on 0x5B6a9B55B6C8f7B2bEa7bF1f937B8b9933B02b54 for nonce 12345.
2023-10-27 10:31:10,121 - TransactionProcessor - INFO - [SIMULATION] Transaction details: to=0x..., amount=500000000000000000
2023-10-27 10:31:10,122 - BridgeOrchestrator - INFO - Successfully processed event with nonce 12345
```

To stop the listener, press `Ctrl+C`.