import datetime
import logging

from tinkoff.invest import Client, TradingSchedule, InstrumentIdType, InstrumentStatus, InstrumentShort
from tinkoff.invest.utils import quotation_to_decimal

from configuration.settings import ShareSettings, FutureSettings
from invest_api.invest_error_decorators import invest_error_logging, invest_api_retry
from invest_api.utils import moex_exchange_name

__all__ = ("InstrumentService")

logger = logging.getLogger(__name__)


class InstrumentService:
    """
    The class encapsulate tinkoff instruments api
    """
    def __init__(self, token: str, app_name: str) -> None:
        self.__token = token
        self.__app_name = app_name

    def moex_today_trading_schedule(self) -> (bool, datetime, datetime):
        """
        :return: Information about trading day status, datetime trading day start, datetime trading day end
        (both on today)
        """
        for schedule in self.__trading_schedules(
                exchange=moex_exchange_name(),
                _from=datetime.datetime.utcnow(),
                _to=datetime.datetime.utcnow() + datetime.timedelta(days=1)
        ):
            for day in schedule.days:
                if day.date.date() == datetime.date.today():
                    logger.info(f"MOEX today schedule: {day}")
                    return day.is_trading_day, day.start_time, day.end_time

        return False, datetime.datetime.utcnow(), datetime.datetime.utcnow()

    @invest_api_retry()
    @invest_error_logging
    def __trading_schedules(
            self,
            exchange: str,
            _from: datetime,
            _to: datetime
    ) -> list[TradingSchedule]:
        result = []

        with Client(self.__token, app_name=self.__app_name) as client:
            logger.debug(f"Trading Schedules for exchange: {exchange}, from: {_from}, to: {_to}")

            for schedule in client.instruments.trading_schedules(
                    exchange=exchange,
                    from_=_from,
                    to=_to
            ).exchanges:
                logger.debug(f"{schedule}")
                result.append(schedule)

        return result

    @invest_api_retry()
    @invest_error_logging
    def find_instrument(self, query: str) -> list[InstrumentShort]:
         with Client(self.__token, app_name=self.__app_name) as client:
            logger.debug(f"FindInstrument query: {query}")
        
            instruments = client.instruments.find_instrument(
                query=query
            ).instruments
            logger.debug(f"Found instruments: {instruments}")

            return instruments
    
    @invest_api_retry()
    @invest_error_logging
    def share_by_figi(self, figi: str) -> ShareSettings:
        """
        :return: Information about share settings by it figi
        """
        with Client(self.__token, app_name=self.__app_name) as client:
            logger.debug(f"ShareBy figi: {figi}:")

            share = client.instruments.share_by(
                id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
                id=figi
            ).instrument
            logger.debug(f"{share}")

            return ShareSettings(
                ticker=share.ticker,
                lot=share.lot,
                short_enabled_flag=share.short_enabled_flag,
                otc_flag=share.otc_flag,
                buy_available_flag=share.buy_available_flag,
                sell_available_flag=share.sell_available_flag,
                api_trade_available_flag=share.api_trade_available_flag
            )
            

    @invest_api_retry()
    @invest_error_logging
    def future_by_figi(self, figi: str) -> FutureSettings:
        """
        :return: Information about share settings by it figi
        """
        with Client(self.__token, app_name=self.__app_name) as client:
            logger.debug(f"FutureBy figi: {figi}:")

            future = client.instruments.future_by(
                id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
                id=figi
            ).instrument
            logger.debug(f"{future}")

            return FutureSettings(
                ticker=future.ticker,
                lot=future.lot,
                short_enabled_flag=future.short_enabled_flag,
                otc_flag=future.otc_flag,
                buy_available_flag=future.buy_available_flag,
                sell_available_flag=future.sell_available_flag,
                api_trade_available_flag=future.api_trade_available_flag,
                basic_asset=future.basic_asset,
                basic_asset_size=quotation_to_decimal(future.basic_asset_size),
                basic_asset_position_uid=future.basic_asset_position_uid
            )
            
    
    @invest_api_retry()
    @invest_error_logging
    def __currencies(self) -> None:
        with Client(self.__token, app_name=self.__app_name) as client:
            for cur in client.instruments.currencies(
                    instrument_status=InstrumentStatus.INSTRUMENT_STATUS_BASE
            ).instruments:
                logger.debug(f"{cur}")

    @invest_api_retry()
    @invest_error_logging
    def __instrument_by_figi(self, figi: str) -> None:
        with Client(self.__token, app_name=self.__app_name) as client:
            logger.debug(f"InstrumentBy figi: {figi}:")

            instrument = client.instruments.get_instrument_by(id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
                                                              id=figi).instrument

            logger.debug(f"{instrument}")
