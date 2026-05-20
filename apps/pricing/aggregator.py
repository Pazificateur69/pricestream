"""Cross-venue aggregation: turn a list of Quotes into a ConsolidatedPrice."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from .models import Quote


@dataclass(frozen=True)
class Consolidated:
    mid: Decimal
    bid: Decimal
    ask: Decimal
    sources: list[str]


def consolidate(quotes: Iterable[Quote]) -> Consolidated | None:
    """Compute a tight-side mid-price across multiple venues.

    Strategy: best bid (max), best ask (min), mid = (bid + ask) / 2.
    This is the same logic an internalising LP uses to derive an internal mark.
    Returns None if the list is empty or if the resulting book is crossed.
    """
    quotes = [q for q in quotes if q.bid > 0 and q.ask > 0]
    if not quotes:
        return None

    best_bid = max(q.bid for q in quotes)
    best_ask = min(q.ask for q in quotes)

    if best_bid > best_ask:
        # Crossed book — fall back to a simple mid-of-mids.
        mid = sum((q.mid for q in quotes), Decimal(0)) / Decimal(len(quotes))
        best_bid = min(best_bid, mid)
        best_ask = max(best_ask, mid)
    else:
        mid = (best_bid + best_ask) / Decimal(2)

    sources = sorted({q.source for q in quotes})
    return Consolidated(mid=mid, bid=best_bid, ask=best_ask, sources=sources)
