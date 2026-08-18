import contextlib
from email.message import Message
import importlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import check_endpoints


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


class ConfigurationTests(unittest.TestCase):
    def test_loads_valid_configuration(self):
        checks = [
            {
                "name": "Example",
                "url": "https://example.com/health",
                "content_type": "application/json",
                "contains": '"status":"ok"',
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "endpoints.json"
            path.write_text(json.dumps(checks), encoding="utf-8")

            loaded = check_endpoints.load_checks(path)

        self.assertEqual(loaded, checks)

    def test_rejects_non_list_root(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "endpoints.json"
            path.write_text(json.dumps({"name": "not-a-list"}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "non-empty JSON list"):
                check_endpoints.load_checks(path)

    def test_rejects_empty_list(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "endpoints.json"
            path.write_text("[]", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "non-empty JSON list"):
                check_endpoints.load_checks(path)

    def test_rejects_non_object_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "endpoints.json"
            path.write_text(json.dumps(["not-an-object"]), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "endpoint 0 must be an object"):
                check_endpoints.load_checks(path)

    def test_rejects_missing_required_field(self):
        checks = [
            {
                "name": "Example",
                "url": "https://example.com",
                "content_type": "text/html",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "endpoints.json"
            path.write_text(json.dumps(checks), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "field 'contains'"):
                check_endpoints.load_checks(path)

    def test_rejects_wrong_field_type(self):
        checks = [
            {
                "name": "Example",
                "url": 42,
                "content_type": "text/html",
                "contains": "Example",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "endpoints.json"
            path.write_text(json.dumps(checks), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "field 'url'"):
                check_endpoints.load_checks(path)

    def test_rejects_blank_field(self):
        checks = [
            {
                "name": "   ",
                "url": "https://example.com",
                "content_type": "text/html",
                "contains": "Example",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "endpoints.json"
            path.write_text(json.dumps(checks), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "field 'name'"):
                check_endpoints.load_checks(path)

    def test_rejects_malformed_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "endpoints.json"
            path.write_text("[{", encoding="utf-8")

            with self.assertRaises(json.JSONDecodeError):
                check_endpoints.load_checks(path)


class FakeHeaders:
    def __init__(self, content_type):
        self.content_type = content_type

    def get_content_type(self):
        return self.content_type


class FakeResponse:
    def __init__(self, *, status=200, content_type="text/html", body=b"Example"):
        self.status = status
        self.headers = FakeHeaders(content_type)
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, limit):
        return self.body[:limit]


class ProbeTests(unittest.TestCase):
    spec = {
        "name": "Example",
        "url": "https://example.com/health",
        "content_type": "text/html",
        "contains": "Example",
    }

    def test_expected_contract_is_healthy(self):
        calls = []

        def opener(request, timeout):
            calls.append((request.full_url, timeout))
            return FakeResponse()

        result = check_endpoints.check(self.spec, opener=opener)

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["detail"], "expected marker present")
        self.assertEqual(calls, [("https://example.com/health", 20)])

    def test_contract_mismatch_is_unhealthy(self):
        cases = {
            "status": FakeResponse(status=503),
            "content type": FakeResponse(content_type="application/json"),
            "marker": FakeResponse(body=b"Unexpected"),
        }
        for label, response in cases.items():
            with self.subTest(label=label):
                result = check_endpoints.check(
                    self.spec, opener=lambda request, timeout: response
                )

                self.assertFalse(result["ok"])
                self.assertEqual(result["detail"], "status/type/content contract mismatch")

    def test_http_error_becomes_structured_failure(self):
        def opener(request, timeout):
            raise check_endpoints.urllib.error.HTTPError(
                request.full_url,
                503,
                "Service Unavailable",
                Message(),
                None,
            )

        result = check_endpoints.check(self.spec, opener=opener)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], 503)
        self.assertEqual(result["detail"], "HTTP 503")

    def test_transport_error_becomes_structured_failure(self):
        def opener(request, timeout):
            raise TimeoutError("timed out")

        result = check_endpoints.check(self.spec, opener=opener)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], 0)
        self.assertEqual(result["detail"], "TimeoutError: timed out")


class RetryTests(unittest.TestCase):
    checks = [{"name": "Example"}]

    def test_stops_after_first_healthy_attempt(self):
        checker_calls = []
        sleep_calls = []

        def checker(spec):
            checker_calls.append(spec)
            return {"ok": True}

        result = check_endpoints.run_checks(
            self.checks,
            checker=checker,
            sleep=sleep_calls.append,
        )

        self.assertTrue(result["healthy"])
        self.assertEqual(len(result["attempts"]), 1)
        self.assertEqual(checker_calls, self.checks)
        self.assertEqual(sleep_calls, [])

    def test_retries_until_recovery(self):
        outcomes = iter([False, True])
        sleep_calls = []

        def checker(spec):
            return {"ok": next(outcomes)}

        result = check_endpoints.run_checks(
            self.checks,
            attempts=3,
            delay_seconds=7,
            checker=checker,
            sleep=sleep_calls.append,
        )

        self.assertTrue(result["healthy"])
        self.assertEqual(len(result["attempts"]), 2)
        self.assertEqual(sleep_calls, [7])

    def test_reports_unhealthy_after_exhaustion(self):
        sleep_calls = []

        result = check_endpoints.run_checks(
            self.checks,
            attempts=3,
            delay_seconds=2,
            checker=lambda spec: {"ok": False},
            sleep=sleep_calls.append,
        )

        self.assertFalse(result["healthy"])
        self.assertEqual(len(result["attempts"]), 3)
        self.assertEqual(sleep_calls, [2, 2])

    def test_rejects_attempts_below_one(self):
        with self.assertRaisesRegex(ValueError, "attempts must be at least 1"):
            check_endpoints.run_checks(self.checks, attempts=0)

    def test_rejects_negative_delay(self):
        with self.assertRaisesRegex(ValueError, "delay_seconds must be non-negative"):
            check_endpoints.run_checks(self.checks, delay_seconds=-1)


if __name__ == "__main__":
    unittest.main()
