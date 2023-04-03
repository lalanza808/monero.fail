setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
	mkdir -p data
	wget https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-City.mmdb -P data --no-clobber

up:
	docker-compose up -d

dev:
	./manage.sh run

prod:
	./manage.sh prod

logs:
	docker-compose logs -f

kill:
	pkill -ef xmrnodes