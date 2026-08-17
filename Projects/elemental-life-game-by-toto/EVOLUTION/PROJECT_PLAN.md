# Project Plan — Elemental Life + Ops Terminal (dual-layer)

## Vision

**L1 Cover:** Hexagonal elemental ecosystem game.

**Unlock:** `UnlockSequence` (default 7× green_adjust within 12s) → L2 Ops Lab.

**L2 Ops:** Evaluate V2Ray/OpenVPN/Tor stubs + DEBUG mock → bridge session → SMP/XFTP TCP readiness → terminal gate.

**Integrity:** No success without ProbeResult (mock shows watermark).

## Decisions

- 2026-07-17: Dual-layer roadmap; skill autonomous-evolution.
- 2026-07-17-R1: Package root `com.toto.elementallife` with cover/unlock/ops split.
- 2026-07-17-R1: Gradle wrapper 9.3.1 (AGP 9.1.1 requires ≥9.3.1); JDK 21 via Android Studio JBR.
- 2026-07-17-R1: Engines as stubs first; mock DEBUG-only for pipeline wiring.
- 2026-07-17-R1: SimRules sliders now wired into HexGrid fire/vapor paths.
- 2026-07-17-R1: Stripped Retrofit/Moshi/Firebase BOM; kept Camera/OkHttp.

## Backlog

| id | item | layer | effort | status | notes |
|----|------|-------|--------|--------|-------|
| B001 | Bootstrap EVOLUTION | shared | S | done | |
| B002 | Gradle wrapper + applicationId/namespace | shared | S | done | gradlew 9.3.1; com.toto.elementallife |
| B003 | Package split cover/unlock/ops/shared | shared | L | done | packages (not Gradle modules) |
| B004 | UnlockSequence + wire entry | unlock | M | done | OpsLabScreen |
| B005 | NetworkEngine + ProbeResult APIs | ops | M | done | |
| B006 | DEBUG MockNetworkEngine + watermark | ops | S | done | OpsLabScreen banner |
| B007 | Strip unused deps | shared | S | done | retrofit/moshi/firebase gone |
| B008 | Local TCP/HTTP probe | ops | M | done | JvmConnectivityProbe |
| B009 | Tor engine spike | ops | L | partial | TorEngineStub (no native yet) |
| B010 | OpenVPN engine spike | ops | L | partial | OpenVpnEngineStub |
| B011 | V2Ray engine spike | ops | L | partial | V2RayEngineStub |
| B012 | BridgeOrchestrator | ops | L | done | DefaultBridgeOrchestrator + controller |
| B013 | SMP reachability | ops | M | partial | TCP only; SOCKS pending |
| B014 | XFTP reachability | ops | M | partial | TCP only |
| B015 | Readiness gate + notify | ops | S | done | UI readiness card |
| B016 | Terminal gated on readiness | ops | M | partial | opens legacy SimpleX UI when green |
| B017 | Cover freeze | cover | M | partial | APIs frozen; cover HOT |
| B018 | Wire SimRules | cover | M | done | fire/vapor/burnout/extinguish |
| B019 | Real billing | cover | M | deferred | product decision |
| B020 | Manifest INTERNET | ops | S | done | |

## Done this run (R1)

B001–B008, B012, B015, B018, B020; partial B009–B011, B013–B014, B016–B017.

## Next run recommendation

1. Real Tor/OpenVPN/V2Ray native embeds (research Orbot / ics-openvpn / libv2ray).
2. SOCKS-aware ConnectivityProbe (OkHttp).
3. Real SimpleX core for SMP/XFTP beyond TCP.
4. Split SimulationDashboard; freeze cover model after golden tests.
5. Product decision on PRO billing.
