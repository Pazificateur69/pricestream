from rest_framework import serializers

from .models import ConsolidatedPrice, Instrument, OHLCBar, Quote


class InstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instrument
        fields = ("id", "symbol", "base", "quote", "is_active", "created_at")


class QuoteSerializer(serializers.ModelSerializer):
    instrument = serializers.SlugRelatedField(slug_field="symbol", read_only=True)
    mid = serializers.DecimalField(max_digits=24, decimal_places=10, read_only=True)

    class Meta:
        model = Quote
        fields = ("id", "instrument", "source", "bid", "ask", "mid", "timestamp")


class ConsolidatedPriceSerializer(serializers.ModelSerializer):
    instrument = serializers.SlugRelatedField(slug_field="symbol", read_only=True)

    class Meta:
        model = ConsolidatedPrice
        fields = ("id", "instrument", "mid", "bid", "ask", "sources", "timestamp")


class OHLCBarSerializer(serializers.ModelSerializer):
    instrument = serializers.SlugRelatedField(slug_field="symbol", read_only=True)

    class Meta:
        model = OHLCBar
        fields = (
            "id",
            "instrument",
            "interval",
            "bucket_start",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "tick_count",
        )
