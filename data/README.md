# Data and provenance

The project authors provide six synthetic procedures and four synthetic totes, including one overweight tote, in the Python fixtures. Runtime startup seeds procedure records into SQLite. There are no real warehouse records, operator recordings, third-party datasets or model weights in the repository.

Runtime databases and their WAL files are ignored by Git. Treat persisted transcripts as operational data. Training and evaluation seeds are separate; the tiny synthetic fixtures are not a held-out language or human-interaction benchmark.
