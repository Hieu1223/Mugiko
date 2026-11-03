# LLM Server

Worker process that consumes messages from Redis streams (via Sequin CDC), processes them through NVIDIA NIM LLM, and publishes responses back to Redis streams.

## Architecture

```
# Conversation flow
Sequin CDC → Redis Stream (conversation_messages) → LLM Server → Redis Stream (llm_responses) → Main Server

# Job flow  
API → llm_jobs table → Sequin CDC → Redis Stream (llm_jobs) → LLM Server → llm_jobs table (update) → Redis Stream (llm_responses) → Main Server
```

## Streams

| Stream | Direction | Description |
|--------|-----------|-------------|
| `conversation_messages` | Input | New user messages in conversations |
| `llm_jobs` | Input | LLM job creation events |
| `llm_responses` | Output | Completed responses (both conversation and job) |

## Configuration

Copy `.env.example` to `.env` and fill in required values:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `NVIDIA_API_KEYS_FILE` - Path to file with NIM API keys (one per line)
- `LLM_INPUT_STREAM` - Input stream for conversation messages (default: conversation_messages)
- `LLM_JOBS_STREAM` - Input stream for LLM jobs (default: llm_jobs)
- `LLM_OUTPUT_STREAM` - Output stream for responses (default: llm_responses)

## Run

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values
python -m src.main
```

## Docker

```bash
docker build -t llm_server .
docker run --env-file .env -v $(pwd)/nim.txt:/app/nim.txt:ro llm_server
```