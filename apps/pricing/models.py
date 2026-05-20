"""Domain models for pricestream.

The schema purposefully mirrors what a small liquidity-provider stack looks like:

- `Instrument` is the tradable pair (BTC-USD, ETH-USD, ...).
- `Quote` is a raw observation from a single exchange.
- `ConsolidatedPrice` is the cross-venue mid we recompute on every tick.
- `OHLCBar` is the rolled-up OHLCV bucket built by the Kafka consumer.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils import timezone


class Instrument(models.Model):
    symbol = models.CharField(max_length=20, unique=True, db_index=True)
    base = models.CharField(max_length=10)
    quote = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("symbol",)

    def __str__(self) -> str:
        return self.symbol

    @classmethod
    def parse_symbol(cls, symbol: str) -> tuple[str, str]:
        """Split `BTC-USD` into ('BTC', 'USD')."""
        base, _, quote = symbol.partition("-")
        if not quote:
            raise ValueError(f"Invalid symbol: {symbol!r}")
        return base.upper(), quote.upper()


class Quote(models.Model):
    """Raw bid/ask observation from one exchange."""

    class Source(models.TextChoices):
        BINANCE = "binance", "Binance"
        COINBASE = "coinbase", "Coinbase"
        KRAKEN = "kraken", "Kraken"

    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="quotes")
    source = models.CharField(max_length=20, choices=Source.choices, db_index=True)
    bid = models.DecimalField(max_digits=24, decimal_places=10)
    ask = models.DecimalField(max_digits=24, decimal_places=10)
    timestamp = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        ordering = ("-timestamp",)
        indexes = [
            models.Index(fields=["instrument", "-timestamp"]),
            models.Index(fields=["source", "-timestamp"]),
        ]

    def __str__(self) -> str:
        return f"{self.instrument.symbol}@{self.source} {self.bid}/{self.ask}"

    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / Decimal(2)

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid


class ConsolidatedPrice(models.Model):
    """Cross-venue mid-price snapshot — the consolidated tape."""

    instrument = models.ForeignKey(
        Instrument, on_delete=models.CASCADE, related_name="consolidated_prices"
    )
    mid = models.DecimalField(max_digits=24, decimal_places=10)
    bid = models.DecimalField(max_digits=24, decimal_places=10)
    ask = models.DecimalField(max_digits=24, decimal_places=10)
    sources = models.JSONField(default=list)
    timestamp = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        ordering = ("-timestamp",)
        indexes = [
            models.Index(fields=["instrument", "-timestamp"]),
        ]

    def __str__(self) -> str:
        return f"{self.instrument.symbol} mid={self.mid} ({len(self.sources)} src)"


class OHLCBar(models.Model):
    """Open / high / low / close / volume bar for a given interval."""

    class Interval(models.TextChoices):
        M1 = "1m", "1 minute"
        M5 = "5m", "5 minutes"
        H1 = "1h", "1 hour"

    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="ohlc_bars")
    interval = models.CharField(max_length=8, choices=Interval.choices, db_index=True)
    bucket_start = models.DateTimeField(db_index=True)
    open = models.DecimalField(max_digits=24, decimal_places=10)
    high = models.DecimalField(max_digits=24, decimal_places=10)
    low = models.DecimalField(max_digits=24, decimal_places=10)
    close = models.DecimalField(max_digits=24, decimal_places=10)
    volume = models.DecimalField(max_digits=24, decimal_places=10, default=0)
    tick_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-bucket_start",)
        unique_together = ("instrument", "interval", "bucket_start")
        indexes = [
            models.Index(fields=["instrument", "interval", "-bucket_start"]),
        ]

    def __str__(self) -> str:
        return f"{self.instrument.symbol} {self.interval}@{self.bucket_start:%Y-%m-%d %H:%M}"


class ArbitrageOpportunity(models.Model):
    """Cross-venue arbitrage signal.

    Triggered when, on a single round of fetches, the best bid on one venue
    is *strictly higher* than the best ask on another venue (book crossed
    across exchanges). In an LP context this is what a market-maker captures
    by buying on the cheap venue and immediately selling on the rich one.
    """

    instrument = models.ForeignKey(
        Instrument, on_delete=models.CASCADE, related_name="arbitrage_opportunities"
    )
    buy_venue = models.CharField(max_length=20)
    buy_price = models.DecimalField(max_digits=24, decimal_places=10)
    sell_venue = models.CharField(max_length=20)
    sell_price = models.DecimalField(max_digits=24, decimal_places=10)
    spread = models.DecimalField(max_digits=24, decimal_places=10)
    spread_bps = models.DecimalField(max_digits=12, decimal_places=4)
    timestamp = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        ordering = ("-timestamp",)
        indexes = [
            models.Index(fields=["instrument", "-timestamp"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.instrument.symbol} BUY@{self.buy_venue} {self.buy_price} → "
            f"SELL@{self.sell_venue} {self.sell_price} ({self.spread_bps} bps)"
        )
