# Testable Configurable Monitor Design

**Date:** 2026-08-18

## Goal

Turn the Fresh Mart uptime monitor into a small, reusable public example without changing its production monitoring or alerting behavior.

## Scope

This change will:

- move endpoint definitions from Python into a tracked JSON configuration file;
- refactor the probe script into import-safe functions and a guarded command-line entry point;
- validate configuration before making network requests;
- add standard-library unit tests for healthy responses, contract mismatches, HTTP errors, network errors, retry behavior, and configuration errors;
- run the tests in GitHub Actions on pushes and pull requests;
- expand the README with architecture, setup, configuration, local testing, and security guidance; and
- add an MIT license.

This change will not alter Telegram secrets, incident deduplication, alert wording, the five-minute schedule, or the three-probe production policy.

## Architecture

`endpoints.json` will contain a JSON array of endpoint objects. Each object requires `name`, `url`, `content_type`, and `contains` string fields.

`check_endpoints.py` will expose four bounded units:

1. `load_checks(path)` loads and validates the configuration.
2. `check(spec, opener=...)` performs one endpoint probe and returns a structured result.
3. `run_checks(checks, attempts=3, delay_seconds=30, sleep=...)` applies the retry policy and returns the complete report.
4. `main(argv=None)` parses arguments, writes JSON to standard output, and returns a process exit code.

The default command will remain compatible with the current workflow:

```bash
python3 check_endpoints.py
```

It will load `endpoints.json`, use three attempts with a 30-second delay, and print the existing report shape:

```json
{
  "healthy": true,
  "attempts": []
}
```

Optional flags will support local verification without changing production defaults:

```text
--config PATH
--attempts INTEGER
--delay-seconds NUMBER
```

## Error Handling

Configuration errors will fail before network access with a concise message on standard error and a non-zero exit code. Invalid attempt counts and negative delays will also fail closed.

Endpoint failures will remain data, not uncaught exceptions. Each result will include the endpoint name, URL, health state, status code, and a bounded detail string. HTTP and transport failures will not expose credentials because endpoint configuration contains no secrets.

## Testing

The test suite will use `unittest`, temporary files, fake openers, and fake sleep functions. It will make no live network requests.

Tests will prove:

- a valid configuration loads;
- malformed JSON, a non-list root, missing fields, wrong field types, and an empty endpoint list fail validation;
- HTTP 200 with the expected type and marker passes;
- wrong status, content type, or marker fails;
- HTTP and transport exceptions become structured failures;
- the runner stops after the first fully healthy attempt;
- the runner retries failures up to the configured limit;
- delays occur only between attempts; and
- CLI output preserves the workflow's `healthy` and `attempts` contract.

CI will run the complete suite on Python 3.11 and 3.12.

## Documentation and License

The README will explain the workflow, configuration schema, local commands, GitHub secrets, incident lifecycle, and security boundary. It will clearly distinguish reusable public code from Fresh Mart's deployment-specific endpoint list.

The repository will use the MIT license so others can reuse the monitor while preserving attribution.

## Compatibility and Rollout

The existing uptime workflow will continue to call `python3 check_endpoints.py > results.json`. The default configuration path, retry count, delay, and output keys will preserve that contract.

Before merge, verification will include:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile check_endpoints.py
python3 check_endpoints.py --help
git diff --check
```

The pull request will describe the unchanged production behavior and attach the complete test output.

## Success Criteria

- The workflow command and JSON keys remain compatible.
- All tests pass without network access.
- CI tests Python 3.11 and 3.12.
- The endpoint list is editable without changing Python code.
- Importing `check_endpoints` performs no network request or sleep.
- The README documents setup and security boundaries.
- The repository contains an MIT license.
