FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PORT=8080 \
    DATABASE_URL=postgresql://messenger:messenger@db:5432/corplink

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY server ./server
COPY client ./client
COPY .env.example ./env.example

EXPOSE 8080

CMD ["python", "-m", "server.httpd"]
