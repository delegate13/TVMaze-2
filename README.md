# Media Finder

## Overview

Media Finder is a resizable Tkinter desktop application for searching movie,
television, and episode catalogs across multiple independent data sources. It
includes the top-rated 100 movies from TMDB and a locally calculated IMDb
top-100 list built from IMDb's official non-commercial datasets. The original
TVMaze provider remains available for television show searches.

## Features

- Search supported movie and TV catalogs from TMDB, Trakt, and Simkl.
- Search TVMaze for television shows and Trakt for individual episodes.
- Search the locally derived IMDb top-100 movie list after selecting its data
  files; IMDb data is not searched as a full online catalog.
- Browse TMDB's top-rated 100 movies.
- Browse the top 100 qualifying IMDb movies using the official daily datasets.
- Filter search results by a minimum rating.
- Select the source and media type in a responsive GUI, with asynchronous
  requests so network calls do not freeze the window.
- Use API clients with environment-provided credentials; no API secrets are
  stored in the repository or configuration files.
- Validate user input, configuration, local data, and API responses.
- Write structured JSON logs to `logs/application.log`.
- Run tests without live API requests.

TV Time, Showly, and JustWatch are not integrated: this project only uses
documented public APIs or datasets, and no supported public developer
interfaces for those services were verified. Trakt and Simkl are used only for
public catalog searches; the application does not access personal accounts,
watch histories, or lists.

## Architecture

`main.py` is the composition root. The GUI in `ui/show_finder_window.py` uses
`services/media_discovery_service.py` for shared input validation, provider
routing, and rating filtering. `services/media_provider.py` defines the
provider contract; `services/media_providers.py` implements TMDB, Trakt,
Simkl, and IMDb dataset access. `services/media_discovery_service.py` adapts
the existing TVMaze client to that same contract. All providers normalize
results into the immutable `models/media_item.py` model before presentation.

`services/configuration_service.py` loads runtime configuration. Validators,
exceptions, logging, CLI formatting, menu behavior, and result rendering stay
in focused modules under `utils/` and `ui/`. Tests are under `tests/`; every
network test uses a mock session.

## Design Decisions

- **Provider boundary:** each source implements the same media search and
  ranking contract, keeping source-specific HTTP and response mapping out of
  the GUI.
- **Normalized model:** movie, show, and episode records share a small model
  while retaining their source and media type.
- **Dependency injection:** providers receive configuration, logger, and
  optional HTTP sessions through constructors.
- **Official interfaces only:** no HTML scraping or private app endpoints are
  used. Trakt and Simkl access is limited to public catalog methods.
- **Credential handling:** API credentials come from environment variables,
  never from checked-in configuration or source code.
- **IMDb ranking:** IMDb does not provide a public real-time movie-chart API.
  The application reads its official downloadable TSV datasets and ranks
  movies by average rating, using vote count as a tie-breaker and a configurable
  minimum-vote threshold. This is a locally derived list, not a claim to
  reproduce IMDb's exact chart ranking.
- **Fail clearly:** missing credentials, invalid responses, and unreadable
  dataset files result in user-facing errors and diagnostic log entries.

## Software Engineering Principles Used

The project applies separation of concerns and single responsibility through
focused providers, services, models, validators, and UI components. Constructor
injection supports testability; shared validation and normalized models avoid
duplication. Configuration keeps endpoints, limits, and logging behavior
outside the provider logic. Type hints, dataclasses, immutable result objects,
explicit exceptions, and mocked tests support maintainability.

## Configuration Guide

`config/config.json` is the active configuration; use
`config/config.example.json` as a starting point.

| Key | Purpose |
| --- | --- |
| `api_base_url` / `search_path` | Existing TVMaze API endpoint |
| `provider_base_urls` | API base URLs for TMDB, Trakt, and Simkl |
| `website_base_urls` | Provider links shown on result cards |
| `timeout_seconds` | Per-request timeout |
| `minimum_search_length` | Minimum accepted search phrase length |
| `rating_minimum` / `rating_maximum` | Allowed rating-filter range |
| `imdb_minimum_votes` | Minimum IMDb votes required for the local top list |
| `log_level` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |

Set credentials in the environment before launching the application:

| Variable | Provider | How to obtain it |
| --- | --- | --- |
| `TMDB_ACCESS_TOKEN` | TMDB | TMDB account API read access token |
| `TRAKT_CLIENT_ID` | Trakt | Client ID from a registered Trakt API application |
| `SIMKL_CLIENT_ID` | Simkl | Client ID from a registered Simkl application |
| `IMDB_DATASET_DIRECTORY` | IMDb | Optional path to the folder containing the two dataset files |

