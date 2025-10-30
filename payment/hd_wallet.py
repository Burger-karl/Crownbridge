# # payments/hd_wallet.py
# # WARNING: this is an example. Use well-tested libraries in production.
# from hdwallet import HDWallet
# from hdwallet.symbols import ETH as ETH_SYMBOL
# from typing import Tuple

# def derive_eth_address_from_xpub(xpub: str, index: int) -> Tuple[str, int]:
#     """
#     Derive an Ethereum address from an XPUB and index.
#     Requires the 'hdwallet' library (pip install hdwallet).
#     Returns checksum address.
#     """
#     hdwallet = HDWallet(symbol=ETH_SYMBOL)
#     # set the extended public key
#     hdwallet.from_xpub(xpub=xpub)
#     # derive child - use BIP44 change 0 : path m/44'/60'/0'/0/index
#     path = f"m/44'/60'/0'/0/{index}"
#     child = hdwallet.from_path(path)
#     address = child.p2pkh_address()  # for eth, hdwallet library exposes address
#     # depending on library you may need to convert / checksum
#     return address, index
