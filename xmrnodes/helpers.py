import sys
import socket
from levin.section import Section
from levin.bucket import Bucket
from levin.ctypes import *
from levin.constants import LEVIN_SIGNATURE
from requests import get as r_get
from xmrnodes import config


def make_request(url: str, path="/get_info", data=None):
    if is_onion(url):
        proxies = {"http": f"socks5h://{config.TOR_HOST}:{config.TOR_PORT}"}
        timeout = 18
    else:
        proxies = None
        timeout = 6
    r = r_get(url + path, timeout=timeout, proxies=proxies, json=data)
    r.raise_for_status()
    return r

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
        r = make_request(url, "/json_rpc", data)
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

def is_onion(url: str):
    _split = url.split(":")
    if len(_split) < 2:
        return False
    if _split[1].endswith(".onion"):
        return True
    else:
        return False

def retrieve_peers():
    try:
        sock = socket.socket()
        sock.connect((config.NODE_HOST, int(config.NODE_PORT))
    except:
        sys.stderr.write("unable to connect to %s:%d\n" % (config.NODE_HOST, int(config.NODE_PORT))
        sys.exit()

    bucket = Bucket.create_handshake_request()

    sock.send(bucket.header())
    sock.send(bucket.payload())

    buckets = []
    peers = []

    while 1:
        buffer = sock.recv(8)
        if not buffer:
            sys.stderr.write("Invalid response; exiting\n")
            break

        if not buffer.startswith(bytes(LEVIN_SIGNATURE)):
            sys.stderr.write("Invalid response; exiting\n")
            break

        bucket = Bucket.from_buffer(signature=buffer, sock=sock)
        buckets.append(bucket)

        if bucket.command == 1001:
            peers = bucket.get_peers() or []

            for peer in peers:
                try:
                    peers.append('http://%s:%d' % (peer['ip'].ip, peer['port'].value))
                except:
                    pass

            sock.close()
            break

    if peers:
        return peers
    else:
        return None
