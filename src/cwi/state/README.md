# Durable state

`warehouse.py` defines synthetic inventory and the configured operator. `store.py` seeds versioned procedure records and atomically writes a SQLite checkpoint containing conversations and simulator state. This is a single-process store, not distributed persistence.

See the [project README](../../../README.md) for startup, evidence and scope.
