#!/bin/bash

source .venv/bin/activate
export FLASK_APP=xmrnodes/app.py
export FLASK_SECRETS=config.py
export FLASK_DEBUG=0
export FLASK_ENV=production

# override
source .env
export SERVER_NAME=livk2fpdv4xjnjrbxfz2tw3ptogqacn2dwfzxbxr3srinryxrcewemid.onion
export BASE=./data/gunicorn
mkdir -p $BASE
gunicorn \
  --bind 127.0.0.1:4001 "xmrnodes.app:app" \
  --daemon \
  --log-file $BASE/onion-gunicorn.log \
  --pid $BASE/onion-gunicorn.pid \
  --reload