For a one-session PowerShell launch, set the relevant values first, for example:

```powershell
$env:TMDB_ACCESS_TOKEN = "your-token"
python main.py
```

The IMDb top list requires `title.ratings.tsv.gz` and `title.basics.tsv.gz`
from [IMDb's official datasets](https://datasets.imdbws.com/). Use the
**Top 100 Movies** action with IMDb selected, then choose the directory
containing those files when prompted. IMDb dataset terms restrict use to
personal and non-commercial use; review the current license before downloading
or using the data. For CLI use, set `IMDB_DATASET_DIRECTORY` to that folder
before running the command.

## Installation Instructions

Python 3.11 or newer with Tcl/Tk support is recommended (the standard Python
for Windows installer includes the Tcl/Tk option required by Tkinter).

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Building a Windows Installer

The installer bundles Python and project dependencies, so the target computer
does not need Python or a separate Tcl/Tk installation. Build on a Windows
computer with the same architecture as the intended target. Internet access
and credentials for the selected API are still required for online searches.

1. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php), or use
   `winget install --id JRSoftware.InnoSetup --exact`.
2. From the project folder, run:

   ```powershell
   .\build_windows.ps1
   ```

The setup executable is `dist-installer\TVMazeShowFinder-Setup.exe`. Copy it
to the other Windows computer, run it, and follow the setup prompts. It
installs per user under `%LOCALAPPDATA%\Programs\TVMaze Show Finder`; a Start
Menu shortcut is created and a desktop shortcut can be selected in setup.
Logs are written to `%LOCALAPPDATA%\TVMazeShowFinder\logs`. The installer is
unsigned, so Windows may show a SmartScreen warning. Update `version.py` to
change the application and installer version together.

## Running the Application

```powershell
python main.py
```

Choose a media type and source, enter a title or keyword, optionally set a
minimum rating, then press **Search** or Enter. Select **TMDB** or **IMDb** and
choose **Top 100 Movies** to browse the corresponding list. The GUI stays
responsive during catalog requests and can be resized; File, Edit, View,
Navigate, and Help menus provide familiar actions.

Some provider/source combinations are not available: TMDB, Simkl, TVMaze, and
IMDb local data do not provide public episode search in this app; Trakt does.
TMDB, Trakt, and Simkl require the corresponding application credentials
described above. IMDb data must first be downloaded by the user.

The command-line interface supports the same configured catalogs:

```powershell
python main.py --cli "The Office"
python main.py --cli "The Office" --min-rating 7.5
python main.py --cli --source TMDB --media-type movie "Dune"
python main.py --cli --source Trakt --media-type episode "The Office"
python main.py --cli --source TMDB --top-movies
python main.py --cli --source IMDb --top-movies
```

Use `--source` to select TVMaze, TMDB, Trakt, Simkl, or IMDb, and
`--media-type` to choose `movie`, `show`, or `episode`. Use `--config PATH` to
select another JSON configuration file.

## Running Tests

```powershell
pytest --cov=main --cov=models --cov=services --cov=ui --cov=utils --cov-report=term-missing --cov-fail-under=80
ruff check .
```

Tests use mocked HTTP sessions and temporary local IMDb-format fixtures; they
do not make live API requests. GUI tests run when a Tcl/Tk runtime is
available. GitHub Actions installs test dependencies and uploads an XML
coverage report.

## Logging

Application events are emitted as structured JSON lines to
`logs/application.log`. The directory and file are created at startup and are
excluded from version control. Logs include application startup,
configuration loading, user searches, provider requests, validation/API errors,
and unexpected exceptions.

## Error Handling

`ConfigurationError`, `ApiError`, and `ValidationError` represent expected
failures. The GUI and CLI display concise messages; technical context and
tracebacks are logged. Unexpected exceptions are logged without exposing
internal details in the interface.

## Future Enhancements

- **More official catalog APIs:** add provider clients behind the existing
  contract when documented public interfaces are available.
- **Caching:** introduce a cache dependency around provider requests with an
  explicit expiry policy.
- **Async requests:** replace the synchronous HTTP client with an asynchronous
  client while keeping the provider boundary.
- **Web interface:** reuse the model, configuration, and services behind a
  separate presentation layer.
- **Database storage:** add a repository abstraction for local collections and
  search history.
- **CSV export:** serialize normalized fields using Python's `csv` module.
- **Excel export:** add an optional spreadsheet dependency and export service.
- **Docker deployment:** package the CLI in an image with externalized
  configuration and a writable log volume.
