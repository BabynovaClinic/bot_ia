import time
from typing import Any, Callable

from src.log.system_logger import Logger, get_system_logger

LOG: Logger = get_system_logger(__name__)

def retry_on_exception(max_retries: int = 3, delay: int = 5, exceptions=(Exception,)) -> Callable:
    """
    A decorator to retry a function call if specific exceptions occur.

    Args:
        max_retries (int): Maximum number of retries.
        delay (int): Delay in seconds between retries.
        exceptions (tuple): Tuple of exceptions to catch and retry on.
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    LOG.warning(f"Attempt {i + 1}/{max_retries} failed for {func.__name__}: {e}")
                    if i < max_retries - 1:
                        time.sleep(delay)
                    else:
                        LOG.error(f"Function {func.__name__} failed after {max_retries} retries.")
                        raise
        return wrapper
    return decorator