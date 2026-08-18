# Activation Core

M6.5 owns immutable launch-envelope, policy, decision, attestation, certification, readiness, and
zero-send shadow-assessment contracts. It deterministically explains activation blockers.

It does not own or mutate M1-M6 records, provision infrastructure, interpret law, collect real
data, resolve contacts, authorize sends, call providers, or expose a delivery port.

Public interfaces are the typed domain records and `ActivationReadinessService`. Persistence is
provided through the `ActivationRepository` port.
