from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.pricing.kafka_consumer import _bucket_start, handle_event
from apps.pricing.models import OHLCBar

from .factories import InstrumentFactory


class TestBucketStart:
    def test_1m(self):
        ts = datetime(2026, 1, 1, 12, 34, 56, tzinfo=UTC)
        assert _bucket_start(ts, "1m") == datetime(2026, 1, 1, 12, 34, tzinfo=UTC)

    def test_5m(self):
        ts = datetime(2026, 1, 1, 12, 37, 0, tzinfo=UTC)
        assert _bucket_start(ts, "5m") == datetime(2026, 1, 1, 12, 35, tzinfo=UTC)

    def test_1h(self):
        ts = datetime(2026, 1, 1, 12, 59, 0, tzinfo=UTC)
        assert _bucket_start(ts, "1h") == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.mark.django_db
class TestHandleEvent:
    def test_creates_bars_for_all_intervals(self):
        InstrumentFactory(symbol="BTC-USD")
        handle_event(
            {
                "instrument": "BTC-USD",
                "source": "binance",
                "bid": "100",
                "ask": "102",
                "ts": "2026-01-01T12:00:00+00:00",
            }
        )
        assert OHLCBar.objects.count() == 3

    def test_updates_existing_bar(self):
        InstrumentFactory(symbol="BTC-USD")
        payload = {
            "instrument": "BTC-USD",
            "source": "binance",
            "bid": "100",
            "ask": "102",
            "ts": "2026-01-01T12:00:30+00:00",
        }
        handle_event(payload)
        handle_event(
            {
                **payload,
                "bid": "110",
                "ask": "112",
                "ts": "2026-01-01T12:00:45+00:00",
            }
        )
        bar = OHLCBar.objects.get(interval="1m")
        assert bar.tick_count == 2
        assert bar.open == Decimal("101")  # (100+102)/2
        assert bar.close == Decimal("111")  # (110+112)/2
        assert bar.high == Decimal("111")
        assert bar.low == Decimal("101")

    def test_unknown_instrument_is_ignored(self):
        handle_event({"instrument": "DOGE-USD", "bid": "1", "ask": "2"})
        assert OHLCBar.objects.count() == 0
