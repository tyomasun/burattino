import datetime
import collections
import logging
import traceback
from decimal import Decimal


from tinkoff.invest import Candle, OrderBook, OrderExecutionReportStatus
from tinkoff.invest.utils import quotation_to_decimal

from blog.blogger import Blogger
from keeper.keeper import Keeper
from invest_api.services.client_service import ClientService
from invest_api.services.instruments_service import InstrumentService
from invest_api.services.market_data_service import MarketDataService
from invest_api.services.operations_service import OperationService
from invest_api.services.orders_service import OrderService
from invest_api.services.market_data_stream_service import MarketDataStreamService
from invest_api.utils import candle_to_historiccandle
from trade_system.signal import SignalType
from trade_system.strategies.base_strategy import IStrategy
from trading.trade_results import TradeResults
from configuration.settings import TradingSettings

__all__ = ("Trader")

logger = logging.getLogger(__name__)


class Trader:
    """
    The class encapsulate main trade logic.
    """

    def __init__(
            self,
            client_service: ClientService,
            instrument_service: InstrumentService,
            operation_service: OperationService,
            order_service: OrderService,
            stream_service: MarketDataStreamService,
            market_data_service: MarketDataService,
            blogger: Blogger,
            keeper: Keeper
    ) -> None:
        self.__today_trade_results: TradeResults = None
        self.__client_service = client_service
        self.__instrument_service = instrument_service
        self.__operation_service = operation_service
        self.__order_service = order_service
        self.__stream_service = stream_service
        self.__market_data_service = market_data_service
        self.__blogger = blogger
        self.__keeper = keeper

    async def trade_day(
            self,
            account_id: str,
            trading_settings: TradingSettings,
            strategies: list[IStrategy],
            trade_day_end_time: datetime,
            min_rub: int
    ) -> None:
        logger.info("Start preparations for trading today")
        today_trade_strategies = self.__get_today_strategies(strategies)
        if not today_trade_strategies:
            logger.info("No shares to trade today.")
            return None

        #self.__clear_all_positions(account_id, today_trade_strategies)

        rub_before_trade_day = self.__operation_service.available_rub_on_account(account_id)
        logger.info(f"Amount of RUB on account {rub_before_trade_day} and minimum for trading: {min_rub}")
        if rub_before_trade_day < min_rub:
            return None

        logger.info("Start trading today")
        #self.__blogger.start_trading_message(strategies, rub_before_trade_day)

        try:
            await self.__trading_orderbook(
                account_id,
                trading_settings,
                today_trade_strategies,
                trade_day_end_time
            )
            logger.debug("Test Results:")
            logger.debug(f"Current: {self.__today_trade_results.get_current_open_orders()}")
            logger.debug(f"Old: {self.__today_trade_results.get_closed_orders()}")
        except Exception as ex:
            logger.error(f"Trading error: {repr(ex)}")
            logger.error(traceback.format_exc())

        logger.info("Finishing trading today")
        #self.__blogger.finish_trading_message()

        """
        try:
            if self.__today_trade_results:
                for key_figi, value_order_id in self.__clear_all_positions(account_id, today_trade_strategies).items():
                    trade_order = self.__today_trade_results.close_position(key_figi, value_order_id)
                    self.__blogger.close_position_message(trade_order)
            else:
                self.__clear_all_positions(account_id, today_trade_strategies)
        except Exception as ex:
            logger.error(f"Finishing trading error: {repr(ex)}")
        """
        logger.info("Show trade results today")
        try:
            self.__summary_today_trade_results(account_id, rub_before_trade_day)
        except Exception as ex:
            logger.error(f"Summary trading day error: {repr(ex)}")

    
    async def __trading_orderbook(
            self,
            account_id: str,
            trading_settings: TradingSettings,
            strategies: dict[str, list[IStrategy]],
            trade_day_end_time: datetime
    ) -> None:
        logger.info(f"Subscribe and read OrderBook for {strategies.keys()}")

        # End trading before close trade session
        trade_before_time: datetime = \
            trade_day_end_time - datetime.timedelta(seconds=trading_settings.stop_trade_before_close)

        signals_before_time: datetime = \
            trade_day_end_time - datetime.timedelta(minutes=trading_settings.stop_signals_before_close)
        logger.debug(f"Stop time: signals - {signals_before_time}, trading - {trade_before_time}")

        current_books: dict[str, OrderBook] = dict()
        self.__today_trade_results = TradeResults()

        
        async for book in self.__stream_service.start_async_orderbook_stream(
                list(strategies.keys()),
                trade_before_time
        ):
            current_figi_book = current_books.setdefault(book.figi, book)
            if book.time < current_figi_book.time:
                # it happens (based on API documentation)
                logger.debug("Skip candle from past.")
                continue

            # check price from candle for take or stop price levels
            # current_trade_order = self.__today_trade_results.get_current_trade_order(candle.figi)
            
            """
            if current_trade_order:
                high, low = quotation_to_decimal(candle.high), quotation_to_decimal(candle.low)

                # Logic is:
                # if stop or take price level is between high and low, then stop or take will be executed
                
                try:
                    if low <= current_trade_order.signal.stop_loss_level <= high:
                        logger.info(f"STOP LOSS: {current_trade_order}")
                        self.__close_position_and_send_message(account_id, candle.figi, strategies)

                    elif low <= current_trade_order.signal.take_profit_level <= high:
                        logger.info(f"TAKE PROFIT: {current_trade_order}")
                        self.__close_position_and_send_message(account_id, candle.figi, strategies)
                except Exception as ex:
                    logger.error(f"Error check Stop loss and Take profit levels: {repr(ex)}")
            """
            
            if True: # book.time > current_figi_book.time and datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc) <= signals_before_time:

                self.__keeper.save_data(book)

                for strategy in strategies[book.figi]:
                    """
                    if not self.__market_data_service.is_stock_ready_for_trading(strategy.settings.figi):
                                logger.info(f"New signal has been skipped. Stock isn't ready for trading")
                    """
                    signal_new = strategy.analyze_books(book)
                    
                    """
                    if signal_new:
                        logger.info(f"New signal: {signal_new}")
    
                        try:
                            if signal_new.signal_type == SignalType.CLOSE:
                                if current_trade_order:
                                    logger.info(f"Close position by close signal: {current_trade_order}")
                                    self.__close_position_and_send_message(account_id, strategy.settings.figi, strategies)
                                else:
                                    logger.info(f"New signal has been skipped. No open position to close.")
    
                            elif current_trade_order:
                                logger.info(f"New signal has been skipped. Previous signal is still alive.")
    
                            elif not self.__market_data_service.is_stock_ready_for_trading(strategy.settings.figi):
                                logger.info(f"New signal has been skipped. Stock isn't ready for trading")
    
                            else:
                                available_lots = self.__open_position_lots_count(
                                    account_id,
                                    strategy.settings.max_lots_per_order,
                                    quotation_to_decimal(candle.close),
                                    strategy.settings.lot_size
                                )
    
                                logger.debug(f"Available lots: {available_lots}")
                                if available_lots > 0:
                                    open_order = self.__order_service.post_market_order(
                                        account_id=account_id,
                                        figi=strategy.settings.figi,
                                        count_lots=available_lots,
                                        is_buy=(signal_new.signal_type == SignalType.LONG)
                                    )
                                    if open_order.execution_report_status == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL or \
                                            open_order.execution_report_status == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_PARTIALLYFILL:
                                        open_position = self.__today_trade_results.open_position(
                                            strategy.settings.figi,
                                            open_order.order_id,
                                            signal_new
                                        )
                                        self.__blogger.open_position_message(open_position)
                                        logger.info(f"Open position: {open_position}")
                                    else:
                                        logger.info(f"Open order status failed: {open_order}")
                                else:
                                    logger.info(f"New signal has been skipped. No available money")
                        except Exception as ex:
                            logger.error(f"Error open new position by new signal: {repr(ex)}")
                    """
            current_books[book.figi] = book

        self.__keeper.save_data(None)
        logger.info("Today trading has been completed")

    
    def __summary_today_trade_results(
            self,
            account_id: str,
            rub_before_trade_day: Decimal
    ) -> None:
        logger.info("Today trading summary:")
        self.__blogger.summary_message()

        current_rub_on_depo = self.__operation_service.available_rub_on_account(account_id)
        logger.info(f"RUBs on account before:{rub_before_trade_day}, after:{current_rub_on_depo}")

        today_profit = current_rub_on_depo - rub_before_trade_day
        today_percent_profit = (today_profit / rub_before_trade_day) * 100
        logger.info(f"Today Profit:{today_profit} rub ({today_percent_profit} %)")
        self.__blogger.trading_depo_summary_message(rub_before_trade_day, current_rub_on_depo)

        if self.__today_trade_results:
            logger.info(f"Today Open Signals:")
            for figi_key, trade_order_value in self.__today_trade_results.get_current_open_orders().items():
                logger.info(f"Stock: {figi_key}")

                open_order_state = self.__order_service.get_order_state(account_id, trade_order_value.open_order_id)
                logger.info(f"Signal {trade_order_value.signal}")
                logger.info(f"Open: {open_order_state}")
                self.__blogger.summary_open_signal_message(trade_order_value, open_order_state)

            logger.info(f"All open positions should be closed manually.")

            logger.info(f"Today Closed Signals:")
            for figi_key, trade_orders_value in self.__today_trade_results.get_closed_orders().items():
                logger.info(f"Stock: {figi_key}")
                for trade_order in trade_orders_value:
                    open_order_state = self.__order_service.get_order_state(account_id, trade_order.open_order_id)
                    close_order_state = self.__order_service.get_order_state(account_id, trade_order.close_order_id)
                    logger.info(f"Signal {trade_order.signal}")
                    logger.info(f"Open: {open_order_state}")
                    logger.info(f"Close: {close_order_state}")
                    self.__blogger.summary_closed_signal_message(trade_order, open_order_state, close_order_state)
        else:
            logger.info(f"Something went wrong: today trade results is empty")
            logger.info(f"All open positions should be closed manually.")
            self.__blogger.fail_message()

        self.__blogger.final_message()

    def __open_position_lots_count(
            self,
            account_id: str,
            max_lots_per_order: int,
            price: Decimal,
            share_lot_size: int
    ) -> int:
        """
        Calculate counts of lots for order
        """
        current_rub_on_depo = self.__operation_service.available_rub_on_account(account_id)

        available_lots = int(current_rub_on_depo / (share_lot_size * price))

        return available_lots if max_lots_per_order > available_lots else max_lots_per_order

    def __clear_all_positions(
            self,
            account_id: str,
            strategies: dict[str, IStrategy]
    ) -> dict[str, str]:
        logger.info("Clear all orders and close all open positions")

        logger.debug("Cancel all order.")
        self.__client_service.cancel_all_orders(account_id)

        logger.debug("Close all positions.")
        return self.__close_position_by_figi(account_id, strategies.keys(), strategies)

    def __close_position_and_send_message(
            self,
            account_id: str,
            figi: str,
            strategies: dict[str, IStrategy]
    ) -> None:
        close_order_id = self.__close_position_by_figi(account_id, [figi], strategies).get(figi, None)
        if close_order_id:
            trade_order = self.__today_trade_results.close_position(figi, close_order_id)
            self.__blogger.close_position_message(trade_order)

    def __close_position_by_figi(
            self,
            account_id: str,
            figies: list[str],
            strategies: dict[str, IStrategy]
    ) -> dict[str, str]:
        result: dict[str, str] = dict()
        current_positions = self.__operation_service.positions_securities(account_id)

        if current_positions:
            logger.info(f"Current positions: {current_positions}")
            for position in current_positions:
                if position.figi in figies:
                    # Check a stock
                    if self.__market_data_service.is_stock_ready_for_trading(position.figi):
                        close_order = self.__order_service.post_market_order(
                            account_id=account_id,
                            figi=position.figi,
                            count_lots=abs(int(position.balance / strategies[position.figi].settings.lot_size)),
                            is_buy=(position.balance < 0)
                        )
                        if close_order.execution_report_status == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL or \
                                close_order.execution_report_status == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_PARTIALLYFILL:
                            result[position.figi] = close_order.order_id
                        else:
                            logger.info(f"Close order status failed: {close_order}")
        return result

    def __get_today_strategies(self, strategies: list[IStrategy]) -> dict[str, list[IStrategy]]:
        """
        Check and Select stocks for trading today.
        """
        logger.info("Check futures and strategy settings")
        today_trade_strategy: dict[str, list[IStrategy]] = collections.defaultdict(list)
        
        for strategy in strategies:
            logger.info(f"Update strategy settings: {str(strategy)}")
            
            future_settings = self.__instrument_service.future_by_figi(strategy.settings.figi)
            logger.debug(f"Check share settings for figi {strategy.settings.figi}: {future_settings}")

            if (not future_settings.otc_flag) \
                    and future_settings.buy_available_flag \
                    and future_settings.sell_available_flag \
                    and future_settings.api_trade_available_flag:
                logger.debug(f"Future is ready for trading")

                # refresh information by latest info
                strategy.update_lot_count(future_settings.lot)
                strategy.update_short_status(future_settings.short_enabled_flag)
                strategy.update_basic_asset_size(future_settings.basic_asset_size)

                # Find basic asset for future
                instruments = self.__instrument_service.find_instrument(future_settings.basic_asset_position_uid)
                if not instruments:
                    logger.info(f"Not found basic asset for future: {future_settings.figi}")
                    continue

                basic_asset_figi = instruments[0].figi
                strategy.update_basic_asset_figi(basic_asset_figi)
                
                # Формируем словарь из основного и парного инструментов
                today_trade_strategy[strategy.settings.figi] = [strategy]
                today_trade_strategy[basic_asset_figi] = [strategy]
                    

        logger.debug(f"Generated list of Instruments {str(today_trade_strategy)}")
        return today_trade_strategy
