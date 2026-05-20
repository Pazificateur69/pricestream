from rest_framework.routers import DefaultRouter

from .views import InstrumentViewSet, OHLCViewSet, QuoteViewSet

router = DefaultRouter()
router.register(r"instruments", InstrumentViewSet, basename="instrument")
router.register(r"quotes", QuoteViewSet, basename="quote")
router.register(r"ohlc", OHLCViewSet, basename="ohlc")

urlpatterns = router.urls
