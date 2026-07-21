# 🔒 Telegram Fsub Bot

A production-grade **Forced Subscription (Fsub) Bot** for Telegram — acts as a content gate that requires users to join specified channels before accessing protected media.

Built with **Python 3.11+**, **Hydrogram** (MTProto), **PostgreSQL**, and **Redis**.

---

## ✨ Features

- **Permanent Deep Links** — Base64-encoded content links (no expiry, always accessible)
- **Forced Subscription** — Users must join all required channels to access content
- **Telegram-as-Storage** — No file hosting needed; stores only `file_id` metadata
- **Album/Multi-file Support** — One content ID can contain multiple files
- **Role-Based Access Control** — Owner → Admin → Staff → User hierarchy
- **Redis-Cached Membership** — 60s TTL cache to minimize Telegram API calls
- **Background Workers** — Redis-backed queue with exponential backoff & DLQ
- **Rate Limiting** — Per-user token-bucket via Redis
- **Audit Logging** — Immutable, append-only log of all admin actions
- **Dockerized** — Multi-stage build with separate bot & worker containers

---

## 🏗️ Architecture

```
┌──────────────┐     ┌──────────────┐
│   Telegram   │◄────│  Hydrogram   │
│   MTProto    │────►│  Bot Client  │
└──────────────┘     └──────┬───────┘
                            │
                  ┌─────────┴─────────┐
                  │   Services Layer   │
                  │  (Pure Logic, No   │
                  │   Framework Code)  │
                  └─────────┬─────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Postgres │  │  Redis   │  │  Worker   │
        │  (Data)  │  │ (Cache/  │  │ (Queue    │
        │          │  │  Queue)  │  │  Consumer)│
        └──────────┘  └──────────┘  └──────────┘
```

---

## 📁 Project Structure

```
fsub-bot/
├── alembic/                 # Database migrations
│   ├── env.py               # Async migration runner
│   ├── script.py.mako       # Migration template
│   └── versions/            # Generated migrations
├── app/
│   ├── bot/                 # Hydrogram interface
│   │   ├── filters/         # Custom filters (IsAdmin, IsStaff, IsOwner)
│   │   ├── handlers/        # Command handlers
│   │   │   ├── start.py     # /start + deep link flow
│   │   │   ├── admin.py     # /stats, /health, /queue, /logs, /setrole
│   │   │   ├── content.py   # /add_content (upload FSM)
│   │   │   └── fsub.py      # /add_channel, /remove_channel, /channels
│   │   ├── middlewares/     # Rate limiting
│   │   └── main.py          # Bot client factory
│   ├── core/                # Infrastructure
│   │   ├── config.py        # Pydantic Settings
│   │   ├── database.py      # SQLAlchemy async engine
│   │   ├── redis.py         # Redis client wrapper
│   │   └── security.py      # Base64 deep links (permanent)
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── user.py          # User + Role enum
│   │   ├── content.py       # Content + ContentFile (1:N)
│   │   ├── channel.py       # Fsub channel list
│   │   ├── logs.py          # AccessLog + AuditLog
│   │   └── job.py           # Background job tracking
│   ├── services/            # Business logic (no framework imports)
│   │   ├── auth_service.py  # Roles, permissions, ban/unban
│   │   ├── fsub_service.py  # Membership check + Redis cache
│   │   └── content_service.py # CRUD, deep links, stats
│   └── workers/             # Background task processing
│       ├── consumer.py      # Redis BRPOP loop + retry + DLQ
│       └── tasks.py         # Task dispatcher + handlers
├── assets/covers/           # Cover images for channel posts
├── .env.example             # Environment variable template
├── alembic.ini              # Alembic configuration
├── docker-compose.yml       # Bot + Worker + Postgres + Redis
├── Dockerfile               # Multi-stage Python 3.11 build
├── main.py                  # Application entry point
└── requirements.txt         # Pinned dependencies
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose** (recommended)
- Telegram **API_ID** & **API_HASH** from [my.telegram.org](https://my.telegram.org)
- A **Bot Token** from [@BotFather](https://t.me/BotFather)

### 1. Clone & Configure

```bash
cd fsub-bot
cp .env.example .env
```

Edit `.env` with your credentials:

```env
API_ID=12345
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
BOT_USERNAME=YourBotUsername
OWNER_ID=your_telegram_user_id
DB_CHANNEL_ID=-100xxxxxxxxxx
```

### 2. Start with Docker (Recommended)

```bash
# Start all services
docker compose up -d

# Check logs
docker compose logs -f bot

# Run database migrations
docker compose exec bot alembic revision --autogenerate -m "initial"
docker compose exec bot alembic upgrade head
```

### 3. Start without Docker (Development)

```bash
# Install dependencies
pip install -r requirements.txt

# Start Postgres & Redis manually (or use Docker for infra only)
docker compose up -d postgres redis

# Run migrations
alembic revision --autogenerate -m "initial"
alembic upgrade head

# Start the bot
python main.py

# Or start bot + worker together
python main.py both
```

---

## 📋 Bot Commands

### General
| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/start <payload>` | Access content via deep link |
| `/help` | Show available commands (role-aware) |

### Staff+
| Command | Description |
|---------|-------------|
| `/stats` | View bot statistics |
| `/add_content` | Upload new content (multi-step) |

### Admin+
| Command | Description |
|---------|-------------|
| `/health` | Check DB & Redis health |
| `/queue` | View job queue status |
| `/logs` | Recent audit log entries |
| `/setrole <user_id> <ROLE>` | Change user role |
| `/ban <user_id>` | Ban a user |
| `/unban <user_id>` | Unban a user |
| `/add_channel <id/@username>` | Add fsub channel |
| `/remove_channel <id>` | Remove fsub channel |
| `/channels` | List active fsub channels |

---

## 🔐 Security

- **Permanent deep links** — Base64-encoded content IDs (no expiry, always accessible)
- **Role hierarchy** enforced at service layer (Owner > Admin > Staff > User)
- **Immutable audit log** — all admin actions recorded with JSONB payload
- **Rate limiting** — per-user token-bucket backed by Redis
- Non-root Docker container user

---

## ⚙️ Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `API_ID` | — | Telegram API ID |
| `API_HASH` | — | Telegram API Hash |
| `BOT_TOKEN` | — | Bot token from BotFather |
| `OWNER_ID` | — | Your Telegram user ID |
| `DB_CHANNEL_ID` | — | Channel ID for content catalogue posts |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `RATE_LIMIT_REQUESTS` | `30` | Max requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window (seconds) |

---

## 🐳 Docker Services

| Service | Image | Purpose |
|---------|-------|---------|
| `bot` | Custom (Python 3.11) | Telegram bot process |
| `worker` | Custom (Python 3.11) | Background job consumer |
| `postgres` | postgres:16-alpine | Primary database |
| `redis` | redis:7-alpine | Cache & job queue |

---

## 👤 Owner & Creator

- **Owner & Creator**: [@hexymm](https://t.me/hexymm)

---

## 📄 License

This project is for educational and personal use.
