import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .factories import (
    ConsolidatedPriceFactory,
    InstrumentFactory,
    OHLCBarFactory,
    QuoteFactory,
)


@pytest.fixture
def api_client(db):
    user = get_user_model().objects.create_user(username="trader", password="pw")
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.mark.django_db
class TestInstrumentsAPI:
    def test_list(self, api_client):
        InstrumentFactory(symbol="BTC-USD")
        InstrumentFactory(symbol="ETH-USD", base="ETH")
        r = api_client.get("/api/instruments/")
        assert r.status_code == 200
        symbols = {row["symbol"] for row in r.json()["results"]}
        assert symbols == {"BTC-USD", "ETH-USD"}


@pytest.mark.django_db
class TestQuotesAPI:
    def test_list_filters_by_instrument(self, api_client):
        btc = InstrumentFactory(symbol="BTC-USD")
        eth = InstrumentFactory(symbol="ETH-USD", base="ETH")
        QuoteFactory(instrument=btc)
        QuoteFactory(instrument=eth)
        r = api_client.get("/api/quotes/?instrument=BTC-USD")
        assert r.status_code == 200
        symbols = {row["instrument"] for row in r.json()["results"]}
        assert symbols == {"BTC-USD"}

    def test_latest_returns_consolidated_price(self, api_client):
        btc = InstrumentFactory(symbol="BTC-USD")
        ConsolidatedPriceFactory(instrument=btc, mid="50500")
        r = api_client.get("/api/quotes/latest/?instrument=BTC-USD")
        assert r.status_code == 200
        assert r.json()["instrument"] == "BTC-USD"

    def test_latest_400_without_instrument(self, api_client):
        r = api_client.get("/api/quotes/latest/")
        assert r.status_code == 400

    def test_latest_404_when_no_data(self, api_client):
        InstrumentFactory(symbol="BTC-USD")
        r = api_client.get("/api/quotes/latest/?instrument=BTC-USD")
        assert r.status_code == 404


@pytest.mark.django_db
class TestOHLCAPI:
    def test_filters_by_instrument_and_interval(self, api_client):
        btc = InstrumentFactory(symbol="BTC-USD")
        eth = InstrumentFactory(symbol="ETH-USD", base="ETH")
        OHLCBarFactory(instrument=btc, interval="1m")
        OHLCBarFactory(instrument=eth, interval="1m")
        OHLCBarFactory(instrument=btc, interval="5m")
        r = api_client.get("/api/ohlc/?instrument=BTC-USD&interval=1m")
        assert r.status_code == 200
        results = r.json()["results"]
        assert len(results) == 1
        assert results[0]["instrument"] == "BTC-USD"
        assert results[0]["interval"] == "1m"


@pytest.mark.django_db
class TestAuth:
    def test_anonymous_reads_allowed(self):
        InstrumentFactory(symbol="BTC-USD")
        r = APIClient().get("/api/instruments/")
        assert r.status_code == 200

    def test_token_endpoint(self, db):
        user = get_user_model().objects.create_user(username="alice", password="pw")
        Token.objects.create(user=user)
        r = APIClient().post(
            "/api/auth/token/",
            {"username": "alice", "password": "pw"},
            format="json",
        )
        assert r.status_code == 200
        assert "token" in r.json()
