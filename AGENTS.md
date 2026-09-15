# Repository Guidelines

jcutil is a MIT-licensed **src-layout Python utility library** (`src/jcutil/`), not an application. Callers import **submodules**; the package root only exports `__version__` / `__author__`. Treat it as a third-party library: stdlib first, no new hard dependencies, keep public APIs small and import-safe.

Version source of truth: `src/jcutil/__init__.py` (`__version__`, currently `2.1.4`). Hatch reads that path.

## Project Overview

Toolbox for console color, tagged DB/MQ clients, JSON helpers, crypto, Consul KV, HTTP, caches, and APScheduler. Author: Jochen.He.

Design rules for every change:

- Prefer stdlib and existing modules. Do **not** add a runtime dependency unless the feature cannot ship without it.
- Heavy stacks (SQLAlchemy, Kafka, pandas, Mongo, Redis, APScheduler) stay behind the modules that already own them. Do not import them from `chalk` / `core`.
- There are **no package extras** today (`pip install jcutil[db]` is not an API). New optional stacks must use `try/except ImportError` (see `drivers/db.py`, `core/pdtools.py`, `crypto_utils.py`) — or add a real extra, not another core dep.
- Do not re-export from `jcutil/__init__.py`.
- Do not introduce new import-time I/O, logging setup, or network.

## Architecture & Data Flow

Submodule library. Config → tagged client registries → call sites.

```
.env / process env
    → jcutil.server.envars.Envars          # import-time; dotenv + logging.basicConfig
    → Consul KV (CONFIG_PATH = CONSUL_KV_PATH/app/env)
    → jcutil.server.config.load_config()   # YAML via consul.fetch_key
    → jcutil.drivers.smart_load(conf)      # key == drivers.<module>
    → per-driver load() → private __clients / __engines
```

`smart_load(conf)` (`src/jcutil/drivers/__init__.py`): for each key, `import_module(f".{key}", package="jcutil.drivers")` and call `load(conf[key])`. Unknown keys: `ModuleNotFoundError` at **debug**. If `load` returns a coroutine, it is `create_task`'d (Redis: fire-and-forget; client may not be ready yet).

Config keys **must** match driver module names:

```yaml
db:     { app: "postgresql://..." }          # tag → SQLAlchemy URL
mongo:  { app: "mongodb://localhost:27017/app" }
redis:  { cache: "redis://localhost:6379/0" }  # cluster:// → RedisCluster
mq:     { app: "host1:9092,host2:9092" }     # bootstrap string
```

Typical use:

```python
from jcutil.drivers import smart_load, db, mongo, redis

smart_load(conf)
with db.connect('app') as conn:          # engine.connect(); missing → RuntimeError
    conn.execute('SELECT 1')
coll = mongo.get_collection('app', 'users')  # missing → KeyError
r = redis.connect('cache')               # asyncio Redis; missing → None
```

`get_client` is **not** uniform: db raises, mongo raises KeyError, redis returns `None`, mq asserts on `send`.

App-server path: `load_config(*needed_keys)` always requires a `server` key when args are passed, then `smart_load`. For read-only KV, use `consul.fetch_key` — do not call `load_config`.

## Key Directories

| Path | Role |
|---|---|
| `src/jcutil/chalk/` | ANSI color (`Chalk`, `RedChalk`, `show_menu`). colorama on Windows only. |
| `src/jcutil/core/` | JSON (`to_json` / `to_obj` / `fix_document`), event-loop helpers, pandas adapters if installed. |
| `src/jcutil/drivers/` | Tagged clients: `db` (optional SQLAlchemy), `mongo` (pymongo+motor), `redis` (asyncio), `mq` (hard `kafka-python`). |
| `src/jcutil/dba/` | `Where` dict → AND SQL **string** (html-escaped, not parameterized). |
| `src/jcutil/server/` | `Envars` + Consul-backed `load_config`. |
| `src/jcutil/crypto.py` | AES/RSA/hash via pycryptodomex. |
| `src/jcutil/crypto_utils.py` | Password hash/verify (optional passlib; Argon2 default). |
| `src/jcutil/data.py` | `mem_cache` (joblib), `redis_cache` (pickle), `persistence`. |
| `src/jcutil/netio.py` | Async HTTP/SSE/WebSocket (httpx / websockets / aiofiles). |
| `src/jcutil/consul.py` | KV, service, session, lock. `ConfigFormat` / `KvProperty` exist but are **not** in `__all__`. |
| `src/jcutil/schedjob.py` | Process-global APScheduler + Mongo jobstore. `create_by_mongo` once. |
| `tests/` | `test_<module>.py`. No `conftest.py`. |
| `examples/` | Password hashing demo only. |
| `scripts/` | Ruff wrappers. |

