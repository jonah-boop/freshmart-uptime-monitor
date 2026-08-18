import contextlib
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


if __name__ == "__main__":
    unittest.main()
