import os
import json
import time
import logging
from typing import Dict, Any, Optional

import requests
from web3 import Web3
from web3.contract import Contract
from web3.logs import DISCARD
from web3.types import LogReceipt
from requests.adapters import HTTPAdapter, Retry
from dotenv import load_dotenv

# --- Configuration Loading ---
load_dotenv()

# Configure logging to provide detailed output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(module)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

# --- Constants and Environment Variables ---
# Fetch configuration from environment variables
SOURCE_CHAIN_WSS_URL = os.getenv('SOURCE_CHAIN_WSS_URL')
BRIDGE_CONTRACT_ADDRESS = os.getenv('BRIDGE_CONTRACT_ADDRESS')
DESTINATION_RELAYER_API_URL = os.getenv('DESTINATION_RELAYER_API_URL')

# A simple ABI for the 'TokensLocked' event. In a real application, this would be part of a larger contract ABI.
# event TokensLocked(address indexed token, address indexed sender, address recipient, uint256 amount, uint256 destinationChainId);
BRIDGE_CONTRACT_ABI = json.dumps([
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "token", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "sender", "type": "address"},
            {"indexed": False, "internalType": "address", "name": "recipient", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "amount", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "destinationChainId", "type": "uint256"}
        ],
        "name": "TokensLocked",
        "type": "event"
    }
])


class BlockchainConnector:
    """Manages the connection to a blockchain node via Web3.py."""

    def __init__(self, wss_url: str):
        """
        Initializes the connector with the WebSocket URL.

        Args:
            wss_url (str): The WebSocket URL of the source chain's node.
        """
        if not wss_url:
            raise ValueError("WebSocket URL (SOURCE_CHAIN_WSS_URL) is not configured.")
        self.wss_url = wss_url
        self.web3: Optional[Web3] = None

    def connect(self) -> None:
        """
        Establishes a connection to the blockchain node.
        Includes retry logic for initial connection failures.
        """
        logging.info(f"Attempting to connect to blockchain node at {self.wss_url}...")
        try:
            self.web3 = Web3(Web3.WebsocketProvider(self.wss_url))
            if self.is_connected():
                logging.info(f"Successfully connected to chain ID: {self.web3.eth.chain_id}")
            else:
                raise ConnectionError("Failed to connect to the blockchain node after initialization.")
        except Exception as e:
            logging.error(f"An error occurred while connecting to the node: {e}")
            raise

    def is_connected(self) -> bool:
        """Checks if the Web3 provider is currently connected."""
        return self.web3 is not None and self.web3.is_connected()

    def get_contract(self, address: str, abi: str) -> Contract:
        """
        Returns a Web3 contract instance.

        Args:
            address (str): The contract's address.
            abi (str): The contract's ABI.

        Returns:
            Contract: A Web3 contract object.
        """
        if not self.is_connected():
            logging.error("Cannot get contract, not connected to the blockchain.")
            raise ConnectionError("Not connected to the blockchain.")
        checksum_address = self.web3.to_checksum_address(address)
        return self.web3.eth.contract(address=checksum_address, abi=abi)


class EventParser:
    """Parses raw event logs into a structured format."""

    def __init__(self, contract_abi: str):
        """
        Initializes the parser with the contract ABI.

        Args:
            contract_abi (str): The JSON string of the contract's ABI.
        """
        # Create a temporary Web3 instance just for ABI parsing
        self.contract = Web3().eth.contract(abi=contract_abi)

    def parse_tokens_locked_event(self, event_log: LogReceipt) -> Dict[str, Any]:
        """
        Parses a 'TokensLocked' event log.

        Args:
            event_log (LogReceipt): The raw event log from web3.

        Returns:
            Dict[str, Any]: A dictionary containing structured event data.
        """
        try:
            # The 'process_log' method decodes the log's data and topics
            processed_log = self.contract.events.TokensLocked().process_log(event_log)
            return {
                'transactionHash': processed_log.transactionHash.hex(),
                'blockNumber': processed_log.blockNumber,
                'event': processed_log.event,
                'args': {
                    'token': processed_log.args.token,
                    'sender': processed_log.args.sender,
                    'recipient': processed_log.args.recipient,
                    'amount': str(processed_log.args.amount),  # Convert Wei to string for serialization
                    'destinationChainId': processed_log.args.destinationChainId
                }
            }
        except Exception as e:
            logging.error(f"Failed to parse event log: {event_log}. Error: {e}")
            return {}


