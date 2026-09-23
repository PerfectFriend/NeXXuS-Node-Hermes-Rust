# HOT
# Frozen registry

Rules: see Hermes skill `autonomous-evolution`.

| path | frozen_at_cycle | interface | tests | notes |
|------|-----------------|-----------|-------|-------|
| app/src/main/java/com/toto/elementallife/unlock/UnlockSequence.kt | 20 | interfaces/unlock.md | UnlockSequenceTest | pure JVM |
| app/src/main/java/com/toto/elementallife/ops/api/ProbeModels.kt | 20 | interfaces/network-engine.md | OpsEngineTest (indirect) | data models |
| app/src/main/java/com/toto/elementallife/ops/api/NetworkEngine.kt | 20 | interfaces/network-engine.md | OpsEngineTest | interfaces only |
| app/src/main/java/com/toto/elementallife/ops/engines/MockNetworkEngine.kt | 20 | interfaces/network-engine.md | OpsEngineTest | DEBUG only |

## COLD (next run)

- [FROZEN] cover/* (game) — freeze after more deterministic sim tests (frozen at cycle 20)
- ops/engines/*Stub — replace with real embeds
- ops/simplex/* — SOCKS-aware + protocol handshake
- ops/terminal/SimpleXChatScreen — still prototype UI
- cover/ui/SimulationDashboard — monolith
