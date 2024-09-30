import asyncio
import logging
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)


async def run_async(
    process: Callable[[Any], Coroutine[Any, Any, None]],
    on_exit: Optional[Callable[[Optional[str]], Any]] = None,
    *args,
    **kwargs,
) -> None:
    """
    Run an async process and handle the exit
    """
    logger.info(f"Workflow started :: {process.__name__}")
    try:
        await process(*args, **kwargs)
        logger.info(f"Workflow completed :: {process.__name__}")
        return on_exit and on_exit(None)
    except Exception as e:
        logger.error(f"Workflow errored :: {process.__name__}")
        logger.exception(e)
        return on_exit and on_exit(str(e))


def run_async_in_loop(
    process: Callable[[Any], Coroutine[Any, Any, None]],
    on_exit: Optional[Callable[[Optional[str]], Any]] = None,
    *args,
    **kwargs,
) -> None:
    """
    Run an async process in a new event loop and handle the exit.
    Useful when called from a non-async context.
    """
    logger.info(f"Workflow started :: {process.__name__}")
    try:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(process(*args, **kwargs))
            logger.info(f"Workflow completed :: {process.__name__}")
            return on_exit and on_exit(None)
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Workflow errored :: {process.__name__}")
        logger.exception(e)
        return on_exit and on_exit(str(e))
