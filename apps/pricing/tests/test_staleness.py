from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.pricing.aggregator import consolidate

from .factories import InstrumentFactory, QuoteFactory


@pytest.mark.django_db
class TestStalenessGate:
    def test_stale_quotes_are_dropped(self, settings):
        settings.MAX_QUOTE_AGE_SECONDS = 5
        instrument = InstrumentFactory()
        fresh = QuoteFactory(
            instrument=instrument, source="binance", bid=Decimal("100"), ask=Decimal("101")
        )
        stale = QuoteFactory(
            instrument=instrument,
            source="coinbase",
            bid=Decimal("200"),  # would dominate if it were included
            ask=Decimal("201"),
            timestamp=timezone.now() - timedelta(seconds=60),
        )
        fresh.refresh_from_db()
        stale.refresh_from_db()

        c = consolidate([fresh, stale])
        assert c is not None
        assert c.sources == ["binance"]
        assert c.bid == Decimal("100")
        assert c.ask == Decimal("101")

    def test_all_stale_returns_none(self, settings):
        settings.MAX_QUOTE_AGE_SECONDS = 5
        instrument = InstrumentFactory()
        q = QuoteFactory(
            instrument=instrument,
            timestamp=timezone.now() - timedelta(seconds=300),
        )
        q.refresh_from_db()
        assert consolidate([q]) is None
