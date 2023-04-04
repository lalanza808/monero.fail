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

# default configs work out of the box, modify .env if needed
# setup .env
cp env-example .env
vim .env

# run services (tor, i2p, etc)
make up

# run development server
make dev

# access at http://127.0.0.1:5000
```

### Background Tasks

There are 3 things that need to run in the background:
* validating nodes that have been added
* checking existing node health
* scraping peer lists

I accomplish this via `crontab` and some management scripts.

```
./manage.sh validate
./manage.sh check
./manace.sh get_peers
```

### Production

For production, update `SERVER_NAME` in `.env` to your production URL/domain. Use `manage.sh` (or provided `Makefile`) to serve the Flask process using Gunicorn. 

```
./manage.sh prod
```

Runs the Gunicorn process on port 4000. Setup a web server to proxy requests to that port.

Kill production Gunicorn with `make kill`.


