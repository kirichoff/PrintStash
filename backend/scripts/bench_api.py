#!/usr/bin/env python3
"""Benchmark PrintStash API endpoints to catch performance regressions.

Times a curated set of read endpoints plus auto-discovered file-serving
endpoints (`/files/{id}/stl|download|thumbnail`) — the class that hid the
~26s STL streaming bug. For each endpoint it reports latency percentiles and
throughput, then flags two failure modes:

  * SLOW  — median total time over --slow-ms (default 1000ms)
  * SLOW-IO — a body over 1 MB served below --min-mbps (default 20 MB/s),
              which is the low-throughput signature of inefficient streaming
              even when the absolute time looks fine on a small file.

Exits non-zero if anything is flagged, so it doubles as a manual gate.

Usage (against the running stack):

    cd backend
    uv run python scripts/bench_api.py --username admin --password admin1234

    # more samples, stricter threshold, JSON for diffing across runs
    uv run python scripts/bench_api.py -u admin -p admin1234 \\
        --runs 10 --slow-ms 500 --json > bench.json

    # add ad-hoc paths on top of the defaults
    uv run python scripts/bench_api.py -u admin -p admin1234 \\
        --endpoint /api/v1/models/stats --endpoint /api/v1/models/trash
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field

import httpx

# Read endpoints worth tracking that take no path params. Detail and
# file-serving endpoints are discovered at runtime from /models.
DEFAULT_PATHS: list[str] = [
    "/api/v1/health",
    "/api/v1/auth/me",
    "/api/v1/models",
    "/api/v1/models/stats",
    "/api/v1/models/trash",
    "/api/v1/collections",
    "/api/v1/tags",
    "/api/v1/printers",
    "/api/v1/filament-profiles",
    "/api/v1/printer-profiles",
]

# file_type values that the viewer fetches via the on-the-fly STL endpoint.
MESH_TYPES = {"stl", "three_mf", "3mf", "obj", "step", "stp"}

MB = 1024 * 1024


@dataclass
class Sample:
    path: str
    status: int
    ttfb_ms: float
    total_ms: float
    size_bytes: int


@dataclass
class Result:
    path: str
    status: int
    size_bytes: int
    totals_ms: list[float] = field(default_factory=list)
    ttfbs_ms: list[float] = field(default_factory=list)
    error: str | None = None

    @property
    def median_ms(self) -> float:
        return statistics.median(self.totals_ms) if self.totals_ms else 0.0

    @property
    def p95_ms(self) -> float:
        if not self.totals_ms:
            return 0.0
        ordered = sorted(self.totals_ms)
        idx = max(0, int(round(0.95 * (len(ordered) - 1))))
        return ordered[idx]

    @property
    def min_ms(self) -> float:
        return min(self.totals_ms) if self.totals_ms else 0.0

    @property
    def median_ttfb_ms(self) -> float:
        return statistics.median(self.ttfbs_ms) if self.ttfbs_ms else 0.0

    @property
    def mbps(self) -> float:
        # Throughput at the median latency, in MB/s.
        if self.median_ms <= 0 or self.size_bytes <= 0:
            return 0.0
        return (self.size_bytes / MB) / (self.median_ms / 1000.0)


def login(client: httpx.Client, base_url: str, username: str, password: str) -> str:
    resp = client.post(
        f"{base_url}/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise SystemExit("login succeeded but no access_token in response")
    return token


def measure(client: httpx.Client, url: str, path: str) -> Sample:
    """One request, streamed so we capture time-to-first-byte and full size."""
    start = time.perf_counter()
    ttfb = 0.0
    size = 0
    with client.stream("GET", url) as resp:
        first = True
        for chunk in resp.iter_bytes():
            if first:
                ttfb = (time.perf_counter() - start) * 1000.0
                first = False
            size += len(chunk)
        if first:  # empty body — ttfb is the header time
            ttfb = (time.perf_counter() - start) * 1000.0
        status = resp.status_code
    total = (time.perf_counter() - start) * 1000.0
    return Sample(path=path, status=status, ttfb_ms=ttfb, total_ms=total, size_bytes=size)


def discover_file_paths(
    client: httpx.Client, base_url: str, token: str, max_models: int
) -> list[str]:
    """Pull a few models and turn their files into viewer-equivalent paths."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        models = client.get(
            f"{base_url}/api/v1/models", headers=headers, params={"limit": max_models}
        ).json()
    except Exception as exc:  # pragma: no cover - discovery is best-effort
        print(f"  (model discovery failed: {exc})", file=sys.stderr)
        return []
    if not isinstance(models, list):
        models = models.get("items", [])

    paths: list[str] = []
    seen: set[str] = set()
    for model in models[:max_models]:
        mid = model.get("id")
        if mid is not None:
            paths.append(f"/api/v1/models/{mid}")
        try:
            detail = client.get(
                f"{base_url}/api/v1/models/{mid}", headers=headers
            ).json()
        except Exception:
            continue
        for f in detail.get("files", []):
            fid = f.get("id")
            ftype = (f.get("file_type") or "").lower()
            if fid is None:
                continue
            candidates: list[str]
            if ftype in MESH_TYPES:
                # Meshes flow through the on-the-fly STL endpoint and always
                # have a thumbnail — probe both.
                candidates = [f"/api/v1/files/{fid}/stl", f"/api/v1/files/{fid}/thumbnail"]
            else:
                # G-code (and anything else) is fetched raw; thumbnails are
                # often absent, so don't probe them and flag spurious 404s.
                candidates = [f"/api/v1/files/{fid}/download"]
            for p in candidates:
                if p not in seen:
                    seen.add(p)
                    paths.append(p)
    return paths


