# Testable Configurable Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the deployed uptime workflow while making the monitor import-safe, configurable, tested, documented, and reusable.

**Architecture:** Keep one dependency-free Python script. Extract configuration, probing, retries, and CLI orchestration into functions with injected network and sleep boundaries. Store deployment-specific endpoints in JSON and run a standard-library test suite in GitHub Actions.

**Tech Stack:** Python 3.11/3.12 standard library, `unittest`, JSON, GitHub Actions, Markdown.

## Global Constraints

- Preserve `python3 check_endpoints.py > results.json`.
- Preserve top-level JSON keys `healthy` and `attempts`.
- Preserve three attempts, 30-second delays, and the current endpoint contracts by default.
- Make no live network requests in tests.
- Keep Telegram credentials only in GitHub Actions secrets.
- Use strict RED-GREEN-REFACTOR for Python behavior.

---

### Task 1: Make Imports Side-Effect Free

**Files:**
- Create: `tests/test_check_endpoints.py`
- Modify: `check_endpoints.py:25-32`

**Interfaces:**
- Consumes: existing `check(spec)` and `CHECKS`.
- Produces: `main() -> int` and a `if __name__ == "__main__"` guard.

- [ ] **Step 1: Write the failing import-safety test**

```python
import contextlib
import importlib
import io
import sys
import unittest
from unittest import mock


class ImportSafetyTests(unittest.TestCase):
    def test_import_performs_no_network_or_output(self):
        sys.modules.pop("check_endpoints", None)
        output = io.StringIO()
        with (
            mock.patch("urllib.request.urlopen") as opener,
            mock.patch("time.sleep") as sleeper,
            contextlib.redirect_stdout(output),
        ):
            importlib.import_module("check_endpoints")

        opener.assert_not_called()
        sleeper.assert_not_called()
        self.assertEqual(output.getvalue(), "")
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python3 -m unittest tests.test_check_endpoints.ImportSafetyTests -v`

Expected: FAIL because importing the current script executes probes and prints JSON.

- [ ] **Step 3: Extract the current top-level runner**

```python
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
    print(json.dumps({"healthy": all(result["ok"] for result in final), "attempts": attempts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run focused and complete tests**

Run: `python3 -m unittest tests.test_check_endpoints.ImportSafetyTests -v`

Expected: PASS.

Run: `python3 -m unittest discover -s tests -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add check_endpoints.py tests/test_check_endpoints.py
git commit -m "refactor: make monitor safe to import"
```

### Task 2: Load and Validate Endpoint Configuration

**Files:**
- Create: `endpoints.json`
- Modify: `check_endpoints.py`
- Modify: `tests/test_check_endpoints.py`

**Interfaces:**
- Produces: `load_checks(path: str | pathlib.Path) -> list[dict[str, str]]`.
- Each endpoint requires non-empty string fields: `name`, `url`, `content_type`, and `contains`.

- [ ] **Step 1: Add a valid-configuration test**

Use `tempfile.TemporaryDirectory()` and write a JSON list with one complete endpoint. Assert `load_checks(path)` returns the list unchanged.

- [ ] **Step 2: Run the valid-configuration test and verify RED**

Run: `python3 -m unittest tests.test_check_endpoints.ConfigurationTests.test_loads_valid_configuration -v`

Expected: ERROR because `load_checks` does not exist.

- [ ] **Step 3: Implement the minimal loader**

```python
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
            if not isinstance(spec.get(field), str) or not spec[field].strip():
                raise ValueError(f"endpoint {index} field {field!r} must be a non-empty string")
    return checks
