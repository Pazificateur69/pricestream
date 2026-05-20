"""Cross-venue aggregation: turn a list of Quotes into a ConsolidatedPrice.

Two responsibilities:

1. `consolidate(quotes)` -> a single mid/bid/ask snapshot.
2. `detect_arbitrage(quotes)` -> any cross-venue arbitrage opportunity present.

Both functions accept any iterable of Quote-like objects (must expose `bid`,
`ask`, `source` and `timestamp`).
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone

if TYPE_CHECKING:
    from .models import Quote


@dataclass(frozen=True)
class Consolidated:
    mid: Decimal
    bid: Decimal
    ask: Decimal
    sources: list[str]


@dataclass(frozen=True)
class Arbitrage:
    buy_venue: str
    buy_price: Decimal
    sell_venue: str
    sell_price: Decimal
    spread: Decimal
    spread_bps: Decimal


def _is_fresh(quote, max_age: float) -> bool:
    age = (timezone.now() - quote.timestamp).total_seconds()
    return age <= max_age


def consolidate(quotes: Iterable[Quote]) -> Consolidated | None:
    """Compute a tight-side mid-price across multiple venues.

    Strategy: best bid (max), best ask (min), mid = (bid + ask) / 2.
    Quotes older than `settings.MAX_QUOTE_AGE_SECONDS` are dropped (staleness
    gate). If the resulting book is crossed (same venue glitching, or stale
    feed), we fall back to a mid-of-mids so the consolidated tape never gaps.
    """
    max_age = getattr(settings, "MAX_QUOTE_AGE_SECONDS", 30)
    candidates = [
        q for q in quotes if q.bid > 0 and q.ask > 0 and _is_fresh(q, max_age)
    ]
    if not candidates:
        return None

    best_bid = max(q.bid for q in candidates)
    best_ask = min(q.ask for q in candidates)

    if best_bid > best_ask:
        mid = sum((q.mid for q in candidates), Decimal(0)) / Decimal(len(candidates))
        best_bid = min(best_bid, mid)
        best_ask = max(best_ask, mid)
    else:
        mid = (best_bid + best_ask) / Decimal(2)

    sources = sorted({q.source for q in candidates})
    return Consolidated(mid=mid, bid=best_bid, ask=best_ask, sources=sources)


def detect_arbitrage(quotes: Iterable[Quote]) -> Arbitrage | None:
    """Return the largest cross-venue arbitrage opportunity, if any.

    An opportunity exists when `bid_on_venue_A > ask_on_venue_B` with A != B:
    you buy at venue B's ask and immediately sell at venue A's bid for a
    risk-free spread (ignoring fees, latency, withdrawal costs).
    """
    qs = [q for q in quotes if q.bid > 0 and q.ask > 0]
    if len(qs) < 2:
        return None

    best = None
    for buy in qs:
        for sell in qs:
            if buy.source == sell.source:
                continue
            # Buy on `buy.source` at its ask; sell on `sell.source` at its bid.
            spread = sell.bid - buy.ask
            if spread <= 0:
                continue
            mid = (buy.ask + sell.bid) / Decimal(2)
            spread_bps = (spread / mid) * Decimal(10000)
            arb = Arbitrage(
                buy_venue=buy.source,
                buy_price=buy.ask,
                sell_venue=sell.source,
                sell_price=sell.bid,
                spread=spread,
                spread_bps=spread_bps,
            )
            if best is None or arb.spread > best.spread:
                best = arb
    return best
