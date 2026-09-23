# HOT
# NetworkEngine + probe contracts

See source: `com.toto.elementallife.ops.api`

## NetworkEngine
- `start(config) -> EngineHandle`
- `stop(handle)`
- `health(handle) -> ProbeResult` — must not report Ok without real health unless `isDebugMock`

## Engines
| id | class | status |
|----|-------|--------|
| mock | MockNetworkEngine | DEBUG only, watermark in UI |
| tor | TorEngineStub | health always Fail until native bind |
| openvpn | OpenVpnEngineStub | same |
| v2ray | V2RayEngineStub | same |

## BridgeOrchestrator
evaluate → build → readiness(smp,xftp)

## Integrity
No UI claim of onion/SMP success without ProbeResult.Ok (or DEBUG mock banner).
