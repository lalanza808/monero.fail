from requests import get as r_get

def is_monero(url):
    data = {"method": "get_block_header_by_height", "params": {"height": 0}}
    known_hashes = [
        "418015bb9ae982a1975da7d79277c2705727a56894ba0fb246adaabb1f4632e3", #mainnet
        "48ca7cd3c8de5b6a4d53d2861fbdaedca141553559f9be9520068053cda8430b", #testnet
        "76ee3cc98646292206cd3e86f74d88b4dcc1d937088645e9b0cbca84b7ce74eb"  #stagenet
    ]
    try:
        r = r_get(url + "/json_rpc", json=data)
        r.raise_for_status()
        assert "result" in r.json()
        is_xmr = r.json()["result"]["block_header"]["hash"] in known_hashes
        return is_xmr
    except:
        return False
