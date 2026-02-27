# AGENTS.md — pyomnigraph

Coding agent guidelines for this repository.

---

## Project Overview

`pyomnigraph` is a Python library and CLI tool for managing multiple SPARQL/RDF triple-store servers
(Blazegraph, GraphDB, Jena, QLever, Oxigraph, Stardog, Virtuoso, MillenniumDB) via a unified interface.
The main source package is `omnigraph/`. Tests live in `tests/`.

---

## Build & Installation

```bash
# Install package in editable mode (also installs qlever CLI)
scripts/install

# Or manually:
pip install -e ".[dev,test]"
```

Build backend is `hatchling`. There is no `Makefile`; use `scripts/` shell scripts for
common workflows.

---

## Running Tests

The primary test runner is Python's built-in `unittest`. All test classes extend
`tests.basetest.Basetest` (which extends `unittest.TestCase`).

```bash
# Run the full test suite (default, used in CI)
scripts/test
# equivalent to:
python3 -m unittest discover

# Run a single test module
python -m unittest tests.test_software_list

# Run a single test class
python -m unittest tests.test_software_list.TestSoftwareList

# Run a single test method
python -m unittest tests.test_software_list.TestSoftwareList.test_check_available_software

# Alternative runners (if installed)
scripts/test -g          # green runner (human-friendly output)
scripts/test -m          # run each module separately
pytest tests/test_software_list.py::TestSoftwareList::test_check_available_software
```

No `pytest.ini` or `tox.ini` exists. `pytest` is an optional dependency only.

---

## Linting & Formatting

```bash
# Format all source and test files (runs isort then black)
scripts/blackisort

# Equivalent to:
isort omnigraph/*.py tests/*.py
black omnigraph/*.py tests/*.py
```

| Tool | Version | Config |
|------|---------|--------|
| `black` | >=23.0.0 | `line-length = 120` (in `pyproject.toml`) |
| `isort` | >=5.12.0 | default settings (no custom config) |
| `mypy` | >=1.0.0 | no config file; run manually with `mypy omnigraph/` |

Always run `scripts/blackisort` before committing. There is no pre-commit hook wired up.

---

## CI

CI runs on GitHub Actions (`.github/workflows/build.yml`) on `ubuntu-latest` / Python 3.12
for every push and PR to `main`. The pipeline runs:

1. `scripts/install` — installs the package + qlever
2. `scripts/test` — `python3 -m unittest discover`

The `GHACTIONS` environment variable is set to `ACTIVE` in CI; use `self.inPublicCI()` from
`Basetest` to skip tests that require local infrastructure (running servers, etc.).

---

## Code Style Guidelines

### Line Length

Maximum **120 characters** (enforced by black).

### Imports

Follow the standard `isort` three-group layout, separated by blank lines:

```python
# 1. Standard library
import os
import re
from pathlib import Path
from typing import List, Optional

# 2. Third-party packages
import requests
from tqdm import tqdm

# 3. Local / project imports
from omnigraph.server_config import ServerConfig
from omnigraph.sparql_server import SparqlServer
```

- Do **not** put imports inside function or method bodies (avoid inline imports).
- Prefer `from X import Y` over bare `import X` for long module paths.

### Type Annotations

Use type annotations on **all** function signatures and return types:

```python
def wait_until_ready(self, timeout: float = 30.0) -> bool:
    ...

def get_server_list(self) -> List[SparqlServer]:
    ...
```

- Use `Optional[X]` (imported from `typing`) for nullable parameters/return values.
- Dataclass fields must also be annotated.
- The codebase mixes `typing.List`/`typing.Optional` (older style) with modern lowercase
  `list[X]`/`tuple[X, Y]` — prefer the modern lowercase style for new code targeting
  Python >= 3.10.

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Classes | `PascalCase` | `SparqlServer`, `BlazegraphConfig` |
| Functions / methods | `snake_case` | `docker_create()`, `wait_until_ready()` |
| Instance / local variables | `snake_case` | `self.config`, `avail_mem` |
| Module-level constants | `UPPER_CASE` | `DEFAULT_TIMEOUT` |
| Enum values | `UPPER_CASE` | `SUPPORTED`, `MISSING_LICENSE` |
| Private helpers | leading `_` | `_convert_turtle_to_insert()` |
| Test methods | `test_` prefix + `snake_case` | `test_check_available_software()` |

