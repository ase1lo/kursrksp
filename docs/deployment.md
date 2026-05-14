# Развертывание

## Локально без Docker

```bash
python3 -m server.httpd
```

После запуска приложение доступно на `http://localhost:8080`.

## Локально через Docker Compose

```bash
docker compose up --build
```

Данные сохраняются в volume `messenger-data`.

## Облако

Проект подготовлен как Docker web service:

- `Dockerfile` содержит production-запуск.
- `render.yaml` описывает Docker-сервис с persistent disk.
- Все секреты передаются через env, а не хранятся в коде.
- CI проверяет тесты, 100% coverage gate и сборку Docker-образа.

Общий порядок деплоя:

1. Загрузить репозиторий на GitHub.
2. Создать web service на Docker-хостинге.
3. Подключить репозиторий.
4. Добавить env-переменные из `.env.example`.
5. Подключить persistent volume для `/app/data`.
6. Дождаться успешной сборки и открыть публичный URL.

Перед финальной сдачей стоит заменить `SECRET_KEY`, проверить публичный URL и сделать скриншоты интерфейса для презентации.
