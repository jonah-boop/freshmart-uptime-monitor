#!/usr/bin/env python3
from __future__ import annotations
import json, time, urllib.error, urllib.request

CHECKS = [
    {"name":"Main storefront","url":"https://freshmart.com.ng/","content_type":"text/html","contains":"Fresh Mart"},
    {"name":"Shop health API","url":"https://shop.freshmart.com.ng/store/health","content_type":"application/json","contains":"\"status\":\"ok\""},
    {"name":"Admin entry","url":"https://admin.freshmart.com.ng/admin","content_type":"text/html","contains":"Fresh Mart"},
]


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
        req=urllib.request.Request(spec["url"],headers={"User-Agent":"FreshMart-External-Uptime/1.0","Accept":"*/*"})
        with opener(req,timeout=20) as r:
            body=r.read(200000).decode("utf-8",errors="replace")
            ctype=r.headers.get_content_type()
            ok=r.status==200 and ctype==spec["content_type"] and spec["contains"] in body
            return {"name":spec["name"],"url":spec["url"],"ok":ok,"status":r.status,"content_type":ctype,"detail":"expected marker present" if ok else "status/type/content contract mismatch"}
    except urllib.error.HTTPError as e:
        return {"name":spec["name"],"url":spec["url"],"ok":False,"status":e.code,"detail":f"HTTP {e.code}"}
    except Exception as e:
        return {"name":spec["name"],"url":spec["url"],"ok":False,"status":0,"detail":f"{type(e).__name__}: {e}"}

def main() -> int:
    attempts = []
    for attempt in range(1, 4):
        results = [check(spec) for spec in CHECKS]
        attempts.append({"attempt": attempt, "results": results})
        if all(result["ok"] for result in results):
            break
        if attempt < 3:
            time.sleep(30)
    final = attempts[-1]["results"]
    print(
        json.dumps(
            {
                "healthy": all(result["ok"] for result in final),
                "attempts": attempts,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
