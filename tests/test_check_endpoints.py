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


if __name__ == "__main__":
    unittest.main()