## Development Commands

From repo root (`pyproject.toml` must exist).

```bash
# editable install (CI path)
pip install -e .
uv sync --group dev          # pytest, pytest-asyncio, ruff, anyio

# lint (what CI and scripts run — check, not format)
uvx ruff check . --fix
uvx ruff check .
./scripts/lint.sh            # macOS/Linux
# Windows: .\scripts\lint.ps1  (adds --unsafe-fixes; do not copy that flag to CI)

# tests
pytest                       # pytest.ini already sets -ra -v
pytest tests/test_chalk.py
pytest tests/test_core.py::test_json_serialization

# live Mongo/Redis for integration tests (no Consul/Kafka/SQL)
docker compose up -d

# build / publish
uv build
uv publish dist/*            # tags v* or workflow_dispatch
```

Bump version by editing `__version__` in `src/jcutil/__init__.py`. Prefer `uv.lock` over stale `requirements.lock`.

Undeclared optionals (install only if you touch that module):

```bash
pip install sqlalchemy       # drivers.db
pip install kafka-python     # drivers.mq
pip install bcrypt argon2-cffi   # passlib backends for crypto_utils
```

## Code Conventions & Common Patterns

**Formatting.** Ruff (`pyproject.toml`): line length 100, `E501` ignored, select E/F/I/N/W, `target-version = py38`, isort first-party `jcutil`. Format quote-style is **single**. Scripts/CI run `ruff check` only. Quote style in source is mixed — **match the file you edit**.

**Typing.** 3.8 floor is declared; several files already use `X | Y` and `typing.override`. Optional imports use `# pyright: ignore [reportMissingImports]` / `reportInvalidTypeForm`. Stubs can lie (`crypto.pyi` still says `Model`). No project-wide pyright/mypy config beyond `[tool.mypy] exclude = '.*\.pyi$'`.

**Public API.** `__all__` is incomplete (missing on `crypto`, `crypto_utils`, `netio`, `mongo`, `redis`, `mq`). Read the module. Do not invent package-root shortcuts.

**FP.** `jcramda` is first-class (`curry`, `compose`, `when`, `if_else`, `loc`, `first`). Prefer that style in mongo/jsonfy helpers.

**Driver registry.** `load` / `new_client` / `get_client` (aliases: `connect`/`conn`) / `instances`. Module-level dicts. Load failures often **swallow** errors (`db` warning, `smart_load` debug, `load_config` error) — empty registry can look like success.

**Optional vs hard deps.** Copy existing patterns; do not add hard imports for optional stacks:

1. Flag + degrade: `drivers/db.py`, `crypto_utils.py` (`SQLALCHEMY_AVAILABLE` / `_require_passlib()`).
2. Shrink `__all__`: `core/pdtools.py` if pandas missing.
3. No-op fallback: `data.redis_cache`, `jsonfy.pp_json` (pygments).
4. Hard import today: kafka, httpx, pymongo, motor, redis, apscheduler, consul, yaml, hcl, Cryptodome, colorama, jcramda, joblib, aiofiles, websockets, dotenv.

**Async.** `asyncio_mode = strict` in tests — mark coroutine tests `@pytest.mark.asyncio`. `jcutil.core.get_running_loop()` **creates** a loop if none (binds Motor). `async_run` = thread pool. Do **not** call `map_async` or Redis `load()`'s `run_until_complete` path from inside a running loop. Redis `new_client` is async; Mongo is dual `foo` / `async_foo`; mq `subscribe` is async wrapping a sync consumer.

**JSON.** `SafeJsonEncoder` handles UUID, datetime (`%Y-%m-%d %H:%M:%S`), bytes→b64, pandas types if present. **Not** ObjectId, Enum, Decimal. BSON → `jcutil.drivers.mongo.to_json` (`bson.json_util`). `fix_document` strips `$`-keys and maps nan/null; used as decoder hook.

**Mongo documents.** `save` writes `createTime` / `updateTime` / `__v`. `find_page` default-sorts `createdTime` DESC and **mutates** the query (`logicDeleted`).

**Name collisions.** `hmac_sha256` in `core` (curried, base64 bytes) ≠ `crypto.hmac_sha256` (hex str). Mongo `to_json` ≠ `core.to_json`.

