from django.contrib import admin

from .models import ConsolidatedPrice, Instrument, OHLCBar, Quote


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ("symbol", "base", "quote", "is_active", "created_at")
    search_fields = ("symbol",)
    list_filter = ("is_active",)


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ("instrument", "source", "bid", "ask", "timestamp")
    list_filter = ("source", "instrument")
    date_hierarchy = "timestamp"


@admin.register(ConsolidatedPrice)
class ConsolidatedPriceAdmin(admin.ModelAdmin):
    list_display = ("instrument", "mid", "bid", "ask", "timestamp")
    list_filter = ("instrument",)
    date_hierarchy = "timestamp"


@admin.register(OHLCBar)
class OHLCBarAdmin(admin.ModelAdmin):
    list_display = (
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
    list_filter = ("interval", "instrument")
    date_hierarchy = "bucket_start"
