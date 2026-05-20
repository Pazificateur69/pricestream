from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ArbitrageOpportunityViewSet,
    InstrumentViewSet,
    OHLCViewSet,
    QuoteViewSet,
    RollingStatsView,
)

router = DefaultRouter()
router.register(r"instruments", InstrumentViewSet, basename="instrument")
router.register(r"quotes", QuoteViewSet, basename="quote")
router.register(r"ohlc", OHLCViewSet, basename="ohlc")
router.register(r"arbitrage", ArbitrageOpportunityViewSet, basename="arbitrage")

urlpatterns = [
    path("stats/", RollingStatsView.as_view(), name="rolling-stats"),
    *router.urls,
]
