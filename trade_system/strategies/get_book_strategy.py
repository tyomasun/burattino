import logging
import numpy as np
from decimal import Decimal
from typing import Optional


from tinkoff.invest import OrderBook, Order, HistoricCandle
from tinkoff.invest.utils import quotation_to_decimal

from configuration.settings import StrategySettings
from trade_system.signal import Signal, SignalType
from trade_system.strategies.base_strategy import IStrategy

__all__ = ("GetBookStrategy")

logger = logging.getLogger(__name__)


class GetBookStrategy(IStrategy):
    """
    Example of trade strategy.
    IMPORTANT: DO NOT USE IT FOR REAL TRADING!
    """
    # Consts for read and parse dict with strategy configuration

    __SIGNAL_VOLUME_NAME = "SIGNAL_VOLUME"
    __SIGNAL_MIN_TICKS_NAME = "SIGNAL_MIN_TICKS"
    __LONG_TAKE_NAME = "LONG_TAKE"
    __LONG_STOP_NAME = "LONG_STOP"
    __SHORT_TAKE_NAME = "SHORT_TAKE"
    __SHORT_STOP_NAME = "SHORT_STOP"
    __SIGNAL_MIN_TAIL_NAME = "SIGNAL_MIN_TAIL"

    def __init__(self, settings: StrategySettings) -> None:
        self.__settings = settings
        
        self.__signal_volume = int(settings.settings[self.__SIGNAL_VOLUME_NAME])
        self.__signal_min_ticks = int(settings.settings[self.__SIGNAL_MIN_TICKS_NAME])
        self.__signal_min_tail = Decimal(settings.settings[self.__SIGNAL_MIN_TAIL_NAME])

        self.__long_take = Decimal(settings.settings[self.__LONG_TAKE_NAME])
        self.__long_stop = Decimal(settings.settings[self.__LONG_STOP_NAME])

        self.__short_take = Decimal(settings.settings[self.__SHORT_TAKE_NAME])
        self.__short_stop = Decimal(settings.settings[self.__SHORT_STOP_NAME])
        
        self.__recent_candles = []
        self.__last_book = None
        self.__last_paired_book = None
        self.__long_spreads = []
        self.__short_spreads = []

        

    @property
    def settings(self) -> StrategySettings:
        return self.__settings

    def update_lot_count(self, lot: int) -> None:
        self.__settings.lot_size = lot

    def update_short_status(self, status: bool) -> None:
        self.__settings.short_enabled_flag = status

    def update_basic_asset_figi(self, figi: str) -> None:
        self.__settings.basic_asset_figi = figi
        
    def update_basic_asset_size(self, size: int) -> None:
        logger.debug(f"update_basic_asset_size {str(size)}")
        self.__settings.basic_asset_size = size

    

    def analyze_books(self, book: OrderBook) -> Optional[Signal]:
        """
        The method analyzes books and returns his decision.
        """
        logger.debug(f"Start analyze books for {self.settings.figi} strategy {__name__}. ")
        
        
        if not self.__update_recent_books(book):
            return None
        
        if self.__is_match_long():
            logger.info(f"Long signal detected {self.settings.figi}, ask = {str(book.asks[0].price)}, qty = {str(book.asks[0].quantity)}")
            #return self.__make_signal(SignalType.LONG, self.__long_take, self.__long_stop)

        if self.settings.short_enabled_flag and self.__is_match_short():
            logger.info(f"Short signal detected {self.settings.figi}, bid = {str(book.bids[0].price)}, qty = {str(book.bids[0].quantity)}")
            #return self.__make_signal(SignalType.SHORT, self.__short_take, self.__short_stop)
        
        return None

    def __add_spread(self, dest: list, value: Decimal) -> tuple[list, bool]:
        if dest and dest[-1] == value:
            return (dest, False)
        
        dest.append(value)

        spread_len = len(dest)
        
        if spread_len < self.__signal_min_ticks:
            logger.debug(f"Spreads in cache are low than required: {str(self.__signal_min_ticks)}")
            return (dest, False)

        #sorted(dest, key=lambda x: x.time)

        # keep only __signal_min_ticks candles in cache
        if spread_len > self.__signal_min_ticks:
            dest = dest[spread_len - self.__signal_min_ticks:]

        return (dest, True)
        
    
    def __update_spread(self) -> bool:
        if not self.__last_book or not self.__last_paired_book:
            return False
       
        bid = quotation_to_decimal(self.__last_book.bids[0].price)
        ask = quotation_to_decimal(self.__last_book.asks[0].price)

        base_bid = quotation_to_decimal(self.__last_paired_book.bids[0].price) * self.__settings.basic_asset_size
        base_ask = quotation_to_decimal(self.__last_paired_book.asks[0].price) * self.__settings.basic_asset_size

        
        long_spread = ask - base_bid
        short_spread = bid - base_ask

        self.__long_spreads, is_long_spread_ready = self.__add_spread(self.__long_spreads, long_spread)
        self.__short_spreads, is_short_spread_ready = self.__add_spread(self.__short_spreads, short_spread)
        
        logger.debug(f"long_spread = {str(self.__long_spreads)}")
        logger.debug(f"short_spread = {str(self.__short_spreads)}")
        
        return is_long_spread_ready and is_short_spread_ready
        
        
    def __update_recent_books(self, book) -> bool:
        if book.figi == self.settings.figi:
            self.__last_book = book            
            return self.__update_spread()
        elif book.figi == self.settings.basic_asset_figi:
            self.__last_paired_book = book            
            return self.__update_spread()
        else:
            logger.eror(f"Unknown book: {str(book)}")
            return False

    def __is_match_long(self) -> bool:
        """
        Check for LONG signal.
        """
        mean = np.average(self.__long_spreads)
        dev = np.std(self.__long_spreads, ddof=2)
        last = self.__long_spreads[-1]

        return last < mean - dev
        

    def __is_match_short(self) -> bool:
        """
        Check for SHORT signal. 
        """
        mean = np.average(self.__short_spreads)
        dev = np.std(self.__short_spreads, ddof=2)
        last = self.__short_spreads[-1]

        return last > mean + dev
        

    def __make_signal(
            self,
            signal_type: SignalType,
            profit_multy: Decimal,
            stop_multy: Decimal
    ) -> Signal:
        # take and stop based on configuration by close price level (close for last price)
        last_candle = self.__recent_candles[len(self.__recent_candles) - 1]

        signal = Signal(
            figi=self.settings.figi,
            signal_type=signal_type,
            take_profit_level=quotation_to_decimal(last_candle.close) * profit_multy,
            stop_loss_level=quotation_to_decimal(last_candle.close) * stop_multy
        )

        logger.info(f"Make Signal: {signal}")

        return signal

    def analyze_candles(self, candles: list[HistoricCandle]) -> Optional[Signal]:
        """
        The method analyzes candles and returns his decision.
        """
        return None