def human_size(n: int) -> str:
    if n >= MB:
        return f"{n / MB:.1f}MB"
    if n >= 1024:
        return f"{n / 1024:.0f}KB"
    return f"{n}B"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("-u", "--username")
    ap.add_argument("-p", "--password")
    ap.add_argument("--token", help="use an existing bearer token instead of logging in")
    ap.add_argument("--runs", type=int, default=5, help="measured requests per endpoint")
    ap.add_argument("--warmup", type=int, default=1, help="unmeasured requests first")
    ap.add_argument("--slow-ms", type=float, default=1000.0, help="median latency budget")
    ap.add_argument(
        "--min-mbps",
        type=float,
        default=20.0,
        help="min throughput for bodies >1MB before flagging SLOW-IO",
    )
    ap.add_argument("--discover-models", type=int, default=5, help="models to expand into file endpoints (0 to skip)")
    ap.add_argument("--endpoint", action="append", default=[], dest="extra", help="extra path to measure (repeatable)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    client = httpx.Client(timeout=120.0, follow_redirects=True)

    token = args.token
    if not token:
        if not (args.username and args.password):
            ap.error("provide --token, or --username and --password")
        token = login(client, base, args.username, args.password)
    client.headers["Authorization"] = f"Bearer {token}"

    paths = list(DEFAULT_PATHS)
    if args.discover_models > 0:
        paths += discover_file_paths(client, base, token, args.discover_models)
    paths += args.extra
    # De-dup while preserving order.
    paths = list(dict.fromkeys(paths))

    results: list[Result] = []
    for path in paths:
        url = f"{base}{path}"
        try:
            for _ in range(max(0, args.warmup)):
                measure(client, url, path)
            res = Result(path=path, status=0, size_bytes=0)
            for _ in range(max(1, args.runs)):
                s = measure(client, url, path)
                res.status = s.status
                res.size_bytes = s.size_bytes
                res.totals_ms.append(s.total_ms)
                res.ttfbs_ms.append(s.ttfb_ms)
        except Exception as exc:
            res = Result(path=path, status=0, size_bytes=0, error=str(exc))
        results.append(res)

    results.sort(key=lambda r: r.median_ms, reverse=True)

    def flags(r: Result) -> list[str]:
        out = []
        if r.error or not (200 <= r.status < 400):
            out.append("ERR")
        if r.median_ms > args.slow_ms:
            out.append("SLOW")
        if r.size_bytes > MB and 0 < r.mbps < args.min_mbps:
            out.append("SLOW-IO")
        return out

    if args.json:
        print(json.dumps(
            [
                {
                    "path": r.path,
                    "status": r.status,
                    "size_bytes": r.size_bytes,
                    "median_ms": round(r.median_ms, 2),
                    "p95_ms": round(r.p95_ms, 2),
                    "min_ms": round(r.min_ms, 2),
                    "ttfb_ms": round(r.median_ttfb_ms, 2),
                    "mbps": round(r.mbps, 2),
                    "flags": flags(r),
                    "error": r.error,
                }
                for r in results
            ],
            indent=2,
        ))
    else:
        print(f"\nPrintStash API benchmark — {base}  ({args.runs} runs, warmup {args.warmup})\n")
        header = f"{'median':>9} {'p95':>9} {'ttfb':>8} {'size':>8} {'MB/s':>7}  {'st':>3}  path"
        print(header)
        print("-" * len(header))
        any_flag = False
        for r in results:
            fl = flags(r)
            if fl:
                any_flag = True
            tag = (" <- " + ",".join(fl)) if fl else ""
            if r.error:
                print(f"{'-':>9} {'-':>9} {'-':>8} {'-':>8} {'-':>7}  {'-':>3}  {r.path}  ERR: {r.error}")
                continue
            print(
                f"{r.median_ms:>8.1f}m {r.p95_ms:>8.1f}m {r.median_ttfb_ms:>7.1f}m "
                f"{human_size(r.size_bytes):>8} {r.mbps:>7.1f}  {r.status:>3}  {r.path}{tag}"
            )
        print()
        if any_flag:
            print("FLAGGED endpoints above. SLOW = over latency budget; "
                  "SLOW-IO = large body served below throughput floor; ERR = bad status.\n")

    return 1 if any(flags(r) for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
