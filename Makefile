compose_file=infra/docker/docker-compose.yml

up:
	docker compose -f $(compose_file) up --build

down:
	docker compose -f $(compose_file) down

logs:
	docker compose -f $(compose_file) logs -f

