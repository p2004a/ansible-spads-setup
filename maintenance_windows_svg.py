#!/usr/bin/env python3
"""Renders the weekly maintenance windows of hosts as SVG.

  ./maintenance_windows_svg.py > maintenance_windows.svg

Hosts are grouped by region (from host name, e.g. eu4 is in EU). Background
of regions shows low activity hours from maintenance_windows_load.dzn, hosts
rows show
maintenance windows from host_vars at their worst case length: SPADS stop
timeout (TimeoutStopSec of spads.service), which waits for ongoing games.
Labels show spads_maxInstances of hosts and their sum per region, region
and TOTAL rows plot the capacity up (not in maintenance) over the week.
"""

import argparse
import glob
import pathlib
import re
from collections import defaultdict

import yaml

ROOT = pathlib.Path(__file__).parent
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
# Shown hours from Monday, weekends are excluded from maintenance.
SPAN = 5 * 24
# (max load %, fill) of the low activity levels, from the quietest.
LOW_LEVELS = [(25, "#c3e6cb"), (40, "#dcf1e0"), (55, "#eef8f0")]
DOWN_FILL, LINE = "#e8590c", "#1c64b4"

HOUR_W, ROW_H, LABEL_W, TOP = 16, 16, 150, 20
PLOT_H, PLOT_TOP_PAD, PLOT_BOTTOM_PAD = 52, 18, 10


def spads_stop_hours():
    """TimeoutStopSec of spads.service in hours."""
    unit = (ROOT / "roles/spads/templates/spads.service.j2").read_text()
    return int(re.search(r"^TimeoutStopSec=(\d+)h$", unit, re.M).group(1))


def parse_window(spec):
    """Start hours of the week of an OnCalendar like 'Mon,Thu 04:00 UTC'."""
    days_spec, time_spec = spec.split()[:2]
    days = set()
    for part in days_spec.split(","):
        a, _, b = part.partition("..")
        days.update(range(DAYS.index(a), DAYS.index(b or a) + 1))
    h, m = time_spec.split(":")[:2]
    return [d * 24 + int(h) + int(m) / 60 for d in sorted(days)]


def load_profile(path):
    """region -> 24 hourly loads, from maintenance_windows_load.dzn."""
    try:
        text = pathlib.Path(path).read_text()
    except FileNotFoundError:
        return {}
    regions = re.search(r"REGION\s*=\s*\{([^}]*)\}", text).group(1).replace(" ", "").split(",")
    array = re.search(r"\[([^\]]*)\]", re.sub(r"%.*", "", text)).group(1)
    values = [int(v) for v in array.split(",")]
    return {r: values[i * 24:(i + 1) * 24] for i, r in enumerate(regions)}