class RelayerService:
    """Simulates a relayer by sending event data to a destination endpoint."""

    def __init__(self, api_url: str):
        """
        Initializes the relayer service with the destination API URL.

        Args:
            api_url (str): The endpoint URL to which event data will be sent.
        """
        if not api_url:
            raise ValueError("Destination relayer API URL is not configured.")
        self.api_url = api_url
        self.session = requests.Session()
        # Configure retry strategy for HTTP requests to handle transient network issues
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def relay_transaction_data(self, event_data: Dict[str, Any]) -> bool:
        """
        Sends the parsed event data to the destination relayer API.

        Args:
            event_data (Dict[str, Any]): The structured event data.

        Returns:
            bool: True if the data was sent successfully, False otherwise.
        """
        headers = {'Content-Type': 'application/json'}
        try:
            logging.info(f"Relaying event data to {self.api_url}...")
            response = self.session.post(self.api_url, json=event_data, headers=headers, timeout=10)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            logging.info(f"Successfully relayed transaction {event_data.get('transactionHash')}. Response: {response.json()}")
            return True
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to relay transaction data for {event_data.get('transactionHash')}. Error: {e}")
            return False


class BridgeEventListener:
    """The main orchestrator that listens for blockchain events and coordinates processing."""

    def __init__(self, config: Dict[str, str]):
        """
        Initializes the listener with all necessary components.

        Args:
            config (Dict[str, str]): A dictionary containing configuration values.
        """
        self.config = config
        self.connector = BlockchainConnector(config['wss_url'])
        self.parser = EventParser(config['abi'])
        self.relayer = RelayerService(config['relayer_url'])
        self.contract: Optional[Contract] = None

    def _event_handler(self, event_log: LogReceipt) -> None:
        """The callback function to handle incoming events."""
        logging.info(f"Received new event log for transaction: {event_log.transactionHash.hex()}")
        parsed_data = self.parser.parse_tokens_locked_event(event_log)
        if parsed_data:
            self.relayer.relay_transaction_data(parsed_data)

    def start_listening(self) -> None:
        """
        Connects to the blockchain and starts the event listening loop.
        This method will run indefinitely until interrupted.
        """
        while True: # Outer loop for handling connection drops
            try:
                self.connector.connect()
                contract_address = self.config['contract_address']
                if not self.connector.web3.is_address(contract_address):
                     raise ValueError(f"Invalid BRIDGE_CONTRACT_ADDRESS: {contract_address}")
                
                self.contract = self.connector.get_contract(contract_address, self.config['abi'])
                event_filter = self.contract.events.TokensLocked.create_filter(fromBlock='latest')

                logging.info(f"Starting to listen for 'TokensLocked' events on contract {contract_address}...")
                while self.connector.is_connected():
                    for event in event_filter.get_new_entries():
                        self._event_handler(event)
                    time.sleep(5) # Poll every 5 seconds

            except (ConnectionError, ValueError, Exception) as e:
                logging.error(f"An error occurred in the listening loop: {e}. Attempting to reconnect in 30 seconds...")
                time.sleep(30)
            finally:
                logging.warning("Connection lost or loop interrupted.")


def main():
    """Main function to set up and run the event listener."""
    # Validate that all required environment variables are set
    required_vars = ['SOURCE_CHAIN_WSS_URL', 'BRIDGE_CONTRACT_ADDRESS', 'DESTINATION_RELAYER_API_URL']
    if any(not os.getenv(var) for var in required_vars):
        logging.error("One or more required environment variables are missing. Please check your .env file.")
        logging.error(f"Required: {', '.join(required_vars)}")
        return

    config = {
        'wss_url': SOURCE_CHAIN_WSS_URL,
        'contract_address': BRIDGE_CONTRACT_ADDRESS,
        'relayer_url': DESTINATION_RELAYER_API_URL,
        'abi': BRIDGE_CONTRACT_ABI
    }

    listener = BridgeEventListener(config)
    try:
        listener.start_listening()
    except KeyboardInterrupt:
        logging.info("Shutting down event listener gracefully.")
    except Exception as e:
        logging.critical(f"A critical, unrecoverable error occurred: {e}", exc_info=True)


if __name__ == '__main__':
    main()
