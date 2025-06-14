import asyncio
import datetime
import logging
from typing import Generator

from tinkoff.invest import Client, CandleInstrument, SubscriptionInterval, InfoInstrument, TradeInstrument, \
    MarketDataResponse, Candle, AsyncClient, AioRequestError, OrderBook, OrderBookInstrument, SubscribeInfoResponse
from tinkoff.invest.market_data_stream.async_market_data_stream_manager import AsyncMarketDataStreamManager
from tinkoff.invest.market_data_stream.market_data_stream_interface import IMarketDataStreamManager
from tinkoff.invest.market_data_stream.market_data_stream_manager import MarketDataStreamManager

from invest_api.utils import invest_api_retry_status_codes

__all__ = ("MarketDataStreamService")

logger = logging.getLogger(__name__)


class MarketDataStreamService:
    """
    The class encapsulate tinkoff market data stream (gRPC) service api
    """
    def __init__(self, token: str, app_name: str) -> None:
        self.__token = token
        self.__app_name = app_name

    def start_candles_stream(
            self,
            figies: list[str],
            trade_before_time: datetime
    ) -> Generator[Candle, None, None]:
        """
        The method starts gRPC stream and return candles
        """
        logger.debug(f"Starting candles stream")

        with Client(self.__token, app_name=self.__app_name) as client:
            market_data_candles_stream: MarketDataStreamManager = client.create_market_data_stream()

            logger.info(f"Subscribe candles: {figies}")
            market_data_candles_stream.candles.subscribe(
                [
                    CandleInstrument(
                        figi=figi,
                        interval=SubscriptionInterval.SUBSCRIPTION_INTERVAL_ONE_MINUTE
                    )
                    for figi in figies
                ]
            )

            for market_data in market_data_candles_stream:
                logger.debug(f"market_data: {market_data}")

                # trading will stop at trade_before_time
                if datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc) >= trade_before_time:
                    logger.debug(f"Time to stop candle stream")
                    self.__stop_stream(market_data_candles_stream)
                    break

                if market_data.candle:
                    yield market_data.candle

        self.__stop_stream(market_data_candles_stream)

    
    async def start_async_candles_stream(
            self,
            figies: list[str],
            trade_before_time: datetime
    ) -> Generator[Candle, None, None]:
        """
        The method starts async gRPC stream and return candles
        """
        logger.debug(f"Starting async candles stream loop")

        while datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc) < trade_before_time:
            try:
                logger.debug(f"Starting async candles stream")

                async with AsyncClient(self.__token, app_name=self.__app_name) as client:
                    async_market_data_candles_stream: AsyncMarketDataStreamManager = client.create_market_data_stream()

                    logger.info(f"Subscribe candles: {figies}")
                    async_market_data_candles_stream.candles.subscribe(
                        [
                            CandleInstrument(
                                figi=figi,
                                interval=SubscriptionInterval.SUBSCRIPTION_INTERVAL_ONE_MINUTE
                            )
                            for figi in figies
                        ]
                    )

                    async for market_data in async_market_data_candles_stream:
                        logger.debug(f"market_data: {market_data}")

                        # trading will stop at trade_before_time
                        if datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc) >= trade_before_time:
                            logger.debug(f"Time to stop candle stream")
                            self.__stop_stream(async_market_data_candles_stream)
                            break

                        if market_data.candle:
                            yield market_data.candle

            except AioRequestError as ex:
                logger.error("AioRequestError code=%s repr=%s details=%s", str(ex.code), repr(ex), ex.details)

                if ex.code in invest_api_retry_status_codes():
                    logger.debug(f"Status code available for reconnect")
                    await asyncio.sleep(1)
                else:
                    raise

            finally:
                self.__stop_stream(async_market_data_candles_stream)

    
    
    async def start_async_orderbook_stream(
            self,
            figies: list[str],
            trade_before_time: datetime
    ) -> Generator[OrderBook, None, None]:
        """
        The method starts async gRPC stream and return orderbook
        """
        logger.debug(f"Starting async orderbook stream loop")

        while datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc) < trade_before_time:
            try:
                logger.debug(f"Starting async orderbook stream")

                async with AsyncClient(self.__token, app_name=self.__app_name) as client:
                    async_market_data_orderbook_stream: AsyncMarketDataStreamManager = client.create_market_data_stream()

                    logger.info(f"Subscribe orderbook: {figies}")

                    """
                    async_market_data_orderbook_stream.info.subscribe(
                        [
                            InfoInstrument(
                                instrument_id=figi
                            )
                            for figi in figies
                        ]
                    )
                    """
                    
                    async_market_data_orderbook_stream.order_book.subscribe(
                        [
                            OrderBookInstrument(
                                instrument_id=figi,
                                depth=10
                            )
                            for figi in figies
                        ]
                    )

                    async for market_data in async_market_data_orderbook_stream:
                        logger.debug(f"market_data: {market_data}")

                        # trading will stop at trade_before_time
                        
                        if datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc) >= trade_before_time:
                            logger.debug(f"Time to stop orderbook stream")
                            self.__stop_stream(async_market_data_orderbook_stream)
                            break
                        
                        if market_data.orderbook:
                            yield market_data.orderbook

            except AioRequestError as ex:
                logger.error("AioRequestError code=%s repr=%s details=%s", str(ex.code), repr(ex), ex.details)

                if ex.code in invest_api_retry_status_codes():
                    logger.info(f"Status code available for reconnect")
                    await asyncio.sleep(1)
                else:
                    raise

            finally:
                self.__stop_stream(async_market_data_orderbook_stream)

    
    @staticmethod
    def __stop_stream(stream: IMarketDataStreamManager) -> None:
        if stream:
            logger.info(f"Stopping stream")
            stream.stop()