### Docstrings

Use **Google-style docstrings** (required by mkdocstrings, configured in `mkdocs.yml`):

```python
def make_request(self, method: str, url: str, **kwargs) -> Response:
    """
    Helper for making HTTP requests with consistent error handling.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        **kwargs: Additional arguments forwarded to requests

    Returns:
        Response dataclass wrapping the HTTP response
    """
```

Every public class and public method should have a docstring. Module-level docstrings follow
this format (Eclipse/PyDev style from project history):

```python
"""
Created on YYYY-MM-DD

@author: <username>
"""
```

### Dataclasses

Prefer `@dataclass` for configuration and value objects. Use `field(default=None)` for optional
fields and `__post_init__` for derived attributes:

```python
@dataclass
class ServerConfig:
    name: str
    host: str = "localhost"
    port: int = 9999
    url: Optional[str] = field(default=None)

    def __post_init__(self):
        if self.url is None:
            self.url = f"http://{self.host}:{self.port}"
```

Use `@lod_storable` (from `basemkit.yamlable`) on config container classes to get
`load_from_yaml_file()` / `ofYaml()` for free.

### Error Handling

- Catch exceptions with `except Exception as ex:` and delegate to
  `self.handle_exception(context, ex)` rather than re-raising or printing directly.
- Propagate success/failure as **return values** (`bool`, count `int`, or
  `tuple[result, Exception]`), not as raised exceptions in the public API.
- HTTP results are wrapped in a `Response` dataclass; do not raise on HTTP errors.

```python
# Preferred pattern
def upload_data(self, data: str) -> bool:
    try:
        response = self.make_request("POST", self.upload_url, data=data)
        return response.ok
    except Exception as ex:
        self.handle_exception("upload_data", ex)
        return False

# Tuple return for SPARQL operations
def execute_update(self, query: str) -> tuple[Optional[Any], Optional[Exception]]:
    return self.sparql.insert(query)
```

### Logging

Use `Log.log(emoji, context, message)` from `basemkit` consistently. Standard emoji markers:

| Emoji | Meaning |
|-------|---------|
| `✅` | success |
| `❌` | error / failure |
| `⚠️` | warning |
| `🛑` | stopped / halted |
| `🔄` | in-progress / retry |

### Server Subclassing Pattern

Each triple store is implemented as:
- A `@dataclass` config class (e.g., `BlazegraphConfig`) that extends or wraps `ServerConfig`
- A server class (e.g., `Blazegraph`) that extends `SparqlServer`

Override only the hooks that differ per server:
`status()`, `pre_create()`, `post_create()`, `upload_request()`, `get_clear_query()`.

Register the pair in `OmniServer.server4Config()` factory method.

### Tests

- Extend `tests.basetest.Basetest` (not `unittest.TestCase` directly).
- Call `Basetest.setUp(self, debug=False, profile=True)` in each test's `setUp`.
- Use `self.inPublicCI()` to skip tests requiring live servers or local resources.
- Keep test method names descriptive: `test_<what_is_being_tested>`.

```python
class TestSparqlServer(Basetest):
    def setUp(self):
        Basetest.setUp(self, debug=False, profile=True)

    def test_connect(self):
        if self.inPublicCI():
            return
        # ... test logic
```

---

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `pybasemkit` | Base utilities: logging (`Log`), YAML I/O, shell, Docker (`DockerUtil`) |
| `pyLodStorage` | SPARQL client, RDF formats, `Endpoint`, `PrefixConfigs` |
| `psutil` | System/process monitoring (memory, PID checks) |
| `dacite` | Dataclass instantiation from dicts |
| `PyYAML` | YAML parsing |
| `tqdm` | Progress bars |
| `qlever` | QLever database management |

Runtime requires **Python >= 3.10**.
