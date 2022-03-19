# monero.fail

Monero node tracker

## Setup

Tools you will need:
* Docker  # apt-get install docker.io
* docker-compose  # apt-get install docker-compose
* python3 (linux os will have this)
* python3-venv  # apt-get install python3-venv

### Development

I have provided a `Makefile` with some helpful stuff...make sure to install `make` to use it.

The map portion of the service requires the GeoLite2 db...the `make setup` command fetches a copy via `wget`.

```
# install python virtual environment and install application dependencies
make setup

# setup config
cp xmrnodes/config.example.py xmrnodes/config.py
vim xmrnodes/config.py

# run services (tor, i2p, etc)
make up

# run development server
make dev

# access at http://127.0.0.1:5000
```
