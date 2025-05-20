import logging
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
        logger.info("analyze_books")
        logger.debug(f"Start analyze books for {self.settings.figi} strategy {__name__}. ")
        
        
        if not self.__update_recent_books(book):
            return None
        
        """
        if self.__is_match_long():
            logger.info(f"Signal (LONG) {self.settings.figi} has been found.")
            return self.__make_signal(SignalType.LONG, self.__long_take, self.__long_stop)

        if self.settings.short_enabled_flag and self.__is_match_short():
            logger.info(f"Signal (SHORT) {self.settings.figi} has been found.")
            return self.__make_signal(SignalType.SHORT, self.__short_take, self.__short_stop)
        """
        return None

    def __update_spread(self) -> bool:
        
        
        if not self.__last_book or not self.__last_paired_book:
            return False

        # Calculate spread (two spreads: ask and bid)
        
        bid = quotation_to_decimal(self.__last_book.bids[0].price)
        ask = quotation_to_decimal(self.__last_book.asks[0].price)

        base_bid = quotation_to_decimal(self.__last_paired_book.bids[0].price) * self.__settings.basic_asset_size
        base_ask = quotation_to_decimal(self.__last_paired_book.asks[0].price) * self.__settings.basic_asset_size

        
        logger.info(f"bid = {str(bid)}")
        logger.info(f"ask = {str(ask)}")

        logger.info(f"base_bid = {str(base_bid)}")
        logger.info(f"base_ask = {str(base_ask)}")
        
        long_spread = ask - base_bid
        short_spread = bid - base_ask
        
        if not self.__long_spreads or self.__long_spreads[-1] != long_spread:
            self.__long_spreads.append(long_spread)
        
        if not self.__short_spreads or self.__short_spreads[-1] != short_spread:
            self.__short_spreads.append(short_spread)
        
        
        logger.info(f"long_spread = {str(self.__long_spreads)}")
        logger.info(f"short_spread = {str(self.__short_spreads)}")
        
        spread_len = len(self.__long_spreads)
        
        if spread_len < self.__signal_min_ticks:
            logger.debug(f"Spreds in cache are low than required")
            return False

        #sorted(dest, key=lambda x: x.time)
        
        # keep only __signal_min_ticks candles in cache
        if spread_len > self.__signal_min_ticks:
            self.__long_spreads = self.__long_spreads[spread_len - self.__signal_min_ticks:]
            self.__short_spreads = self.__short_spreads[spread_len - self.__signal_min_ticks:]

        return True
        
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
        Check for LONG signal. All candles in cache:
        Green candle, tail lower than __signal_min_tail, volume more that __signal_volume
        """
        for candle in self.__recent_candles:
            logger.debug(f"Recent Candle to analyze {self.settings.figi} LONG: {candle}")
            open_, high, close, low = quotation_to_decimal(candle.open), quotation_to_decimal(candle.high), \
                                      quotation_to_decimal(candle.close), quotation_to_decimal(candle.low)

            if open_ < close \
                    and ((high - close) / (high - low)) <= self.__signal_min_tail \
                    and candle.volume >= self.__signal_volume:
                logger.debug(f"Continue analyze {self.settings.figi}")
                continue

            logger.debug(f"Break analyze {self.settings.figi}")
            break
        else:
            logger.debug(f"Signal detected {self.settings.figi}")
            return True

        return False

    def __is_match_short(self) -> bool:
        """
        Check for LONG signal. All candles in cache:
        Red candle, tail lower than __signal_min_tail, volume more that __signal_volume
        """
        for candle in self.__recent_candles:
            logger.debug(f"Recent Candle to analyze {self.settings.figi} SHORT: {candle}")
            open_, high, close, low = quotation_to_decimal(candle.open), quotation_to_decimal(candle.high), \
                                      quotation_to_decimal(candle.close), quotation_to_decimal(candle.low)

            if open_ > close \
                    and ((close - low) / (high - low)) <= self.__signal_min_tail \
                    and candle.volume >= self.__signal_volume:
                logger.debug(f"Continue analyze {self.settings.figi}")
                continue

            logger.debug(f"Break analyze {self.settings.figi}")
            break
        else:
            logger.debug(f"Signal detected {self.settings.figi}")
            return True

        return False

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
