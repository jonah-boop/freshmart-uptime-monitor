# Fresh Mart External Uptime Monitor

A dependency-free HTTP monitor that runs on GitHub-hosted infrastructure and opens a deduplicated incident when a configured endpoint fails repeatedly.

Fresh Mart uses it to check public services independently of its VPS. The code is reusable; deployment-specific endpoints live in [`endpoints.json`](endpoints.json).

## How it works

1. GitHub Actions starts the monitor every five minutes.
2. `check_endpoints.py` loads and validates `endpoints.json`.
3. Each endpoint must return HTTP 200, the configured content type, and the configured body marker.
4. A failed run makes up to three attempts, waiting 30 seconds between attempts.
5. A confirmed failure opens one `uptime-incident` GitHub issue and sends one Telegram alert.
6. A later healthy run closes the issue and sends one recovery message.

The open issue is the incident state, so repeated failing runs do not send duplicate alerts.

## Requirements

- Python 3.11 or 3.12
- A GitHub repository with Actions enabled
- Telegram credentials only if you use the included notification workflow

The monitor uses only the Python standard library.

## Configure endpoints

`endpoints.json` must contain a non-empty list. Every endpoint requires four non-empty string fields:

```json
[
  {
    "name": "Example health API",
    "url": "https://example.com/health",
    "content_type": "application/json",
    "contains": "\"status\":\"ok\""
  }
]
```

| Field | Purpose |
| --- | --- |
| `name` | Human-readable service name |
| `url` | Endpoint URL to probe; use public HTTPS in shared workflow repositories |
| `content_type` | Exact media type expected from the response |
| `contains` | Text marker that must appear in the first 200,000 response bytes |

Keep credentials, signed URLs, and private network addresses out of this public file. Configuration validation checks the JSON shape and required strings; it does not enforce the URL scheme or destination. Treat `endpoints.json` as trusted workflow configuration and review every URL change before merge.

## Run locally

Use production defaults:

```bash
python3 check_endpoints.py
```

Use a custom configuration or a faster local retry policy:

```bash
python3 check_endpoints.py \
  --config endpoints.json \
  --attempts 1 \
  --delay-seconds 0
```

The command prints a JSON report with two stable top-level keys:

```json
{
  "healthy": true,
  "attempts": []
}
```

The `attempts` array contains each probe result. Endpoint failures are returned as structured data instead of uncaught network exceptions.

## Test

The unit suite uses fake HTTP responses and fake sleep functions. It makes no live network requests.

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile check_endpoints.py
python3 -m json.tool endpoints.json >/dev/null
```

GitHub Actions runs the same checks on Python 3.11 and 3.12 for pushes and pull requests.

## Enable Telegram incident alerts

Add these GitHub Actions repository secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

The workflow reads them only at runtime. Never add either value to code, JSON, logs, issues, or pull requests.

Run **Test external Telegram delivery** manually after adding the secrets. The normal uptime workflow requires `issues: write` so it can reconcile incident state; CI uses `contents: read` only.

## Files

- `check_endpoints.py`: configuration validation, HTTP probes, retry policy, and CLI
- `endpoints.json`: deployment-specific public endpoint contracts
- `tests/test_check_endpoints.py`: network-free unit tests
- `.github/workflows/uptime.yml`: scheduled checks, incident reconciliation, and notifications
- `.github/workflows/test-notification.yml`: manual Telegram delivery test
- `.github/workflows/keepalive.yml`: monthly activity that prevents GitHub from disabling an inactive schedule
- `.github/workflows/ci.yml`: Python 3.11 and 3.12 verification

## Security boundary

This repository contains no runtime credentials. GitHub Actions secrets hold notification credentials. The monitor will contact any URL listed in the trusted `endpoints.json` configuration, so repository review—not runtime URL filtering—enforces the intended public-HTTPS boundary. Review every endpoint change before merge because GitHub-hosted runners will contact those URLs.

## License

[MIT](LICENSE) © 2026 jonah-boop
