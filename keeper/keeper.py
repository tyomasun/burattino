import asyncio
import logging
import traceback

from tinkoff.invest import OrderBook

__all__ = ("Keeper")

logger = logging.getLogger(__name__)

class Keeper:
    """
    Class sends data to db queue.
    """
    def __init__(self, data_queue: asyncio.Queue) -> None:
        self.__data_queue = data_queue

    def save_data(self, data: OrderBook):
        try:
            logger.debug(f"Put data to db queue {str(data)}")

            self.__data_queue.put_nowait(data)
        except Exception as ex:
            logger.error(f"Error pu data to db queue {repr(ex)}")
            logger.error(traceback.format_exc())