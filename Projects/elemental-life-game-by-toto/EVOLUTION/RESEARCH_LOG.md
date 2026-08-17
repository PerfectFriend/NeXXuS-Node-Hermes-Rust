# Research log

Append-only. Cap: ≤3 primary sources per evolution cycle.

## 2026-07-17 — Bootstrap (pre-run)

### Target stacks
- Tor (mobile): Orbot APIs, tor-android, Arti Android readiness — TBD cycle research
- OpenVPN: ics-openvpn / OpenVPN3 for Android patterns
- V2Ray/Xray: v2rayNG architecture, libv2ray / xray-core mobile
- SimpleX: SMP + XFTP official protocol/client libraries (must be real, not UI cosplay)
- Local proxy chaining: SOCKS5 listen + OkHttp/Cronet via proxy

### Decision
Implement `NetworkEngine` interface first; spike one engine at a time; never claim success without probe.

## 2026-07-17-R1 — Build toolchain

### Finding
- Host `gradle` chocolatey + JDK11 fails; AGP 9.1.1 needs Gradle ≥9.3.1 and modern JVM.
- Android Studio JBR 21 works.
- Wrapper distributionUrl → gradle-9.3.1-bin.zip.

### Decision
Pin wrapper 9.3.1; document JAVA_HOME to Android Studio JBR for CLI builds.

## 2026-07-17-R1 — Engine strategy (no deep web crawl; prior knowledge + deferred)

### Options considered
1. Full native AAR embeds now — high risk, long cycle, blocks dual-layer shell.
2. Stub engines + real probe/readiness pipeline — tracer bullet.
3. Ship mock-only cosplay — rejected (integrity rule).

### Decision
Option 2 adopted for R1. Real embeds = R2 primary backlog (B009–B011 real).
