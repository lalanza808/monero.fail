import os
from secrets import token_urlsafe

from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.environ.get('SECRET_KEY', token_urlsafe(14))
SERVER_NAME = os.environ.get('SERVER_NAME', '127.0.0.1:5000')
DATA_DIR = os.environ.get('DATA_DIR', './data')
TOR_HOST = os.environ.get('TOR_HOST', '127.0.0.1')
TOR_PORT = os.environ.get('TOR_PORT', 9050)
NODE_HOST = os.environ.get('NODE_HOST', 'singapore.node.xmr.pm')
NODE_PORT = os.environ.get('NODE_PORT', 18080)