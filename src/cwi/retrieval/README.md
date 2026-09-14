# Grounded retrieval

`service.py` ranks six synthetic procedures with BM25. It filters inactive and other-warehouse documents and rejects conflicting active versions. Required policy citations use exact IDs. SQLite provides the runtime records; no vector database is required for this small corpus.

See the [project README](../../../README.md) for startup, evidence and scope.
