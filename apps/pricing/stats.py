"""Rolling analytics over the consolidated tape.

Given an instrument and a window size in seconds, returns descriptive stats
computed in-memory from `ConsolidatedPrice` rows. The implementation is
deliberately simple — the goal is to demonstrate that pricing telemetry is a
first-class concern of the service, not to compete with a TSDB.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from statistics import StatisticsError, pstdev

from django.utils import timezone

from .models import ConsolidatedPrice, Instrument


@dataclass(frozen=True)
class RollingStats:
    instrument: str
    window_seconds: int
    samples: int
    last_mid: Decimal | None
    avg_mid: Decimal | None
    min_mid: Decimal | None
    max_mid: Decimal | None
    mid_stdev: Decimal | None
    avg_spread_bps: Decimal | None

    def as_dict(self) -> dict:
        def to_str(x):
            return None if x is None else str(x)

        return {
            "instrument": self.instrument,
            "window_seconds": self.window_seconds,
            "samples": self.samples,
            "last_mid": to_str(self.last_mid),
            "avg_mid": to_str(self.avg_mid),
            "min_mid": to_str(self.min_mid),
            "max_mid": to_str(self.max_mid),
            "mid_stdev": to_str(self.mid_stdev),
            "avg_spread_bps": to_str(self.avg_spread_bps),
        }


def compute_rolling_stats(instrument: Instrument, window_seconds: int) -> RollingStats:
    """Compute descriptive stats over the last `window_seconds` of consolidated prices."""
    since = timezone.now() - timedelta(seconds=window_seconds)
    rows = list(
        ConsolidatedPrice.objects.filter(
            instrument=instrument, timestamp__gte=since
        ).order_by("timestamp")
    )

    if not rows:
        return RollingStats(
            instrument=instrument.symbol,
            window_seconds=window_seconds,
            samples=0,
            last_mid=None,
            avg_mid=None,
            min_mid=None,
            max_mid=None,
            mid_stdev=None,
            avg_spread_bps=None,
        )

    mids = [row.mid for row in rows]
    spreads_bps = []
    for row in rows:
        if row.mid > 0:
            spreads_bps.append((row.ask - row.bid) / row.mid * Decimal(10000))

    avg_mid = sum(mids, Decimal(0)) / Decimal(len(mids))
    try:
        stdev_value = Decimal(str(pstdev(float(m) for m in mids)))
    except StatisticsError:
        stdev_value = Decimal(0)

    avg_spread = (
        sum(spreads_bps, Decimal(0)) / Decimal(len(spreads_bps))
        if spreads_bps
        else None
    )

    return RollingStats(
        instrument=instrument.symbol,
        window_seconds=window_seconds,
        samples=len(rows),
        last_mid=mids[-1],
        avg_mid=avg_mid,
        min_mid=min(mids),
        max_mid=max(mids),
        mid_stdev=stdev_value,
        avg_spread_bps=avg_spread,
    )
