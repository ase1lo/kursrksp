# Развертывание

## Локально без Docker

```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql://messenger:messenger@localhost:5432/corplink
python3 -m server.httpd
```

Перед запуском должен быть доступен PostgreSQL. После запуска приложение доступно на `http://localhost:8080`.

## Локально через Docker Compose

```bash
docker compose up --build
```

Docker Compose поднимает приложение и PostgreSQL. Данные сохраняются в volume `postgres-data`.

## Облако

Проект подготовлен как Docker web service:

- `Dockerfile` содержит production-запуск.
- `render.yaml` описывает Docker-сервис и managed PostgreSQL.
- Все секреты передаются через env, а не хранятся в коде.
- CI проверяет тесты, 100% coverage gate и сборку Docker-образа.

Общий порядок деплоя:

1. Загрузить репозиторий на GitHub.
2. Создать web service на Docker-хостинге.
3. Подключить репозиторий.
4. Добавить env-переменные из `.env.example`.
5. Подключить managed PostgreSQL и передать `DATABASE_URL`.
6. Дождаться успешной сборки и открыть публичный URL.

Перед финальной сдачей стоит заменить `SECRET_KEY`, проверить публичный URL и сделать скриншоты интерфейса для презентации.
