from requests import get as r_get

def is_monero(url):
    data = {"method": "get_block_header_by_height", "params": {"height": 0}}
    try:
        r = r_get(url + "/json_rpc", json=data)
        r.raise_for_status()
        assert "result" in r.json()
        is_xmr = r.json()["result"]["block_header"]["hash"] == "418015bb9ae982a1975da7d79277c2705727a56894ba0fb246adaabb1f4632e3"
        return is_xmr
    except:
        return False
