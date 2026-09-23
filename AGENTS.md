# AGENTS.md

## Project Overview

monero.fail is a Monero remote node monitoring web application. Users submit node URLs (scheme://host:port), and the app regularly validates and health-checks them, storing results in SQLite. It also discovers peers via the Levin P2P protocol and catalogs Light Wallet Servers (LWS).

## Tech Stack

- **Language:** Python 3
- **Web framework:** Flask (app entry: `xmrnodes/app.py`)
- **ORM/DB:** Peewee with SqliteQueueDatabase (`data/sqlite.db`)
- **Task runner:** Click CLI commands in `xmrnodes/cli.py` (run via cron)
- **Templating:** Jinja2 (`xmrnodes/templates/`)
- **Package management:** uv (see `pyproject.toml`, `uv.lock`)
- **Deployment:** Docker Compose with Tor and I2P sidecar containers + Systemd Gunicorn
- **GeoIP:** MaxMind GeoLite2-City (`data/GeoLite2-City.mmdb`)

## Project Structure

```
xmrnodes/
  app.py          - Flask app factory
  cli.py          - CLI commands: validate, check, export, import, peers, validate_lws, check_lws
  config.py       - Configuration from environment variables
  models.py       - Peewee models: Node, Peer, HealthCheck, LWS, LWSHealthCheck
  helpers.py      - HTTP requests, GeoIP, Levin protocol, utility functions
  forms.py        - WTForms for node and LWS submission
  filters.py      - Jinja2 template filters
  routes/         - Flask blueprints (meta.py handles /add, /add_lws, node listing, LWS listing, API)
  templates/      - Jinja2 HTML templates
  static/         - CSS, JS, images
```

## Key Workflows

### Node Submission
1. User POSTs to `/add` with a URL
2. Validated against regex in `routes/meta.py`
3. Stored as `Node(url=..., validated=False)`

### Node Validation (`flask validate`)
- Picks unvalidated nodes, calls `/get_info` on them
- Determines crypto type, nettype, sets GeoIP data
- Deletes nodes that fail initial validation

### Health Checking (`flask check`)
- Picks 20 oldest-checked validated nodes
- Calls `/get_info`, compares height to network
- Records HealthCheck entries; auto-deletes persistently-failing nodes

### Peer Discovery (`flask peers`)
- Connects to known nodes via Levin protocol
- Extracts peer lists from binary responses
- Stores as Peer records with GeoIP

### LWS Submission
1. User POSTs to `/add_lws` with a URL, contact info, and details URL (all required)
2. Validated against regex in `routes/meta.py`
3. Stored as `LWS(url=..., contact=..., details_url=..., validated=False)`

### LWS Validation (`flask validate_lws`)
- Picks unvalidated LWS servers, POSTs to `/get_version`
- Captures server metadata: server_type, server_version, monero_version_full, blockchain_height, api version, max_subaddresses, network_type, git commit info
- Sets GeoIP data for clearnet servers
- Deletes servers that fail initial validation

### LWS Health Checking (`flask check_lws`)
- Picks 20 oldest-checked validated LWS servers
- POSTs to `/get_version`, updates server metadata
- Records LWSHealthCheck entries; auto-deletes persistently-failing servers (>15 all-failed checks)
- Prunes old successful healthchecks (>240 hours)

## Development

```bash
# Setup
uv sync

# Run dev server
uv run flask run

# Run CLI commands
uv run flask validate
uv run flask check
uv run flask peers
uv run flask validate_lws
uv run flask check_lws
```

Environment variables are defined in `.env` (see `env-example` for reference). Key vars are in `xmrnodes/config.py`.

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_url_validation.py -v

# Run a specific test class
uv run pytest tests/test_helpers.py::TestMakeRequest -v
```

Tests use an in-memory SQLite database and mock external calls (HTTP, DNS, GeoIP). See `TESTS.md` for full details on test structure and conventions.

## Important Patterns

- URLs are stored as `scheme://netloc` (lowercased). The `url` field is the unique identifier for nodes.
- Tor nodes end in `.onion`, I2P nodes end in `.i2p`. Routing is handled automatically via proxy config.
- `socket.gethostbyname()` is used for DNS resolution (IPv4 only currently).
- Host extraction from URLs uses `.split(':')[0]` in some places -- prefer `urlparse().hostname` for correctness.

## Known Limitations / Technical Debt

- No IPv6 support (regex rejects it, `gethostbyname` is IPv4-only, colon-splitting breaks on IPv6)
- No validation that IPv4 octets are <= 255
- SQLite is the only supported database
- Health check deletion logic: if all checks fail and count > 15, node is auto-deleted
