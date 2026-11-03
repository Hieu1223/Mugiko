"""Entry point for LLM Server."""
import logging
import signal
import sys
import threading
import time

from dotenv import load_dotenv

from src.config import LLMServerConfig
from src.listener import StreamListener
from src.models import ConversationMessage, LLMJobMessage
from src.processor import LLMProcessor
from src.nim_client import NIMClient
from src.repository import ConversationRepository
from src.common.db import Database
from src.common.redis import create_redis_client

load_dotenv()
load_dotenv(".env.local", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("llm_server")


class LLMServer:
    def __init__(self):
        self.config = LLMServerConfig.from_env()
        self._running = False
        self._threads = []

    def start(self):
        logger.info("Starting LLM Server...")

        # Initialize connections
        db = Database(self.config.database_url)
        redis_client = create_redis_client(self.config.redis_url)

        # Initialize components
        api_keys = self.config.load_api_keys()
        nim_client = NIMClient(
            api_keys=api_keys,
            base_url=self.config.base_url,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout_seconds=self.config.timeout_seconds,
        )

        repo = ConversationRepository(db)
        listener = StreamListener(self.config, redis_client)
        processor = LLMProcessor(self.config, nim_client, repo, redis_client)

        # Ensure consumer group exists
        listener.ensure_group()

        self._running = True

        # Start worker threads
        for i in range(self.config.max_concurrent_jobs):
            thread = threading.Thread(
                target=self._worker_loop,
                args=(listener, processor),
                name=f"llm-worker-{i}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

        logger.info("Started %d worker threads", self.config.max_concurrent_jobs)

        # Main loop - just keep alive and handle stale claim
        try:
            while self._running:
                time.sleep(30)
                # Periodic stale claim
                claimed = listener.claim_stale()
                for msg in claimed:
                    logger.info("Reclaimed stale message %s", getattr(msg, "message_id", getattr(msg, "id", "unknown")))
                    # Process in background (could use a queue)
                    threading.Thread(
                        target=self._process_and_ack,
                        args=(listener, processor, msg),
                        daemon=True
                    ).start()
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            self.stop()
            nim_client.close()
            redis_client.close()
            db.close()
            logger.info("LLM Server stopped")

    def _worker_loop(self, listener: StreamListener, processor: LLMProcessor):
        while self._running:
            try:
                messages = listener.read_messages(count=1)
                for msg in messages:
                    self._process_and_ack(listener, processor, msg)
            except Exception as e:
                logger.exception("Worker error: %s", e)
                time.sleep(5)  # Back off on error

    def _process_and_ack(self, listener: StreamListener, processor: LLMProcessor, msg):
        entry_id = getattr(msg, "_stream_entry_id", None)
        stream_name = getattr(msg, "_stream_name", None)
        try:
            response = processor.process(msg)
            processor.publish_response(response)
        finally:
            if entry_id:
                listener.ack(entry_id, stream_name)

    def stop(self):
        self._running = False
        for thread in self._threads:
            if thread.is_alive():
                thread.join(timeout=10)


def main():
    server = LLMServer()

    def signal_handler(signum, frame):
        logger.info("Received signal %s", signum)
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    server.start()


if __name__ == "__main__":
    main()