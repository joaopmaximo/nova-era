# Client Registration System

Simple client registration system built with Python, FastAPI, and PostgreSQL.

## Stack

- **Backend**: FastAPI + SQLAlchemy
- **Database**: PostgreSQL (via Docker)
- **Frontend**: HTML + CSS (responsive, modern design)

## Project Structure

```
├── app/
│   ├── database.py    # DB connection
│   ├── models.py      # SQLAlchemy models
│   └── main.py        # API routes
├── static/css/
│   └── style.css      # Styles
├── templates/
│   ├── base.html      # Layout
│   ├── register.html  # Registration page
│   └── clients.html   # Client list page
├── docker-compose.yml
├── requirements.txt
└── .env
```

## Setup

```bash
# Start database
docker compose up -d

# Install dependencies
pip install -r requirements.txt

# Run server
py -m uvicorn app.main:app --reload
```

## Routes

- `/register` - New client registration
- `/clients` - List all clients (with search)