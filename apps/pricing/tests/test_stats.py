from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.pricing.stats import compute_rolling_stats

from .factories import ConsolidatedPriceFactory, InstrumentFactory


@pytest.mark.django_db
class TestComputeRollingStats:
    def test_empty_window_returns_zero_samples(self):
        instrument = InstrumentFactory()
        stats = compute_rolling_stats(instrument, window_seconds=60)
        assert stats.samples == 0
        assert stats.last_mid is None

    def test_aggregates_recent_consolidated_rows(self):
        instrument = InstrumentFactory()
        now = timezone.now()
        ConsolidatedPriceFactory(
            instrument=instrument,
            mid=Decimal("100"),
            bid=Decimal("99.5"),
            ask=Decimal("100.5"),
            timestamp=now - timedelta(seconds=30),
        )
        ConsolidatedPriceFactory(
            instrument=instrument,
            mid=Decimal("102"),
            bid=Decimal("101.5"),
            ask=Decimal("102.5"),
            timestamp=now - timedelta(seconds=10),
        )
        ConsolidatedPriceFactory(
            instrument=instrument,
            mid=Decimal("104"),
            bid=Decimal("103.5"),
            ask=Decimal("104.5"),
            timestamp=now - timedelta(seconds=1),
        )

        stats = compute_rolling_stats(instrument, window_seconds=60)
        assert stats.samples == 3
        assert stats.last_mid == Decimal("104")
        assert stats.min_mid == Decimal("100")
        assert stats.max_mid == Decimal("104")
        assert stats.avg_mid == Decimal("102")
        assert stats.mid_stdev is not None and stats.mid_stdev > Decimal("0")
        assert stats.avg_spread_bps is not None and stats.avg_spread_bps > Decimal("0")

    def test_excludes_rows_outside_window(self):
        instrument = InstrumentFactory()
        ConsolidatedPriceFactory(
            instrument=instrument,
            mid=Decimal("50"),
            timestamp=timezone.now() - timedelta(seconds=600),
        )
        ConsolidatedPriceFactory(
            instrument=instrument,
            mid=Decimal("100"),
            timestamp=timezone.now() - timedelta(seconds=10),
        )
        stats = compute_rolling_stats(instrument, window_seconds=60)
        assert stats.samples == 1
        assert stats.last_mid == Decimal("100")


@pytest.mark.django_db
class TestStatsEndpoint:
    def test_returns_400_without_instrument(self):
        r = APIClient().get("/api/stats/")
        assert r.status_code == 400

    def test_returns_400_for_invalid_window(self):
        InstrumentFactory(symbol="BTC-USD")
        r = APIClient().get("/api/stats/?instrument=BTC-USD&window=not-a-number")
        assert r.status_code == 400

    def test_returns_stats_payload(self):
        instrument = InstrumentFactory(symbol="BTC-USD")
        ConsolidatedPriceFactory(
            instrument=instrument,
            mid=Decimal("100"),
            bid=Decimal("99"),
            ask=Decimal("101"),
            timestamp=timezone.now() - timedelta(seconds=5),
        )
        r = APIClient().get("/api/stats/?instrument=BTC-USD&window=60")
        assert r.status_code == 200
        payload = r.json()
        assert payload["instrument"] == "BTC-USD"
        assert payload["samples"] == 1
        assert Decimal(payload["last_mid"]) == Decimal("100")

    def test_404_for_unknown_instrument(self):
        r = APIClient().get("/api/stats/?instrument=UNKNOWN-USD&window=60")
        assert r.status_code == 404
