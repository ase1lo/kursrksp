# CorpLink Messenger

Корпоративный мессенджер с каналами, сообщениями, интеграциями, RBAC, аудитом, Docker, CI, fuzzing-тестированием и 100% coverage gate для backend-ядра.

## Стек

- Backend: Python 3.11+, standard library HTTP/API layer.
- Frontend: Vanilla HTML/CSS/JS SPA.
- Database: PostgreSQL как production-БД через `DATABASE_URL`.
- Auth: PBKDF2-HMAC-SHA256 password hashing + HMAC bearer tokens.
- Tests: `unittest`, integration tests, deterministic fuzzing.
- Coverage: собственный `scripts/coverage_gate.py`, 100% line coverage по `server/`.
- DevOps: Docker, Docker Compose, GitHub Actions CI.

## Быстрый старт

```bash
docker compose up --build
```

Открыть `http://localhost:8080`.

Демо-аккаунт:

- email: `admin@corp.test`
- password: `AdminPass123`

## Запуск проверок

```bash
pip install -r requirements.txt
python3 -m unittest discover -v
python3 scripts/coverage_gate.py
docker build -t corplink-messenger .
```

## Docker

```bash
docker compose up --build
```

Smoke-проверка после старта:

```bash
curl -i http://127.0.0.1:8080/
curl -i http://127.0.0.1:8080/api/health
```

Если браузер показывает пустой экран после перехода с SQLite на PostgreSQL, очистите старый `localStorage` для `localhost:8080` или откройте DevTools Console и выполните:

```js
localStorage.clear()
```

## Структура проекта

```text
server/                 Backend API, auth, RBAC, DB schema
client/                 Browser SPA
tests/                  Unit, integration, fuzzing tests
scripts/coverage_gate.py 100% coverage gate
docs/                   Domain analysis, UML, 12-factor, deployment
.github/workflows/ci.yml GitHub Actions CI
Dockerfile              Production container
docker-compose.yml      Local app + PostgreSQL runtime
render.yaml             Cloud deployment blueprint
```

## Реализованные возможности

- Авторизация и аутентификация пользователя.
- Роли `admin`, `moderator`, `member`, `bot`.
- Валидация некорректных ролей и прав доступа.
- CRUD для пользователей, каналов, сообщений и интеграций.
- Приватные каналы и membership-доступ.
- Реляционная схема с внешними ключами.
- Seed-данные для демонстрации.
- Аудит действий.
- Фаззинг-тестирование входных данных.
- CI на GitHub с тестами, 100% coverage и Docker build.

## Документы

- [Анализ предметной области](docs/domain-analysis.md)
- [UML и архитектура](docs/uml.md)
- [12 факторов](docs/12-factor.md)
- [Развертывание](docs/deployment.md)
