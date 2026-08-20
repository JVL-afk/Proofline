# Shadow Validation Local

M6.7A local adapters provide append-only SQLite persistence and a deterministic synthetic
canonical M1-M5 pipeline fixture. They open no network connection, load no credential, contain no
real business/person/contact data, and expose no delivery or AI adapter.

M6.7C adds a separate SQLite gate-record/work-lease adapter, an in-memory synthetic artifact store,
and scripted resolver/HTTP fakes. No socket-backed or provider-backed research transport exists.
