from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ArbitrageOpportunity, ConsolidatedPrice, Instrument, OHLCBar, Quote
from .serializers import (
    ArbitrageOpportunitySerializer,
    ConsolidatedPriceSerializer,
    InstrumentSerializer,
    OHLCBarSerializer,
    QuoteSerializer,
)
from .stats import compute_rolling_stats


class InstrumentViewSet(viewsets.ReadOnlyModelViewSet):
    """List supported instruments and their metadata."""

    queryset = Instrument.objects.all()
    serializer_class = InstrumentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_fields = ("is_active",)
    ordering_fields = ("symbol", "created_at")


class QuoteViewSet(viewsets.ReadOnlyModelViewSet):
    """Historic raw quotes and the latest consolidated mid-price."""

    queryset = Quote.objects.select_related("instrument").all()
    serializer_class = QuoteSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_fields = ("source",)
    ordering_fields = ("timestamp",)

    def get_queryset(self):
        qs = super().get_queryset()
        symbol = self.request.query_params.get("instrument")
        if symbol:
            qs = qs.filter(instrument__symbol=symbol)
        return qs

    @action(detail=False, methods=["get"])
    def latest(self, request):
        """Return the latest consolidated mid-price for an instrument."""
        symbol = request.query_params.get("instrument")
        if not symbol:
            return Response({"detail": "instrument query param required."}, status=400)
        instrument = get_object_or_404(Instrument, symbol=symbol)
        latest = (
            ConsolidatedPrice.objects.filter(instrument=instrument)
            .order_by("-timestamp")
            .first()
        )
        if not latest:
            return Response({"detail": "no consolidated price yet."}, status=404)
        return Response(ConsolidatedPriceSerializer(latest).data)


class OHLCViewSet(viewsets.ReadOnlyModelViewSet):
    """OHLC bars built by the Kafka consumer."""

    queryset = OHLCBar.objects.select_related("instrument").all()
    serializer_class = OHLCBarSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_fields = ("interval",)
    ordering_fields = ("bucket_start",)

    def get_queryset(self):
        qs = super().get_queryset()
        symbol = self.request.query_params.get("instrument")
        interval = self.request.query_params.get("interval")
        if symbol:
            qs = qs.filter(instrument__symbol=symbol)
        if interval:
            qs = qs.filter(interval=interval)
        return qs


class ArbitrageOpportunityViewSet(viewsets.ReadOnlyModelViewSet):
    """Detected cross-venue arbitrage opportunities."""

    queryset = ArbitrageOpportunity.objects.select_related("instrument").all()
    serializer_class = ArbitrageOpportunitySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_fields = ("buy_venue", "sell_venue")
    ordering_fields = ("timestamp", "spread_bps")

    def get_queryset(self):
        qs = super().get_queryset()
        symbol = self.request.query_params.get("instrument")
        if symbol:
            qs = qs.filter(instrument__symbol=symbol)
        return qs


class RollingStatsView(APIView):
    """`GET /api/stats/?instrument=BTC-USD&window=300`

    Returns rolling stats over the last `window` seconds of consolidated prices:
    sample count, last/avg/min/max mid, mid stdev, and average spread in bps.
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        symbol = request.query_params.get("instrument")
        if not symbol:
            return Response({"detail": "instrument query param required."}, status=400)
        try:
            window = int(request.query_params.get("window", "300"))
        except ValueError:
            return Response({"detail": "window must be an integer."}, status=400)
        window = max(1, min(window, 86400))
        instrument = get_object_or_404(Instrument, symbol=symbol)
        return Response(compute_rolling_stats(instrument, window).as_dict())


@require_GET
def metrics_view(_request):
    """Prometheus scrape endpoint."""
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)


def dashboard(request):
    """A tiny dashboard that subscribes via WebSocket and ticks live."""
    instruments = list(Instrument.objects.filter(is_active=True).values_list("symbol", flat=True))
    return render(request, "pricing/dashboard.html", {"instruments": instruments})
