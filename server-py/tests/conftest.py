"""
Shared pytest fixtures.

The kit ships an empty conftest — apps add fixtures here as they grow.
Backend tests assume a live Mongo instance reachable via core.config settings
(no mongomock) — start mongo via `./dev.sh` or `docker compose up mongo -d`
before running the suite.
"""
