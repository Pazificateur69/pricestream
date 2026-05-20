from decimal import Decimal
from unittest.mock import MagicMock, patch

from apps.pricing.exchanges import BinanceClient, CoinbaseClient, KrakenClient


def _fake_response(payload):
    r = MagicMock()
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


class TestBinanceClient:
    def test_symbol_translation(self):
        assert BinanceClient._to_binance_symbol("BTC-USD") == "BTCUSDT"
        assert BinanceClient._to_binance_symbol("ETH-USDT") == "ETHUSDT"

    def test_fetch_parses_response(self):
        with patch(
            "apps.pricing.exchanges._session.get",
            return_value=_fake_response({"bidPrice": "50000.5", "askPrice": "50001.2"}),
        ):
            bid, ask = BinanceClient().fetch("BTC-USD")
        assert bid == Decimal("50000.5")
        assert ask == Decimal("50001.2")

    def test_fetch_returns_none_on_error(self):
        with patch("apps.pricing.exchanges._session.get", side_effect=Exception("boom")):
            assert BinanceClient().fetch("BTC-USD") is None


class TestCoinbaseClient:
    def test_fetch_parses_top_of_book(self):
        with patch(
            "apps.pricing.exchanges._session.get",
            return_value=_fake_response(
                {"bids": [["50000.0", "1.0", 1]], "asks": [["50001.0", "1.0", 1]]}
            ),
        ):
            bid, ask = CoinbaseClient().fetch("BTC-USD")
        assert bid == Decimal("50000.0")
        assert ask == Decimal("50001.0")


class TestKrakenClient:
    def test_symbol_translation_btc_to_xbt(self):
        assert KrakenClient._to_kraken_symbol("BTC-USD") == "XBTUSD"

    def test_fetch_parses_response(self):
        payload = {
            "error": [],
            "result": {"XXBTZUSD": {"b": ["50000.0", "1", "1"], "a": ["50001.0", "1", "1"]}},
        }
        with patch("apps.pricing.exchanges._session.get", return_value=_fake_response(payload)):
            bid, ask = KrakenClient().fetch("BTC-USD")
        assert bid == Decimal("50000.0")
        assert ask == Decimal("50001.0")

    def test_fetch_returns_none_on_error_payload(self):
        with patch(
            "apps.pricing.exchanges._session.get",
            return_value=_fake_response({"error": ["bad pair"], "result": {}}),
        ):
            assert KrakenClient().fetch("BTC-USD") is None
