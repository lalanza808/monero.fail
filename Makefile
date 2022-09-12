setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
	mkdir -p data
	wget https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-City.mmdb -P data

up:
	docker-compose up -d

dev:
	./bin/dev

prod:
	./bin/prod

logs:
	docker-compose logs -f