def clock(hour):
    h, m = divmod(round(hour * 60) % (24 * 60), 60)
    return f"{h:02}:{m:02}" if m else f"{h:02}"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--glob", default="host_vars/*/vars.yaml")
    p.add_argument("--load", default="maintenance_windows_load.dzn")
    args = p.parse_args()
    length = spads_stop_hours()

    regions = defaultdict(dict)  # region -> host -> (capacity, starts)
    for path in sorted(glob.glob(args.glob)):
        host = pathlib.Path(path).parent.name
        m = re.fullmatch(r"([a-z]+)\d+", host)
        region = m.group(1).upper() if m else "OTHER"
        hv = yaml.safe_load(pathlib.Path(path).read_text()) or {}
        starts = [s for w in hv.get("maintenance_windows", []) for s in parse_window(w)]
        regions[region][host] = (hv.get("spads_maxInstances", 0), starts)
    load = load_profile(args.load)

    width = LABEL_W + SPAN * HOUR_W
    bg, out = [], []
    rect = lambda x, y, w, h, fill, to=out: to.append(f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" fill="{fill}"/>')
    text = lambda x, y, s, extra="": out.append(f'<text x="{x:g}" y="{y:g}"{extra}>{s}</text>')
    hx = lambda hour: LABEL_W + hour * HOUR_W

    def down_intervals(capacity, starts):
        """(begin, end, capacity) in maintenance, wrapping past Sunday to Monday, clipped to SPAN."""
        for start in starts:
            for b, e in ((start, start + length), (start - 168, start + length - 168)):
                if min(e, SPAN) > max(b, 0):
                    yield max(b, 0), min(e, SPAN), capacity

    def low_activity(y, h, profile):
        """Low activity hours as background of the rows from y, h high."""
        fills = [next((f for limit, f in LOW_LEVELS if profile[i % 24] <= limit), None) for i in range(SPAN)]
        start = 0
        for hour in range(1, SPAN + 1):
            if hour == SPAN or fills[hour] != fills[start]:
                if fills[start]:
                    rect(hx(start), y, (hour - start) * HOUR_W, h, fills[start], bg)
                start = hour

    def capacity_plot(y, label, total, intervals):
        """Row with line of capacity up (not in maintenance) over time."""
        times = sorted({0, SPAN} | {t for b, e, _ in intervals for t in (b, e)})
        steps = [(t0, t1, total - sum(c for b, e, c in intervals if b <= t0 < e)) for t0, t1 in zip(times, times[1:])]
        low = min(v for _, _, v in steps)
        # Line spans from full capacity at the top to 0 at the bottom, with padding.
        top, bottom = y + PLOT_TOP_PAD, y + PLOT_H - PLOT_BOTTOM_PAD
        vy = lambda v: bottom - v / total * (bottom - top)
        d = "".join(f"{'L' if i else 'M'}{hx(t0):g} {vy(v):g}L{hx(t1):g} {vy(v):g}" for i, (t0, t1, v) in enumerate(steps))
        out.append(f'<path d="{d}" fill="none" stroke="{LINE}" stroke-width="1.5"/>')
        text(hx(0) + 3, top - 3, "capacity", f' font-size="9" fill="{LINE}"')
        for t0, t1, v in steps:
            # Short steps between other ones would overlap labels, except the lowest.
            if v < total and ((t1 - t0) * HOUR_W >= 24 or v == low):
                below = vy(v) + 10 <= y + PLOT_H - 1
                text(hx((t0 + t1) / 2), vy(v) + 10 if below else vy(v) - 3, v,
                     f' text-anchor="middle" font-size="9" font-weight="bold" fill="{LINE}"')
        text(4, y + 13, label, ' font-weight="bold"')
        text(LABEL_W - 6, y + 13, total, ' text-anchor="end" font-weight="bold"')
        text(LABEL_W - 6, y + 26, f"min capacity {low} ({low / total:.0%})", ' text-anchor="end" font-size="9" fill="#666"')
        return y + PLOT_H

    text(4, 14, "All times in UTC", ' font-weight="bold"')
    text(LABEL_W - 6, 14, "capacity", ' text-anchor="end" font-size="9" fill="#666"')
    y = TOP
    all_intervals = []
    for region in sorted(regions):
        hosts = regions[region]
        if profile := load.get(region):
            low_activity(y, PLOT_H + len(hosts) * ROW_H, profile)
        intervals = [i for c, starts in hosts.values() for i in down_intervals(c, starts)]
        all_intervals += intervals
        y = capacity_plot(y, region, sum(c for c, _ in hosts.values()), intervals)
        for host, (capacity, starts) in hosts.items():
            text(14, y + ROW_H - 4, host)
            text(LABEL_W - 6, y + ROW_H - 4, capacity, ' text-anchor="end"')
            for b, e, _ in down_intervals(capacity, starts):
                rect(hx(b), y + 2, (e - b) * HOUR_W, ROW_H - 4, DOWN_FILL)
            for start in (s for s in starts if s < SPAN):
                text(hx((start + length / 2) % 168), y + ROW_H - 5, f"{clock(start)}–{clock(start + length)}",
                     ' text-anchor="middle" font-size="8" fill="#fff"')
            y += ROW_H
        out.append(f'<path d="M0 {y}H{width}" stroke="#ccc"/>')
    y = capacity_plot(y, "TOTAL", sum(c for h in regions.values() for c, _ in h.values()), all_intervals)
    out.append(f'<path d="M0 {y}H{width}" stroke="#ccc"/>')

    grid = []
    for d, name in enumerate(DAYS[:SPAN // 24]):
        x = hx(d * 24)
        grid.append(f'<text x="{x + 12 * HOUR_W:g}" y="14" text-anchor="middle">{name} (UTC)</text>')
        grid.append(f'<path d="M{x} {TOP}V{y}" stroke="#999"/>')
        grid += [f'<path d="M{x + h * HOUR_W} {TOP}V{y}" stroke="#0000000f"/>' for h in (6, 12, 18)]

    x = LABEL_W
    out.append(f'<path d="M{x} {y + 13}h10" stroke="{LINE}" stroke-width="1.5"/>')
    legend = [(None, "capacity up, not in maintenance"),
              (DOWN_FILL, f"maintenance, labeled start–end hour in UTC, up to {length}h (SPADS stop timeout)")]
    legend += [(f, f"load ≤ {limit}% of peak") for limit, f in LOW_LEVELS]
    for fill, label in legend:
        if fill:
            rect(x, y + 8, 10, 10, fill)
        text(x + 14, y + 17, label)
        x += 30 + 6 * len(label)

    print(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{y + 24}" '
          f'font-family="sans-serif" font-size="11"><rect width="100%" height="100%" fill="#fff"/>')
    # Low activity background first, then grid, then everything else.
    print("\n".join(bg + grid + out))
    print("</svg>")


if __name__ == "__main__":
    main()
