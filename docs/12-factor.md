# Соответствие методологии 12 факторов

| Фактор | Реализация в проекте |
| --- | --- |
| Codebase | Один Git-репозиторий для backend, frontend, tests, docs, Docker и CI. |
| Dependencies | Нулевые внешние runtime-зависимости; Python standard library. |
| Config | `APP_ENV`, `DATABASE_URL`, `SECRET_KEY`, `PORT`, `TOKEN_TTL_SECONDS`, `CORS_ORIGIN`. |
| Backing services | БД подключается как ресурс через `DATABASE_URL`. |
| Build, release, run | Dockerfile разделяет образ и запуск; release меняется через env. |
| Processes | Stateless HTTP-процесс; состояние хранится в реляционной БД. |
| Port binding | Сервер слушает порт из `PORT`. |
| Concurrency | `ThreadingHTTPServer` допускает параллельные HTTP-запросы. |
| Disposability | Быстрый старт, stdout-логи, корректная работа с volume. |
| Dev/prod parity | Один и тот же Dockerfile для локального и облачного запуска. |
| Logs | Процесс пишет служебные события в stdout, аудит хранится в БД. |
| Admin processes | Seed-данные создаются через `/api/seed` и при старте production-контейнера. |

## Переменные окружения

```bash
APP_ENV=production
PORT=8080
DATABASE_URL=sqlite:////app/data/messenger.db
SECRET_KEY=<strong-random-secret>
TOKEN_TTL_SECONDS=86400
CORS_ORIGIN=*
```
