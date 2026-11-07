FROM python:3.12-slim

WORKDIR /app

# yt-dlp requires a JS runtime (Deno) for YouTube's EJS challenge solver.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl unzip && \
    curl -fsSL https://deno.land/install.sh | sh && \
    apt-get purge -y curl unzip && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

ENV DENO_INSTALL=/root/.deno
ENV PATH="/root/.deno/bin:${PATH}"
ENV YTDLP_DENO_PATH=/root/.deno/bin/deno

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY nim.txt .

ENV PYTHONPATH=/app

CMD ["python", "-m", "src.main"]
