"""Entrypoint: runs the subtitle and LLM workers in background threads."""

import logging
import os
import threading

from dotenv import load_dotenv

from src.llm import run as run_llm
from src.llm.config import LLMConfig
from src.subtitle import run as run_subtitle

logger = logging.getLogger("main")


def main() -> None:
    load_dotenv()
    load_dotenv(".env.local", override=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    queue = os.getenv("SUBTITLE_STREAM", "subtitle_queue")
    threads = [
        threading.Thread(
            target=run_subtitle,
            args=(queue,),
            name=f"subtitle[{queue}]",
            daemon=True,
        )
    ]
    logger.info("Starting subtitle worker on stream %r", queue)

    if LLMConfig.is_configured():
        threads.append(
            threading.Thread(
                target=run_llm,
                name="llm",
                daemon=True,
            )
        )
        logger.info("Starting LLM worker")
    else:
        logger.warning(
            "NVIDIA key file is missing or empty; LLM worker disabled"
        )

    for thread in threads:
        thread.start()

    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        for thread in threads:
            if thread.is_alive():
                logger.info(
                    "%s thread is a daemon; in-flight work may be redelivered",
                    thread.name,
                )
    logger.info("Worker stopped.")


if __name__ == "__main__":
    main()
