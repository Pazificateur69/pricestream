from decimal import Decimal

import pytest

from apps.pricing.aggregator import consolidate

from .factories import InstrumentFactory, QuoteFactory


@pytest.mark.django_db
class TestConsolidate:
    def test_returns_none_on_empty(self):
        assert consolidate([]) is None

    def test_best_bid_best_ask(self):
        instrument = InstrumentFactory()
        q1 = QuoteFactory(instrument=instrument, source="binance", bid=Decimal("100"), ask=Decimal("101"))
        q2 = QuoteFactory(instrument=instrument, source="coinbase", bid=Decimal("100.5"), ask=Decimal("101.2"))
        q3 = QuoteFactory(instrument=instrument, source="kraken", bid=Decimal("99.8"), ask=Decimal("100.9"))
        for q in (q1, q2, q3):
            q.refresh_from_db()

        c = consolidate([q1, q2, q3])
        assert c is not None
        assert c.bid == Decimal("100.5")
        assert c.ask == Decimal("100.9")
        assert c.mid == (Decimal("100.5") + Decimal("100.9")) / Decimal(2)
        assert c.sources == ["binance", "coinbase", "kraken"]

    def test_skips_invalid_quotes(self):
        instrument = InstrumentFactory()
        good = QuoteFactory(instrument=instrument, bid=Decimal("100"), ask=Decimal("101"))
        bad = QuoteFactory(
            instrument=instrument, source="coinbase", bid=Decimal("0"), ask=Decimal("0")
        )
        good.refresh_from_db()
        bad.refresh_from_db()
        c = consolidate([good, bad])
        assert c is not None
        assert c.sources == ["binance"]

    def test_crossed_book_falls_back_to_mid_of_mids(self):
        instrument = InstrumentFactory()
        # Crossed: max(bid)=105 > min(ask)=100
        q1 = QuoteFactory(instrument=instrument, source="binance", bid=Decimal("105"), ask=Decimal("106"))
        q2 = QuoteFactory(instrument=instrument, source="coinbase", bid=Decimal("99"), ask=Decimal("100"))
        q1.refresh_from_db()
        q2.refresh_from_db()
        c = consolidate([q1, q2])
        assert c is not None
        # mid of mids = (105.5 + 99.5)/2 = 102.5
        assert c.mid == Decimal("102.5")
