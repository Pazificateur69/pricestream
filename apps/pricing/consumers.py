"""Django Channels consumer streaming live mid-prices."""
from __future__ import annotations

import json

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.cache import cache


class QuoteConsumer(AsyncJsonWebsocketConsumer):
    """Subscribe to consolidated mid-price updates for a single instrument.

    URL pattern: `/ws/quotes/<symbol>/`. On connect we send the last cached
    snapshot so the client gets immediate data without waiting for the next tick.
    """

    async def connect(self) -> None:
        self.symbol = self.scope["url_route"]["kwargs"]["symbol"].upper()
        self.group = f"quotes.{self.symbol}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

        snapshot = cache.get(f"pricestream:mid:{self.symbol}")
        if snapshot:
            await self.send(text_data=json.dumps({"instrument": self.symbol, **snapshot}))

    async def disconnect(self, code) -> None:
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def quote_update(self, event) -> None:
        await self.send(text_data=json.dumps(event["payload"]))
