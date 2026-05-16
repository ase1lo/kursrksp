# UML и архитектура

## Клиент-серверная архитектура

Приложение построено как классическая трехзвенная клиент-серверная система:

- Presentation layer: SPA в `client/`, работает в браузере и обращается к `/api`.
- Application layer: Python backend в `server/`, маршрутизация, auth, RBAC, валидация и бизнес-правила.
- Data layer: реляционная PostgreSQL БД, подключаемая через `DATABASE_URL`.

## Component Diagram

```mermaid
flowchart LR
    Browser[Browser SPA] -->|HTTP JSON| API[MessengerApp API]
    API --> Auth[Auth and Token Service]
    API --> RBAC[RBAC Policy]
    API --> Validators[Input Validators]
    API --> DB[(Relational DB)]
    API --> Audit[Audit Log]
    Integrations[Git / CI / Webhook / Calendar] -->|bot messages| API
    CI[GitHub Actions] --> Tests[Unit + Integration + Fuzz Tests]
    CI --> Docker[Docker Build]
```

## Class Diagram

```mermaid
classDiagram
    class MessengerApp {
      +handle(method, path, headers, body) ApiResponse
      +seed_demo() dict
      -_login(payload) dict
      -_users_route(method, tail, payload, user) ApiResponse
      -_channels_route(method, tail, payload, user, query) ApiResponse
      -_messages_route(method, tail, payload, user) ApiResponse
      -_integrations_route(method, tail, payload, user) ApiResponse
    }

    class ApiResponse {
      +int status
      +dict payload
      +dict headers
      +body() bytes
    }

    class Database {
      +migrate()
      +execute(sql, parameters)
      +one(sql, parameters)
      +all(sql, parameters)
      +insert(sql, parameters)
      +require_one(sql, parameters, label)
      +close()
    }

    class Settings {
      +str app_env
      +str database_url
      +str secret_key
      +int port
      +int token_ttl_seconds
      +factor_report() dict
    }

    class User {
      +id
      +email
      +name
      +role
      +active
    }

    class Channel {
      +id
      +slug
      +name
      +description
      +is_private
    }

    class Message {
      +id
      +channel_id
      +author_id
      +body
      +edited
    }

    class Integration {
      +id
      +channel_id
      +name
      +type
      +config
      +enabled
    }

    MessengerApp --> Database
    MessengerApp --> Settings
    MessengerApp --> ApiResponse
    User "1" --> "*" Message
    Channel "1" --> "*" Message
    Channel "1" --> "*" Integration
```

## ER Diagram

```mermaid
erDiagram
    USERS ||--o{ CHANNELS : creates
    USERS ||--o{ MESSAGES : writes
    USERS ||--o{ INTEGRATIONS : creates
    USERS ||--o{ AUDIT_EVENTS : acts
    CHANNELS ||--o{ MESSAGES : contains
    CHANNELS ||--o{ INTEGRATIONS : connects
    CHANNELS ||--o{ CHANNEL_MEMBERS : has
    USERS ||--o{ CHANNEL_MEMBERS : joins

    USERS {
      integer id PK
      text email UK
      text name
      text password_hash
      text role
      integer active
      text created_at
    }

    CHANNELS {
      integer id PK
      text slug UK
      text name
      text description
      integer is_private
      integer created_by FK
      text created_at
    }

    MESSAGES {
      integer id PK
      integer channel_id FK
      integer author_id FK
      text body
      integer edited
      text created_at
    }

    INTEGRATIONS {
      integer id PK
      integer channel_id FK
      text name
      text type
      text config_json
      integer enabled
      integer created_by FK
      text created_at
    }
```

## Sequence Diagram: вход и отправка сообщения

```mermaid
sequenceDiagram
    actor User
    participant SPA as Browser SPA
    participant API as MessengerApp
    participant Auth as Security
    participant DB as PostgreSQL

    User->>SPA: email + password
    SPA->>API: POST /api/auth/login
    API->>DB: SELECT user by email
    API->>Auth: verify_password + issue_token
    API-->>SPA: bearer token
    User->>SPA: отправляет сообщение
    SPA->>API: POST /api/channels/{id}/messages
    API->>Auth: verify_token
    API->>API: RBAC + channel access
    API->>DB: INSERT message
    API->>DB: INSERT audit_event
    API-->>SPA: created message
```

## Deployment Diagram

```mermaid
flowchart TB
    Dev[Developer Workstation] --> Git[Git Repository]
    Git --> Actions[GitHub Actions CI]
    Actions --> Test[100% tests + fuzzing]
    Actions --> Image[Docker image build]
    Image --> Cloud[Cloud Docker Web Service]
    Cloud --> Volume[(Persistent DB volume)]
    User[Employee Browser] --> Cloud
```
