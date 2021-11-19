import os

SECRET_KEY = os.environ.get('SECRET_KEY', 'xxxx')
DATA_DIR = os.environ.get('DATA_DIR', './data')
TOR_HOST = os.environ.get('TOR_HOST', '127.0.0.1')
TOR_PORT = os.environ.get('TOR_PORT', 9050)
NODE_HOST = os.environ.get('NODE_HOST', '127.0.0.1')
NODE_PORT = os.environ.get('NODE_PORT', 18080)
I2P_HOST = os.environ.get('I2P_HOST', '127.0.0.1')
I2P_PORT = os.environ.get('I2P_PORT', 4447)
