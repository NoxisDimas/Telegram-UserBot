# Telegram Userbot Worker v3.0

Production-ready Telegram userbot dengan 12 fitur AI-powered menggunakan Groq + LangChain.

> **Owner & Creator:** [@hexymm](https://t.me/hexymm) on Telegram


## 🚀 Quick Start

```bash
# 1. Setup .env
cp .env.example .env
# Edit dengan API credentials

# 2. Build & Run
docker-compose up --build
```

## 📱 Commands

| Command | Description |
|---------|-------------|
| `.help` | Show all commands |
| `.info [task]` | Bot & Task status |
| `.status` | System status |

### 🤖 AI Features (Groq)
| Command | Description |
|---------|-------------|
| `.summarize [N]` | Summarize last N messages |
| `.suggest` | AI reply suggestions |
| `.mood` | Chat sentiment analysis |

### 📊 Analytics
| Command | Description |
|---------|-------------|
| `.stats` | Chat statistics |
| `.health` | Account health & risk score |

### ⏰ Utility
| Command | Description |
|---------|-------------|
| `.getid [target]` | Get Chat/User ID |
| `.schedule 10m <msg>` | Schedule message |
| `.download` | Download media (reply) |
| `.scrapemedia <id> <limit> [date]` | Scrape media to Saved Messages |
| `.backup` | Backup session |
| `.afk [reason]` | Enable AFK mode |
| `.back` | Disable AFK |

### 📡 Broadcasting
| Command | Description |
|---------|-------------|
| `.gcast <msg>` | Broadcast to groups |
| `.kill` | Toggle kill switch |
| `.autoreply ai` | Enable AI auto-reply |

## ⚙️ Configuration

```env
# Required
TG_API_ID=123456
TG_API_HASH=abcdef...
REDIS_URL=redis://redis:6379/0

# AI Features (Phase 3)
GROQ_API_KEY=gsk_xxx...
AI_MODEL=llama-3.3-70b-versatile

# Safety (Phase 2)
WARMUP_ENABLED=true
ACTIVE_HOURS_START=9
ACTIVE_HOURS_END=21
```

## 🔐 Safety Features

- **Warm-Up Engine**: Staged limits (5→15→50→500/day)
- **Risk Control**: Auto-escalate on flood errors
- **Kill Switch**: Emergency stop via `.kill`
- **Time Window**: Active hours only

## 📁 Project Structure

```
app/
├── services/
│   ├── ai/
│   │   ├── groq_client.py    # LangChain + Groq
│   │   ├── summarizer.py     # Chat summaries
│   │   ├── smart_reply.py    # AI suggestions
│   │   └── sentiment.py      # Mood analysis
│   ├── auto_reply.py         # Auto-reply bot
│   ├── scheduler.py          # Scheduled messages
│   ├── forwarder.py          # Auto-forward
│   ├── analytics.py          # Chat stats
│   ├── health_monitor.py     # Ban risk
│   ├── afk.py                # AFK mode
│   ├── downloader.py         # Media download
│   ├── session_backup.py     # Session backup
│   └── proxy_manager.py      # Proxy rotation
├── handlers/
│   ├── monitor.py            # Commands
│   ├── scraper.py            # Scrape media command
│   └── executor.py           # Task execution
└── guards/
    ├── rate_limit.py
    └── anti_spam.py
```

## ⚠️ Disclaimer

Educational purposes only. Use responsibly.

---

## 👤 Author & Owner
**Creator:** [@hexymm](https://t.me/hexymm) di Telegram.
