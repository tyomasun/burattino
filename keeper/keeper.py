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

    def save_data(self, data: OrderBook, ticker: str) -> None:
        try:
            logger.debug(f"Put data to db queue {str(data)}")
            book = data
            if book:
                book = self.__flatten_order_book(data, ticker)
            self.__data_queue.put_nowait(book)
        except Exception as ex:
            logger.error(f"Error put data to db queue {repr(ex)}")
            logger.error(traceback.format_exc())
            

    def __flatten_order_book(self, order_book: OrderBook, ticker: str, depth:int = 10) -> tuple:
        # Извлекаем цены и количества для bids
        bid_prices = []
        bid_quantities = []
        for i, bid in enumerate(order_book.bids[:depth]):
            bid_prices.append(float(quotation_to_decimal(bid.price)))
            bid_quantities.append(bid.quantity)
        
        # Дополняем нулями, если стаканов меньше depth
        while len(bid_prices) < depth:
            bid_prices.append(0.0)
            bid_quantities.append(0)
        
        # Извлекаем цены и количества для asks
        ask_prices = []
        ask_quantities = []
        for i, ask in enumerate(order_book.asks[:depth]):
            ask_prices.append(float(quotation_to_decimal(ask.price)))
            ask_quantities.append(ask.quantity)
        
        # Дополняем нулями, если стаканов меньше depth
        while len(ask_prices) < depth:
            ask_prices.append(0.0)
            ask_quantities.append(0)
        
        # Собираем все в один кортеж
        return (
            ticker,
            order_book.time,
            bid_prices[0],  # Распаковываем bid_price_1..bid_price_N
            bid_quantities[0],  # Распаковываем bid_qty_1..bid_qty_N
            ask_prices[0],  # Распаковываем ask_price_1..ask_price_N
            ask_quantities[0]  # Распаковываем ask_qty_1..ask_qty_N
            
        )