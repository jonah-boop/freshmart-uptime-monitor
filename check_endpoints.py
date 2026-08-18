#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

REQUIRED_FIELDS = ("name", "url", "content_type", "contains")


def load_checks(path):
    with open(path, encoding="utf-8") as config_file:
        checks = json.load(config_file)
    if not isinstance(checks, list) or not checks:
        raise ValueError("configuration must be a non-empty JSON list")
    for index, spec in enumerate(checks):
        if not isinstance(spec, dict):
            raise ValueError(f"endpoint {index} must be an object")
        for field in REQUIRED_FIELDS:
            if (
                field not in spec
                or not isinstance(spec[field], str)
                or not spec[field].strip()
            ):
                raise ValueError(
                    f"endpoint {index} field {field!r} must be a non-empty string"
                )
    return checks


def check(spec, opener=urllib.request.urlopen):
    try:
        req = urllib.request.Request(
            spec["url"],
            headers={"User-Agent": "FreshMart-External-Uptime/1.0", "Accept": "*/*"},
        )
        with opener(req, timeout=20) as r:
            body = r.read(200000).decode("utf-8", errors="replace")
            ctype = r.headers.get_content_type()
            ok = (
                r.status == 200
                and ctype == spec["content_type"]
                and spec["contains"] in body
            )
            return {
                "name": spec["name"],
                "url": spec["url"],
                "ok": ok,
                "status": r.status,
                "content_type": ctype,
                "detail": "expected marker present"
                if ok
                else "status/type/content contract mismatch",
            }
    except urllib.error.HTTPError as e:
        return {
            "name": spec["name"],
            "url": spec["url"],
            "ok": False,
            "status": e.code,
            "detail": f"HTTP {e.code}",
        }
    except Exception as e:
        return {
            "name": spec["name"],
            "url": spec["url"],
            "ok": False,
            "status": 0,
            "detail": f"{type(e).__name__}: {e}",
        }


def run_checks(checks, attempts=3, delay_seconds=30, checker=check, sleep=time.sleep):
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if delay_seconds < 0:
        raise ValueError("delay_seconds must be non-negative")
    history = []
    for attempt in range(1, attempts + 1):
        results = [checker(spec) for spec in checks]
        history.append({"attempt": attempt, "results": results})
        if all(result["ok"] for result in results):
            break
        if attempt < attempts:
            sleep(delay_seconds)
    final = history[-1]["results"]
    return {"healthy": all(result["ok"] for result in final), "attempts": history}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe configured HTTP endpoints and emit a JSON health report."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("endpoints.json"),
        help="endpoint configuration file (default: endpoints.json beside this script)",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=3,
        help="maximum probe attempts (default: 3)",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=30,
        help="delay between failed attempts (default: 30)",
    )
    args = parser.parse_args(argv)

    try:
        checks = load_checks(args.config)
        report = run_checks(
            checks,
            attempts=args.attempts,
            delay_seconds=args.delay_seconds,
        )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return 2

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
