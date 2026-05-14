FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PORT=8080 \
    DATABASE_URL=sqlite:////app/data/messenger.db

WORKDIR /app

COPY server ./server
COPY client ./client
COPY .env.example ./env.example

RUN mkdir -p /app/data

EXPOSE 8080

CMD ["python", "-m", "server.httpd"]
