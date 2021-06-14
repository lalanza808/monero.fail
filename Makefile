setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

up:
	docker-compose up -d

dev:
	./bin/dev

prod:
	./bin/prod

logs:
	docker-compose logs -f
