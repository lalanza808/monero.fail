#!/bin/bash

source .venv/bin/activate
export FLASK_APP=xmrnodes/app.py
export FLASK_SECRETS=config.py
export FLASK_DEBUG=1
export FLASK_ENV=development

# override
source .env

if [[ ${1} == "prod" ]];
then
  export FLASK_DEBUG=0
  export FLASK_ENV=production
  export BASE=./data/gunicorn
  mkdir -p $BASE
  pgrep -F $BASE/gunicorn.pid
  if [[ $? != 0 ]]; then
    gunicorn \
      --bind 127.0.0.1:4000 "xmrnodes.app:app" \
      --daemon \
      --log-file $BASE/gunicorn.log \
      --pid $BASE/gunicorn.pid \
      --reload
    sleep 2
    echo "Started gunicorn on 127.0.0.1:4000 with pid $(cat $BASE/gunicorn.pid)"
  fi
else
  flask $@
fi
