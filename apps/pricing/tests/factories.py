from decimal import Decimal

import factory
from django.utils import timezone

from apps.pricing.models import ConsolidatedPrice, Instrument, OHLCBar, Quote


class InstrumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Instrument
        django_get_or_create = ("symbol",)

    symbol = "BTC-USD"
    base = "BTC"
    quote = "USD"
    is_active = True


class QuoteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Quote

    instrument = factory.SubFactory(InstrumentFactory)
    source = Quote.Source.BINANCE
    bid = Decimal("50000")
    ask = Decimal("50010")
    timestamp = factory.LazyFunction(timezone.now)


class ArbitrageOpportunityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "pricing.ArbitrageOpportunity"

    instrument = factory.SubFactory(InstrumentFactory)
    buy_venue = "binance"
    buy_price = Decimal("50000")
    sell_venue = "coinbase"
    sell_price = Decimal("50050")
    spread = Decimal("50")
    spread_bps = Decimal("10.0000")
    timestamp = factory.LazyFunction(timezone.now)


class ConsolidatedPriceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ConsolidatedPrice

    instrument = factory.SubFactory(InstrumentFactory)
    mid = Decimal("50005")
    bid = Decimal("50000")
    ask = Decimal("50010")
    sources = factory.LazyFunction(lambda: ["binance", "coinbase"])
    timestamp = factory.LazyFunction(timezone.now)


class OHLCBarFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OHLCBar

    instrument = factory.SubFactory(InstrumentFactory)
    interval = OHLCBar.Interval.M1
    bucket_start = factory.LazyFunction(timezone.now)
    open = Decimal("50000")
    high = Decimal("50100")
    low = Decimal("49900")
    close = Decimal("50050")
    volume = Decimal("0")
    tick_count = 1
