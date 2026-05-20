from decimal import Decimal

import pytest

from apps.pricing.aggregator import detect_arbitrage

from .factories import InstrumentFactory, QuoteFactory


@pytest.mark.django_db
class TestDetectArbitrage:
    def test_returns_none_when_book_is_tight(self):
        instrument = InstrumentFactory()
        q1 = QuoteFactory(
            instrument=instrument, source="binance", bid=Decimal("100"), ask=Decimal("101")
        )
        q2 = QuoteFactory(
            instrument=instrument, source="coinbase", bid=Decimal("100.2"), ask=Decimal("101.1")
        )
        q1.refresh_from_db()
        q2.refresh_from_db()
        assert detect_arbitrage([q1, q2]) is None

    def test_detects_cross_venue_opportunity(self):
        instrument = InstrumentFactory()
        # Coinbase is willing to buy at 105, Binance willing to sell at 100.
        cheap = QuoteFactory(
            instrument=instrument, source="binance", bid=Decimal("99"), ask=Decimal("100")
        )
        rich = QuoteFactory(
            instrument=instrument, source="coinbase", bid=Decimal("105"), ask=Decimal("106")
        )
        cheap.refresh_from_db()
        rich.refresh_from_db()

        arb = detect_arbitrage([cheap, rich])
        assert arb is not None
        assert arb.buy_venue == "binance"
        assert arb.sell_venue == "coinbase"
        assert arb.buy_price == Decimal("100")
        assert arb.sell_price == Decimal("105")
        assert arb.spread == Decimal("5")
        # spread_bps = (5 / 102.5) * 10000 ≈ 487.8
        assert arb.spread_bps > Decimal("400")

    def test_returns_largest_when_multiple(self):
        instrument = InstrumentFactory()
        small = QuoteFactory(
            instrument=instrument, source="binance", bid=Decimal("100.5"), ask=Decimal("101")
        )
        mid = QuoteFactory(
            instrument=instrument, source="coinbase", bid=Decimal("101.5"), ask=Decimal("102")
        )
        big = QuoteFactory(
            instrument=instrument, source="kraken", bid=Decimal("110"), ask=Decimal("111")
        )
        for q in (small, mid, big):
            q.refresh_from_db()

        arb = detect_arbitrage([small, mid, big])
        assert arb is not None
        # Best edge: buy binance @ 101, sell kraken @ 110, spread = 9
        assert arb.buy_venue == "binance"
        assert arb.sell_venue == "kraken"
        assert arb.spread == Decimal("9")