**Import-time side effects (do not add more).** `server.envars` configures logging and UDP-connects `180.76.76.76:80` for `local_ip`. `consul` builds a default client. `schedjob` holds a process-global manager.

**Safety.** `dba.Where` concatenates SQL — not for untrusted input. `obj_loads` / `redis_cache` use pickle — not for untrusted Redis. Crypto stays library AES/RSA/password hashing; no new backends, no exploit samples.

**jcramda / logging.** Driver load: log and continue. Do not turn that into hard fails unless asked.

## Important Files

| File | Why |
|---|---|
| `src/jcutil/__init__.py` | Version only. |
| `src/jcutil/drivers/__init__.py` | `smart_load`. |
| `src/jcutil/drivers/db.py` | Optional-dep + registry template. |
| `src/jcutil/server/config.py` | Consul YAML → `smart_load` → `context["conf"]`. |
| `src/jcutil/server/envars.py` | Env contract (`APP_NAME`, `APP_ENV`, `CONFIG_PATH`, …). |
| `pyproject.toml` | Deps, Ruff, hatch version path. No extras. |
| `pytest.ini` | Discovery + strict asyncio. |
| `docker-compose.yml` | Local Mongo `:27017` (no auth) + Redis `:6379`. |
| `tests/config.yaml` | Localhost URIs matching compose. |
| `.github/workflows/python-package.yml` | CI: Python 3.12, Redis+Mongo services, ruff `--fix`, `pytest tests`, `uv build`. |
| `README.md` | Advertised chalk / drivers / crypto APIs. Incomplete vs tree (`dba`, `server`, `netio` usage missing). |
| `README-crypto.md` | `crypto_utils` (not `crypto`). |

Trust **code + tests** over CLAUDE.md / README trees. CLAUDE.md overstates `__all__` coverage, quote uniformity, and SafeJsonEncoder types (no ObjectId/Enum).

## Runtime/Tooling Preferences

- **Python:** `requires-python = ">=3.8"`; local pin `.python-version` = **3.13**; CI matrix **3.12 only**. Do not assume 3.8–3.11 are tested.
- **Package manager:** uv for lock/build/publish; pip `-e .` is what CI uses.
- **Lint:** Ruff. Do not add flake8/black/isort as parallel tools.
- **No extras names.** Do not document `jcutil[mongo]`.
- **`uv.toml` indexes** are PyPI **upload** URLs, not install simple indexes.
- `.gitignore` includes `*.txt` — a `requirements.txt` would be ignored.
- Do not commit `.env` secrets. Local dotenv `MONGO_URI` **overrides** compose’s unauthenticated Mongo in `test_mongo.py`.

Core `[project.dependencies]` is already heavy (pandas, motor+pymongo, redis, apscheduler, joblib, py-consul, …). New features must not grow that list without an extras split.

## Testing & QA

No coverage tool, no tox/nox, no `conftest.py`, no coverage gate.

```bash
pytest                       # from repo root (CWD-relative tests/config.yaml)
```

- Unit (no services): `tests/test_chalk.py`, `test_core.py`, `test_crypto.py`.
- Live skip-on-connect: `test_mongo.py`, `test_redis.py`, `test_consul.py`. Pattern: try ping/connect → `pytest.skip`. Do **not** add fakeredis/mongomock.
- Consul is **not** in compose or CI. Kafka/SQL are not either.
- Async tests **must** be `@pytest.mark.asyncio`. Keep `map_async` tests **sync** (`run_until_complete` nested-loop).
- Redis fixture currently returns `None` then tests call `setup_redis()` as a factory — do not treat Redis tests as a green baseline until that is fixed. Yield `get_client(...)`.

**Has tests (partial):** chalk, core JSON/async/pickle, crypto AES modes, mongo CRUD+proxy, redis ops+locks, consul KV.

**No tests:** `drivers.db`, `drivers.mq`, `smart_load`, `crypto_utils`, `data`, `netio`, `schedjob`, `dba`, `server`, most of core (`pdtools`, loops, hmac) and crypto (RSA/HMAC/PBKDF2).

Add a permanent test when changing a covered contract or a bug that existing asserts would miss. Same file naming (`test_<module>.py`), same skip-if-missing for live services. Do **not** add tests for wiring/`__all__`, optional-dep matrices, or coverage padding. Untested modules: throwaway smoke first; promote only with skip-if-unavailable and no new test-only heavy deps.

Importing `jcutil.drivers.mq` requires `kafka-python` or collection fails. `drivers.db` can be imported without SQLAlchemy.
