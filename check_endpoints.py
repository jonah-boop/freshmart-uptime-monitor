#!/usr/bin/env python3
from __future__ import annotations
import json, time, urllib.error, urllib.request

CHECKS = [
    {"name":"Main storefront","url":"https://freshmart.com.ng/","content_type":"text/html","contains":"Fresh Mart"},
    {"name":"Shop health API","url":"https://shop.freshmart.com.ng/store/health","content_type":"application/json","contains":"\"status\":\"ok\""},
    {"name":"Admin entry","url":"https://admin.freshmart.com.ng/admin","content_type":"text/html","contains":"Fresh Mart"},
]


def check(spec):
    try:
        req=urllib.request.Request(spec["url"],headers={"User-Agent":"FreshMart-External-Uptime/1.0","Accept":"*/*"})
        with urllib.request.urlopen(req,timeout=20) as r:
            body=r.read(200000).decode("utf-8",errors="replace")
            ctype=r.headers.get_content_type()
            ok=r.status==200 and ctype==spec["content_type"] and spec["contains"] in body
            return {"name":spec["name"],"url":spec["url"],"ok":ok,"status":r.status,"content_type":ctype,"detail":"expected marker present" if ok else "status/type/content contract mismatch"}
    except urllib.error.HTTPError as e:
        return {"name":spec["name"],"url":spec["url"],"ok":False,"status":e.code,"detail":f"HTTP {e.code}"}
    except Exception as e:
        return {"name":spec["name"],"url":spec["url"],"ok":False,"status":0,"detail":f"{type(e).__name__}: {e}"}

attempts=[]
for attempt in range(1,4):
    results=[check(spec) for spec in CHECKS]
    attempts.append({"attempt":attempt,"results":results})
    if all(r["ok"] for r in results): break
    if attempt<3: time.sleep(30)
final=attempts[-1]["results"]
print(json.dumps({"healthy":all(r["ok"] for r in final),"attempts":attempts},indent=2))
