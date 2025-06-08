import asyncio
import logging
import traceback
import asyncpg

from configuration.settings import KeepSettings

__all__ = ("KeepWorker")

logger = logging.getLogger(__name__)

BATCH_SIZE = 100
STOP_SIGNAL = None

class KeepWorker:
    """
    Class is represent worker (coroutine) for asyncio task.
    Checks available data in queue and save they asynchronously into DB.
    """
    def __init__(
        self,
        keep_settings: KeepSettings,
        data_queue: asyncio.Queue
    ) -> None:
        self.__data_queue = data_queue


    async def worker(self) -> None:
        conn = await asyncpg.connect("postgres://juman:zemlyanika7&@localhost:5432/mystery")
        try:
            batch: list[tuple] = []
            while True:
                data = await self.__data_queue.get()
                logger.debug(f"Get data from queue (size: {self.__data_queue.qsize()}): {data}")

                if data is STOP_SIGNAL:
                    logger.info("Stop signal has been received.")
                    if batch:
                        await self.__save_batch(conn, batch)
                    self.__data_queue.task_done()
                    break

                batch.append(data)
                self.__data_queue.task_done()

                if len(batch) >= BATCH_SIZE:
                    await self.__save_batch(conn, batch)
                    batch = []
            
            logger.info("The Keeper has completed its work.")
        except Exception as ex:
            logger.error(f"Error saving the data to the database: {repr(ex)}") 
            logger.error(traceback.format_exc())
        finally:
            await conn.close()
            

    async def __save_batch(self, conn: asyncpg.Connection, batch: list[tuple]) -> None:
        try:
            logger.debug(f"Try copy batch: {str(batch)}")
            await conn.copy_records_to_table(
                "order_book",
                records=batch,
                columns=[
                    'ticker',
                    'datetime',
                    'bid_price_1',
                    'bid_qty_1',
                    'ask_price_1',
                    'ask_qty_1'
                ]
            )
            logger.debug(f"Batch saved")
        except Exception as ex:
            logger.error(f"Error COPY the data to the database: {repr(ex)}") 
            logger.error(traceback.format_exc())
                