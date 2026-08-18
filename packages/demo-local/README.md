# Demo Local

Development-only SQLite persistence, canonical read adapters, and capability hashing for M4.

This package may access local M1-M4 repositories at composition time. It must not be imported by
the separate demo runtime, perform external network calls, or provide real action integrations.
