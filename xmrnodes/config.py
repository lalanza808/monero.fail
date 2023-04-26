from os import environ
from secrets import token_urlsafe

from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = environ.get("SECRET_KEY", token_urlsafe(14))
SERVER_NAME = environ.get("SERVER_NAME", "127.0.0.1:5000")
DATA_DIR = environ.get("DATA_DIR", "./data")
TOR_HOST = environ.get("TOR_HOST", "127.0.0.1")
TOR_PORT = environ.get("TOR_PORT", 9050)
NODE_HOST = environ.get("NODE_HOST", "singapore.node.xmr.pm")
NODE_PORT = environ.get("NODE_PORT", 18080)
HEALTHY_BLOCK_DIFF = int(environ.get("HEALTHY_BLOCK_DIFF", 500))
PEER_LIFETIME = int(environ.get("PEER_LIFETIME", 96))
I2P_HOST = environ.get("I2P_HOST", "127.0.0.1")
I2P_PORT = environ.get("I2P_PORT", 4444)