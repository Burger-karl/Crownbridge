# payments/services.py
import os
from decimal import Decimal
from web3 import Web3
from web3.middleware import geth_poa_middleware
from django.conf import settings

# environment vars
RPC_URLS = {
    # example keys - set in env
    "ethereum": os.getenv("WEB3_RPC_ETHEREUM"),
    "bsc": os.getenv("WEB3_RPC_BSC"),
}

USDT_CONTRACTS = {
    # Put the USDT contract addresses per chain (set in env or here)
    "ethereum": os.getenv("USDT_CONTRACT_ETHEREUM"),  # e.g. 0xdac17f...
    "bsc": os.getenv("USDT_CONTRACT_BSC"),
}


def get_web3(chain: str) -> Web3:
    rpc = RPC_URLS.get(chain)
    if not rpc:
        raise RuntimeError(f"No RPC URL defined for chain {chain}")
    w3 = Web3(Web3.HTTPProvider(rpc))
    # some chains (BSC, etc) require PoA middleware
    if chain == "bsc":
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return w3


# ERC20 ABI fragment needed for events and decimals/balanceOf
ERC20_ABI_MIN = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
]


def get_token_contract(w3: Web3, token_address: str):
    return w3.eth.contract(address=w3.toChecksumAddress(token_address), abi=ERC20_ABI_MIN)


def get_token_decimals(chain: str) -> int:
    w3 = get_web3(chain)
    contract_addr = USDT_CONTRACTS.get(chain)
    contract = get_token_contract(w3, contract_addr)
    return contract.functions.decimals().call()


def raw_to_human(amount_raw: int, decimals: int) -> Decimal:
    return Decimal(amount_raw) / (Decimal(10) ** decimals)


def human_to_raw(amount: Decimal, decimals: int) -> int:
    return int(amount * (Decimal(10) ** decimals))
