setup:
	uv sync
	mkdir -p data
	wget https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-City.mmdb -P data --no-clobber

up:
	docker compose up -d

dev:
	FLASK_DEBUG=1 uv run flask run

build:
	docker compose -f docker-compose.prod.yaml build

prod:
	docker compose -f docker-compose.prod.yaml up -d

logs:
	docker compose -f docker-compose.prod.yaml logs -f

down:
	docker compose -f docker-compose.prod.yaml down

validate:
	docker compose -f docker-compose.prod.yaml exec web uv run flask validate

check:
	docker compose -f docker-compose.prod.yaml exec web uv run flask check

export:
	docker compose -f docker-compose.prod.yaml exec web uv run flask export

peers:
	docker compose -f docker-compose.prod.yaml exec web uv run flask get_peers

html:
	docker compose -f docker-compose.prod.yaml exec web uv run flask html

vacuum:
	sqlite3 data/sqlite.db 'VACUUM;'
	sqlite3 data/sqlite.db 'PRAGMA wal_checkpoint(truncate);'