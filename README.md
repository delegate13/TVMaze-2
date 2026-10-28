# TVMaze Show Finder

## Overview

TVMaze Show Finder is a desktop application that searches the public TVMaze API,
validates its responses, and presents normalized show information. Its
searchable, scrollable window filters results by an optional minimum rating;
the same features are also available from an optional command-line interface.

## Features

- Search TVMaze by show name or phrase.
- Browse results in a desktop window with responsive show cards and summaries.
- Optionally filter results by a rating threshold from 0 to 10.
- Validate user input, configuration, and API response data.
- Write structured JSON logs to `logs/application.log`.
- Run isolated unit tests with mocked HTTP requests.

## Architecture

The root `main.py` is the composition root and launches the desktop interface
by default; `ui/show_finder_window.py` is the Tkinter presentation layer.
`services/configuration_service.py` loads runtime settings,
`services/tvmaze_service.py` owns HTTP communication, and
`services/show_filter_service.py` contains rating filtering. `models/show.py`
holds the immutable show model. `utils/` contains reusable validation,
structured logging, application exceptions, and presentation formatting.
Configuration examples are in `config/`; tests are in `tests/`.

## Design Decisions

- **Dependency injection:** the API service receives immutable configuration,
  a logger, and an optional `requests.Session`; tests can substitute the session.
- **Explicit boundaries:** the API client returns validated `Show` objects,
  leaving CLI formatting to a presentation utility.
- **Fail clearly:** expected configuration, network, and validation failures
  have dedicated exceptions and concise user-facing messages. Technical
  details are recorded in logs.
- **Small synchronous client:** synchronous `requests` keeps this interactive
  CLI straightforward; the service boundary permits later replacement.
- **No API secrets:** TVMaze search does not require credentials, and runtime
  settings remain outside business logic in JSON configuration.

## Software Engineering Principles Used

The project applies separation of concerns and single responsibility through
focused services, model, validators, and CLI layers. Constructor injection
supports testability; shared validation and formatting avoid duplication.
Configuration-driven timeouts, paths, logging levels, and rating bounds avoid
scattered tuning constants. Service interfaces make additional APIs and
filters possible without coupling them to terminal output. Dataclasses,
type hints, immutable settings, explicit errors, and automated coverage support
maintainability.

## Configuration Guide

`config/config.json` is the active configuration; use
`config/config.example.json` as a starting point for another environment.

| Key | Purpose |
| --- | --- |
| `api_base_url` | Absolute TVMaze API base URL |
| `search_path` | Relative path used for show searches |
| `timeout_seconds` | HTTP request timeout |
| `minimum_search_length` | Minimum accepted search phrase length |
| `rating_minimum` / `rating_maximum` | Allowed threshold range |
| `log_level` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |

Use `--config PATH` to select a configuration file. Rating bounds must remain
inside the TVMaze 0-to-10 rating scale.

## Installation Instructions

Python 3.11 or newer with Tcl/Tk support is recommended (the standard Python
for Windows installer includes the Tcl/Tk option required by Tkinter).

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Running the Application

```powershell
python main.py
```

The desktop window opens by default. Search for a show, optionally choose a
minimum rating, and press **Search shows** (or Enter). Results load in the
background so the window remains responsive.

The command-line interface remains available:

```powershell
python main.py --cli "The Office"
python main.py --cli "The Office" --min-rating 7.5
```

To select another configuration file:

```powershell
python main.py --config config\config.example.json
python main.py --cli --config config\config.example.json "The Office"
```

The application requires a graphical desktop session for the default GUI and
network access to the configured API when performing a search.

Providing a search phrase without `--cli` also runs a one-shot CLI search for
compatibility with the original invocation.

## Running Tests

```powershell
pytest --cov=main --cov=models --cov=services --cov=ui --cov=utils --cov-report=term-missing --cov-fail-under=80
ruff check .
```

All service tests use mocked HTTP sessions; the test suite makes no live API
requests. GUI tests run when a Tcl/Tk runtime is available; GitHub Actions
installs a virtual display and desktop test dependencies, then uploads an XML
coverage report.

## Logging

Application events are emitted as structured JSON lines to
`logs/application.log`. The directory and file are created at startup and are
excluded from version control. Logs include application startup, configuration
loading, searches, requests, validation/API errors, and unexpected exceptions.

## Error Handling

`ConfigurationError`, `ApiError`, and `ValidationError` represent expected
failures. The CLI displays concise messages and returns a non-zero exit status
for failures; technical context and tracebacks are logged. Unexpected
exceptions are logged with a traceback without exposing internals to users.

## Future Enhancements

- **Multiple APIs:** add provider-specific clients behind a shared search
  contract and normalize each result into the existing `Show` model.
- **Caching:** introduce a cache dependency around API requests with an
  explicit expiry policy.
- **Async requests:** replace the synchronous HTTP client with an asynchronous
  client and make concurrency an API-service concern.
- **Web interface:** reuse the model, configuration, and services behind a
  separate web presentation layer.
- **Database storage:** add a repository abstraction for persisting shows and
  search history.
- **CSV export:** serialize normalized fields using Python's `csv` module.
- **Excel export:** add an optional spreadsheet dependency and export service.
- **Docker deployment:** package the CLI in an image with externalized
  configuration and a writable log volume.
