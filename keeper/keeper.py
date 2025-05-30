import asyncio
import logging
import traceback

from tinkoff.invest import OrderBook
from tinkoff.invest.utils import quotation_to_decimal

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

            self.__data_queue.put_nowait(self.__flatten_order_book(data))
        except Exception as ex:
            logger.error(f"Error put data to db queue {repr(ex)}")
            logger.error(traceback.format_exc())
            

    def __flatten_order_book(self, order_book: OrderBook , depth=10) -> dict:
        # Преобразуем bids в плоскую структуру
        bids_data = {}
        for i in range(1, depth + 1):
            if i <= len(order_book.bids):
                bid = order_book.bids[i-1]
                bids_data[f'bid_price_{i}'] = quotation_to_decimal(bid.price)
                bids_data[f'bid_qty_{i}'] = bid.quantity
            else:
                bids_data[f'bid_price_{i}'] = 0.0
                bids_data[f'bid_qty_{i}'] = 0
        
        # Преобразуем asks в плоскую структуру
        asks_data = {}
        for i in range(1, depth + 1):
            if i <= len(order_book.asks):
                ask = order_book.asks[i-1]
                asks_data[f'ask_price_{i}'] = quotation_to_decimal(ask.price)
                asks_data[f'ask_qty_{i}'] = ask.quantity
            else:
                asks_data[f'ask_price_{i}'] = 0.0
                asks_data[f'ask_qty_{i}'] = 0
        
        # Основные поля
        return {
            'figi': order_book.figi,
            'depth': order_book.depth,
            'is_consistent': order_book.is_consistent,
            **bids_data,  # Распаковываем bid_price_1..bid_price_N и bid_qty_1..bid_qty_N
            **asks_data,  # Распаковываем ask_price_1..ask_price_N и ask_qty_1..ask_qty_N
            'time': order_book.time,
            'instrument_uid': order_book.instrument_uid,
            'order_book_type': str(order_book.order_book_type)
        }