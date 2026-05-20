from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .models import ConsolidatedPrice, Instrument, OHLCBar, Quote
from .serializers import (
    ConsolidatedPriceSerializer,
    InstrumentSerializer,
    OHLCBarSerializer,
    QuoteSerializer,
)


class InstrumentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Instrument.objects.all()
    serializer_class = InstrumentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_fields = ("is_active",)
    ordering_fields = ("symbol", "created_at")


class QuoteViewSet(viewsets.ReadOnlyModelViewSet):
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
