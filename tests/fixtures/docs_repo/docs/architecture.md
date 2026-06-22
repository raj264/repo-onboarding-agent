# Architecture

## Retry Strategy

The ingestion pipeline wraps each external call with exponential backoff:
3 attempts, base delay 1 second, doubling each time.

## Storage

Ingested files are written to a local staging directory before being loaded
into the database.
