# TESTS.md

## Running Tests

```bash
# All tests
uv run pytest tests/ -v

# Single file
uv run pytest tests/test_url_validation.py -v

# Single class
uv run pytest tests/test_helpers.py::TestMakeRequest -v

# Single test
uv run pytest tests/test_models.py::TestHealthCheckModel::test_auto_delete_threshold -v
```

## Test Structure

```
tests/
  __init__.py
  test_url_validation.py  - URL regex validation (submission input)
  test_helpers.py         - Helper functions (is_onion, is_i2p, make_request, get_geoip)
  test_models.py          - Peewee model behavior (Node, HealthCheck, Peer)
  test_routes.py          - Flask route integration tests (/add endpoint)
```

## Conventions

### Database

Tests use an **in-memory SQLite database** (`SqliteDatabase(":memory:")`) bound to models via a fixture. Each test gets a fresh schema:

```python
test_db = SqliteDatabase(":memory:")

@pytest.fixture(autouse=True)
def setup_db():
    test_db.bind([Node, HealthCheck, Peer])
    test_db.connect()
    test_db.create_tables([Node, HealthCheck, Peer])
    yield
    test_db.drop_tables([Node, HealthCheck, Peer])
    test_db.close()
```

### Mocking

External calls are mocked with `unittest.mock.patch`:

- **HTTP requests:** `@patch("xmrnodes.helpers.r_get")` for `make_request`
- **DNS resolution:** `@patch("xmrnodes.helpers.socket.gethostbyname")`
- **GeoIP reader:** `@patch("xmrnodes.helpers.geoip2.database.Reader")`

### Flask Test Client

Route tests use Flask's built-in test client with CSRF disabled:

```python
@pytest.fixture
def app():
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    # ... bind test_db ...
    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()
```

### Parametrized Tests

URL validation tests use `@pytest.mark.parametrize` for concise coverage of many inputs:

```python
@pytest.mark.parametrize("url", [
    "http://1.2.3.4:18081",
    "http://node.example.com:18081",
])
def test_valid_urls(self, url):
    assert REGEX.match(url)
```

## Test Categories

### test_url_validation.py

| Class | Purpose |
|-------|---------|
| `TestCurrentRegexAccepts` | URLs the current regex correctly matches |
| `TestCurrentRegexRejects` | URLs the current regex correctly rejects |
| `TestCurrentRegexKnownBugs` | Documents known issues (invalid octets accepted) |
| `TestIPv6Regex` | Tests for the proposed IPv6-capable regex |

### test_helpers.py

| Class | Purpose |
|-------|---------|
| `TestIsOnion` | Tor URL detection |
| `TestIsI2p` | I2P URL detection |
| `TestHostExtraction` | Documents correct vs broken host parsing |
| `TestMakeRequest` | Proxy routing based on URL type |
| `TestGetGeoip` | DNS resolution and GeoIP lookup |

### test_models.py

| Class | Purpose |
|-------|---------|
| `TestNodeModel` | Node CRUD, uniqueness, `get_netloc()` |
| `TestHealthCheckModel` | Health check records, auto-delete threshold |
| `TestPeerModel` | Peer CRUD, `hostname`/`port` properties |

### test_routes.py

| Class | Purpose |
|-------|---------|
| `TestAddNode` | `/add` POST endpoint — valid/invalid/duplicate submissions |

## Writing New Tests

1. Place tests in the appropriate file by category, or create a new `tests/test_*.py` file.
2. Use the in-memory DB fixture pattern (copy from existing test files).
3. Mock all external I/O (network, filesystem, GeoIP).
4. Use parametrize for input variations.
5. Name tests descriptively: `test_<what>_<condition>` (e.g., `test_ipv6_not_onion`).
6. Tests documenting future behavior should assert current (broken) behavior and include a docstring noting "After refactor this should...".
