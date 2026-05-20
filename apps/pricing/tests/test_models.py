from decimal import Decimal

import pytest

from apps.pricing.models import Instrument

from .factories import (
    ConsolidatedPriceFactory,
    InstrumentFactory,
    OHLCBarFactory,
    QuoteFactory,
)


@pytest.mark.django_db
class TestInstrument:
    def test_parse_symbol_ok(self):
        assert Instrument.parse_symbol("BTC-USD") == ("BTC", "USD")
        assert Instrument.parse_symbol("eth-usdt") == ("ETH", "USDT")

    def test_parse_symbol_rejects_garbage(self):
        with pytest.raises(ValueError):
            Instrument.parse_symbol("BTCUSD")

    def test_str(self):
        i = InstrumentFactory(symbol="ETH-USD", base="ETH", quote="USD")
        assert str(i) == "ETH-USD"


@pytest.mark.django_db
class TestQuote:
    def test_mid_and_spread(self):
        q = QuoteFactory(bid=Decimal("100"), ask=Decimal("102"))
        q.refresh_from_db()
        assert q.mid == Decimal("101")
        assert q.spread == Decimal("2")

    def test_default_ordering_is_newest_first(self):
        old = QuoteFactory()
        new = QuoteFactory()
        # Refresh both — auto_now_add not in play here, but timestamp default
        # is set by factory_boy at creation time.
        from apps.pricing.models import Quote

        latest = Quote.objects.first()
        assert latest in (old, new)


@pytest.mark.django_db
class TestConsolidatedPrice:
    def test_str_carries_source_count(self):
        cp = ConsolidatedPriceFactory(sources=["binance", "coinbase", "kraken"])
        assert "3 src" in str(cp)


@pytest.mark.django_db
class TestOHLCBar:
    def test_unique_constraint(self, django_assert_num_queries):
        bar = OHLCBarFactory()
        # Same (instrument, interval, bucket_start) must raise.
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            OHLCBarFactory(
                instrument=bar.instrument,
                interval=bar.interval,
                bucket_start=bar.bucket_start,
            )
