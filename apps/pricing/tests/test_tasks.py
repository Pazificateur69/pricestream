from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.pricing.models import ConsolidatedPrice, Quote
from apps.pricing.tasks import fetch_quotes

from .factories import InstrumentFactory


class _FakeClient:
    def __init__(self, name, bid, ask):
        self.name = name
        self._bid = bid
        self._ask = ask

    def fetch(self, symbol):
        return Decimal(self._bid), Decimal(self._ask)


@pytest.mark.django_db
def test_fetch_quotes_writes_quotes_and_consolidates(settings):
    settings.INSTRUMENTS = ["BTC-USD"]
    InstrumentFactory(symbol="BTC-USD")

    fake_clients = [
        _FakeClient("binance", "100", "101"),
        _FakeClient("coinbase", "100.5", "101.2"),
        _FakeClient("kraken", "100.2", "101.1"),
    ]

    with patch("apps.pricing.tasks.all_clients", return_value=fake_clients), patch(
        "apps.pricing.tasks._publish_to_kafka"
    ), patch("apps.pricing.tasks._broadcast_ws"):
        result = fetch_quotes()

    assert result["quotes"] == 3
    assert result["consolidated"] == 1
    assert result["arbitrages"] == 0
    assert Quote.objects.count() == 3
    cp = ConsolidatedPrice.objects.get()
    assert cp.bid == Decimal("100.5")
    assert cp.ask == Decimal("101.0")
    assert set(cp.sources) == {"binance", "coinbase", "kraken"}


@pytest.mark.django_db
def test_fetch_quotes_skips_failing_clients(settings):
    settings.INSTRUMENTS = ["BTC-USD"]
    InstrumentFactory(symbol="BTC-USD")

    class _Broken:
        name = "broken"

        def fetch(self, _symbol):
            return None

    fake_clients = [
        _FakeClient("binance", "100", "101"),
        _Broken(),
    ]
    with patch("apps.pricing.tasks.all_clients", return_value=fake_clients), patch(
        "apps.pricing.tasks._publish_to_kafka"
    ), patch("apps.pricing.tasks._broadcast_ws"):
        result = fetch_quotes()

    assert result["quotes"] == 1
    assert Quote.objects.count() == 1
