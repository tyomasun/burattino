import datetime
import uuid
from decimal import Decimal

from grpc import StatusCode
from tinkoff.invest import MoneyValue, Quotation, Candle, HistoricCandle, TradingDay
from tinkoff.invest.utils import quotation_to_decimal, decimal_to_quotation

__all__ = ()


def rub_currency_name() -> str:
    return "rub"


def moex_exchange_name() -> str:
    return "MOEX_PLUS_WEEKEND"


def moneyvalue_to_decimal(money_value: MoneyValue) -> Decimal:
    return quotation_to_decimal(
        Quotation(
            units=money_value.units,
            nano=money_value.nano
        )
    )


def decimal_to_moneyvalue(decimal: Decimal, currency: str = rub_currency_name()) -> MoneyValue:
    quotation = decimal_to_quotation(decimal)
    return MoneyValue(
        currency=currency,
        units=quotation.units,
        nano=quotation.nano
    )


def generate_order_id() -> str:
    return str(uuid.uuid4())


def candle_to_historiccandle(candle: Candle) -> HistoricCandle:
    return HistoricCandle(
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=candle.volume,
        time=candle.time,
        is_complete=True
    )


def invest_api_retry_status_codes() -> set[StatusCode]:
    return {StatusCode.CANCELLED, StatusCode.DEADLINE_EXCEEDED, StatusCode.RESOURCE_EXHAUSTED,
            StatusCode.FAILED_PRECONDITION, StatusCode.ABORTED, StatusCode.INTERNAL,
            StatusCode.UNAVAILABLE, StatusCode.DATA_LOSS, StatusCode.UNKNOWN}

def get_next_morning() -> datetime:
    return datetime.datetime.combine(datetime.datetime.now(datetime.UTC), datetime.time.min) + datetime.timedelta(days=1)


def is_time_in_regular_session(trading_day: TradingDay, time: datetime) -> bool:
    
    # Находим все интервалы с типом 'regular_trading_session'
    regular_intervals = [
        interval.interval 
        for interval in trading_day.intervals 
        if interval.type == 'regular_trading_session'
    ]
    
    # Проверяем, находится ли текущее время в каком-либо из этих интервалов
    return any(
        interval.start_ts <= time <= interval.end_ts
        for interval in regular_intervals
    )
