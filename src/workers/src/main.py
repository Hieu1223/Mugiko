"""Entrypoint: runs the subtitle worker."""

import logging
import os
import threading

from dotenv import load_dotenv

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
    thread = threading.Thread(
        target=run_subtitle,
        args=(queue,),
        name=f"subtitle[{queue}]",
        daemon=True,
    )
    logger.info("Starting subtitle worker on stream %r", queue)
    thread.start()
    try:
        thread.join()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    logger.info("Worker stopped.")


if __name__ == "__main__":
    main()