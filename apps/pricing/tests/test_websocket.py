import pytest
from channels.testing import WebsocketCommunicator
from django.core.cache import cache

from pricestream.asgi import application


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_websocket_sends_cached_snapshot_on_connect():
    cache.set(
        "pricestream:mid:BTC-USD",
        {
            "mid": "50000",
            "bid": "49999",
            "ask": "50001",
            "sources": ["binance", "coinbase"],
            "ts": "2026-01-01T12:00:00+00:00",
        },
        timeout=60,
    )
    communicator = WebsocketCommunicator(application, "/ws/quotes/BTC-USD/")
    connected, _ = await communicator.connect()
    assert connected

    message = await communicator.receive_json_from()
    assert message["instrument"] == "BTC-USD"
    assert message["mid"] == "50000"
    assert message["sources"] == ["binance", "coinbase"]

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_websocket_broadcast_via_group():
    from channels.layers import get_channel_layer

    communicator = WebsocketCommunicator(application, "/ws/quotes/ETH-USD/")
    connected, _ = await communicator.connect()
    assert connected

    layer = get_channel_layer()
    await layer.group_send(
        "quotes.ETH-USD",
        {
            "type": "quote.update",
            "payload": {
                "instrument": "ETH-USD",
                "mid": "3000",
                "bid": "2999",
                "ask": "3001",
                "sources": ["binance"],
                "ts": "2026-01-01T12:00:00+00:00",
            },
        },
    )

    msg = await communicator.receive_json_from()
    assert msg["instrument"] == "ETH-USD"
    assert msg["mid"] == "3000"

    await communicator.disconnect()
