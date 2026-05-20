"""Thin HTTP clients for the public ticker endpoints of the supported exchanges.

Every client returns a normalised tuple `(bid: Decimal, ask: Decimal)` for a given
symbol like `BTC-USD`. No authentication is needed for these endpoints.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(5.0, connect=3.0)


class ExchangeClient(Protocol):
    name: str

    def fetch(self, symbol: str) -> tuple[Decimal, Decimal] | None: ...


class BinanceClient:
    name = "binance"
    base_url = "https://api.binance.com"

    @staticmethod
    def _to_binance_symbol(symbol: str) -> str:
        # BTC-USD → BTCUSDT (Binance trades USDT, not USD)
        base, _, quote = symbol.partition("-")
        if quote.upper() == "USD":
            quote = "USDT"
        return f"{base.upper()}{quote.upper()}"

    def fetch(self, symbol: str) -> tuple[Decimal, Decimal] | None:
        url = f"{self.base_url}/api/v3/ticker/bookTicker"
        params = {"symbol": self._to_binance_symbol(symbol)}
        try:
            r = httpx.get(url, params=params, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            return Decimal(data["bidPrice"]), Decimal(data["askPrice"])
        except Exception as exc:
            logger.warning("Binance fetch failed for %s: %s", symbol, exc)
            return None


class CoinbaseClient:
    name = "coinbase"
    base_url = "https://api.exchange.coinbase.com"

    @staticmethod
    def _to_coinbase_symbol(symbol: str) -> str:
        # BTC-USD → BTC-USD (already correct).
        return symbol.upper()

    def fetch(self, symbol: str) -> tuple[Decimal, Decimal] | None:
        url = f"{self.base_url}/products/{self._to_coinbase_symbol(symbol)}/book"
        try:
            r = httpx.get(url, params={"level": 1}, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            bid = Decimal(data["bids"][0][0])
            ask = Decimal(data["asks"][0][0])
            return bid, ask
        except Exception as exc:
            logger.warning("Coinbase fetch failed for %s: %s", symbol, exc)
            return None


class KrakenClient:
    name = "kraken"
    base_url = "https://api.kraken.com"

    @staticmethod
    def _to_kraken_symbol(symbol: str) -> str:
        # Kraken uses XBT for BTC and ZUSD legacy codes for some pairs.
        mapping = {"BTC": "XBT"}
        base, _, quote = symbol.partition("-")
        base = mapping.get(base.upper(), base.upper())
        return f"{base}{quote.upper()}"

    def fetch(self, symbol: str) -> tuple[Decimal, Decimal] | None:
        url = f"{self.base_url}/0/public/Ticker"
        params = {"pair": self._to_kraken_symbol(symbol)}
        try:
            r = httpx.get(url, params=params, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            payload = r.json()
            if payload.get("error"):
                logger.warning("Kraken returned error for %s: %s", symbol, payload["error"])
                return None
            result = payload["result"]
            (_, ticker), = result.items()
            bid = Decimal(ticker["b"][0])
            ask = Decimal(ticker["a"][0])
            return bid, ask
        except Exception as exc:
            logger.warning("Kraken fetch failed for %s: %s", symbol, exc)
            return None


def all_clients() -> list[ExchangeClient]:
    return [BinanceClient(), CoinbaseClient(), KrakenClient()]
