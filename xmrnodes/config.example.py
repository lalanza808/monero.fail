import os

SECRET_KEY = os.environ.get('SECRET_KEY', 'xxxx')
DATA_DIR = os.environ.get('DATA_DIR', './data')
