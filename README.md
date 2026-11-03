# Mugiko

Unified repository for Mugiko projects.

## Structure

```
Mugiko/
├── doc/                 # Documentation
├── src/                 # All source code
│   ├── backend/         # MugikoGO (Go API server)
│   ├── frontend/        # MugikoFrontend (React/Vite)
│   ├── llm/             # llm_server (Python LLM service)
│   ├── workers/         # MugikoWorkServer (Python workers)
│   ├── data/            # MugikoDictionary (dictionary binaries + build scripts)
│   └── web/             # Web subprojects
│       └── anki-decks/  # AnkiDecks (deck generation)
├── scripts/             # Build/deploy scripts
│   ├── backend/
│   ├── frontend/
│   ├── llm/
│   ├── deploy/          # MugikoDeploy (Docker Compose, envs, SQL)
│   ├── workers/
│   ├── data/
│   └── web/
├── docker-compose.yml   # Root compose file
└── .gitignore
```
