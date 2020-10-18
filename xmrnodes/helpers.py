from requests import get as r_get

def determine_crypto(url):
    data = {"method": "get_block_header_by_height", "params": {"height": 0}}
    hashes = {
        "monero": [
            "418015bb9ae982a1975da7d79277c2705727a56894ba0fb246adaabb1f4632e3", #mainnet
            "48ca7cd3c8de5b6a4d53d2861fbdaedca141553559f9be9520068053cda8430b", #testnet
            "76ee3cc98646292206cd3e86f74d88b4dcc1d937088645e9b0cbca84b7ce74eb"  #stagenet
        ],
        "wownero": [
            "a3fd635dd5cb55700317783469ba749b5259f0eeac2420ab2c27eb3ff5ffdc5c", #mainnet
            "d81a24c7aad4628e5c9129f8f2ec85888885b28cf468597a9762c3945e9f29aa", #testnet
        ]
    }
    try:
        r = r_get(url + "/json_rpc", json=data, timeout=5)
        r.raise_for_status()
        assert "result" in r.json()
        hash = r.json()["result"]["block_header"]["hash"]
        crypto = "unknown"
        for c, h in hashes.items():
            if hash in h:
                crypto = c
                break
        return crypto
    except:
        return "unknown"