```

- [ ] **Step 4: Add and cycle validation tests one at a time**

Add separate tests for malformed JSON, non-list root, empty list, non-object endpoint, missing field, wrong field type, and blank field. Run each test before and after the minimal validation change that satisfies it.

- [ ] **Step 5: Create the production configuration**

```json
[
  {
    "name": "Main storefront",
    "url": "https://freshmart.com.ng/",
    "content_type": "text/html",
    "contains": "Fresh Mart"
  },
  {
    "name": "Shop health API",
    "url": "https://shop.freshmart.com.ng/store/health",
    "content_type": "application/json",
    "contains": "\"status\":\"ok\""
  },
  {
    "name": "Admin entry",
    "url": "https://admin.freshmart.com.ng/admin",
    "content_type": "text/html",
    "contains": "Fresh Mart"
  }
]
```

- [ ] **Step 6: Run the complete suite and validate JSON**

Run: `python3 -m unittest discover -s tests -v`

Expected: PASS.

Run: `python3 -m json.tool endpoints.json >/dev/null`

Expected: exit 0.

- [ ] **Step 7: Commit**

```bash
git add check_endpoints.py endpoints.json tests/test_check_endpoints.py
git commit -m "feat: load endpoint checks from validated config"
```

### Task 3: Test the Probe Boundary

**Files:**
- Modify: `check_endpoints.py`
- Modify: `tests/test_check_endpoints.py`

**Interfaces:**
- Produces: `check(spec, opener=urllib.request.urlopen) -> dict[str, object]`.
- A response object supplies `status`, `headers.get_content_type()`, `read(limit)`, and context-manager methods.

- [ ] **Step 1: Add a healthy-response test with a fake response**

Create a small `FakeResponse` class and an opener function that returns it. Assert status 200, matching content type, and marker produce `ok=True`.

- [ ] **Step 2: Run the test and verify RED**

Run: `python3 -m unittest tests.test_check_endpoints.ProbeTests.test_expected_contract_is_healthy -v`

Expected: ERROR because `check` does not accept an injected opener.

- [ ] **Step 3: Inject the opener**

Change the signature to:

```python
def check(spec, opener=urllib.request.urlopen):
```

Replace `urllib.request.urlopen(req, timeout=20)` with `opener(req, timeout=20)`.

- [ ] **Step 4: Add and cycle failure tests one at a time**

Add separate tests for wrong status, wrong content type, missing marker, `urllib.error.HTTPError`, and `OSError`. Assert each failure returns `ok=False`, a bounded status, and a useful detail without raising.

- [ ] **Step 5: Run the complete suite**

Run: `python3 -m unittest discover -s tests -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add check_endpoints.py tests/test_check_endpoints.py
git commit -m "test: cover endpoint probe contracts and failures"
```

### Task 4: Extract and Test Retry Policy

**Files:**
- Modify: `check_endpoints.py`
- Modify: `tests/test_check_endpoints.py`

**Interfaces:**
- Produces: `run_checks(checks, attempts=3, delay_seconds=30, checker=check, sleep=time.sleep) -> dict[str, object]`.

- [ ] **Step 1: Add an early-success test**

Use a fake checker that returns healthy results and a fake sleeper that records calls. Assert one attempt, `healthy=True`, and no sleep.

- [ ] **Step 2: Run the test and verify RED**

Run: `python3 -m unittest tests.test_check_endpoints.RetryTests.test_stops_after_first_healthy_attempt -v`

Expected: ERROR because `run_checks` does not exist.

- [ ] **Step 3: Implement the retry function**

```python
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
```

- [ ] **Step 4: Add and cycle retry tests one at a time**

Add tests for failure followed by recovery, exhaustion after three failures, exact delays between attempts, attempts below one, and negative delay.

- [ ] **Step 5: Run the complete suite**

Run: `python3 -m unittest discover -s tests -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add check_endpoints.py tests/test_check_endpoints.py
git commit -m "refactor: isolate and test monitor retry policy"
```

### Task 5: Add a Compatible CLI

**Files:**
- Modify: `check_endpoints.py`
- Modify: `tests/test_check_endpoints.py`

**Interfaces:**
- Produces: `main(argv=None) -> int`.
- Supports `--config`, `--attempts`, and `--delay-seconds` while retaining existing defaults.

- [ ] **Step 1: Add a CLI success test**

Patch `load_checks` and `run_checks`, call `main([])`, capture stdout, and assert the JSON contains `healthy` and `attempts` and the return code is zero.

- [ ] **Step 2: Run the test and verify RED**

Run: `python3 -m unittest tests.test_check_endpoints.CliTests.test_main_prints_compatible_report -v`

Expected: FAIL because `main` does not accept arguments or load configuration.

- [ ] **Step 3: Implement CLI parsing and orchestration**

Use `argparse.ArgumentParser`, default config path `Path(__file__).with_name("endpoints.json")`, default attempts `3`, and default delay `30`. Print `json.dumps(report, indent=2)`.

Catch `OSError`, `json.JSONDecodeError`, and `ValueError`; print `configuration error: ...` to stderr and return `2`.

- [ ] **Step 4: Add and cycle CLI error tests**

Add tests for custom values reaching `run_checks`, malformed configuration returning `2`, attempts below one returning `2`, and negative delay returning `2`.

- [ ] **Step 5: Run focused and complete verification**

Run: `python3 -m unittest discover -s tests -v`

Expected: PASS.

Run: `python3 check_endpoints.py --help`

Expected: exit 0 and all three flags listed.

Run: `python3 -m py_compile check_endpoints.py`

Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add check_endpoints.py tests/test_check_endpoints.py
git commit -m "feat: add compatible monitor CLI"
```

### Task 6: Add CI, Documentation, and License

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `LICENSE`
- Modify: `README.md`

**Interfaces:**
- CI runs `python3 -m unittest discover -s tests -v` on Python 3.11 and 3.12.

- [ ] **Step 1: Create the CI workflow**

Use `actions/checkout@v4` and `actions/setup-python@v5`. Trigger on pushes and pull requests. Grant `contents: read` only.

- [ ] **Step 2: Add the MIT license**

Use the standard MIT text with copyright `2026 jonah-boop`.

- [ ] **Step 3: Rewrite the README**

Document purpose, architecture, endpoint schema, local commands, CLI flags, GitHub secrets, incident lifecycle, CI, security boundaries, and license. State that public code contains no credentials and that deployment-specific endpoints live in `endpoints.json`.

- [ ] **Step 4: Verify documentation and workflow contracts**

Run a Python script that parses `endpoints.json` and asserts README mentions `endpoints.json`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, the test command, and MIT.

Run: `git diff --check`

Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml LICENSE README.md
git commit -m "docs: publish setup, CI, and MIT license"
```

### Task 7: Final Verification and Pull Request

**Files:**
- Review all changed files.

**Interfaces:**
- Produces: a public pull request against `jonah-boop/freshmart-uptime-monitor:main`.

- [ ] **Step 1: Run the full verification ladder**

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile check_endpoints.py
python3 check_endpoints.py --help
python3 -m json.tool endpoints.json >/dev/null
git diff --check main...HEAD
git status --short
```

Expected: all commands exit 0; status is clean.

- [ ] **Step 2: Review scope**

Run: `git diff --stat main...HEAD`

Run: `git log --oneline main..HEAD`

Confirm every change belongs to the approved design and contains no secrets.

- [ ] **Step 3: Push the branch**

```bash
git push -u origin feat/testable-configurable-monitor
```

- [ ] **Step 4: Open the pull request**

Create a PR titled `Make the uptime monitor configurable and testable`. Summarize compatibility, tests, CI, documentation, and licensing. Include the exact verification command and result.

- [ ] **Step 5: Verify the remote artifact**

Run `gh pr view --json number,url,state,headRefName,baseRefName` and `gh pr checks` for the created PR. Report pending checks honestly; do not claim CI success until GitHub reports it.
