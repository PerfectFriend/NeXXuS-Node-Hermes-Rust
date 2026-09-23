# HOT
package com.toto.elementallife.ops.engines

import com.toto.elementallife.ops.api.EngineConfig
import com.toto.elementallife.ops.api.EngineHandle
import com.toto.elementallife.ops.api.NetworkEngine
import com.toto.elementallife.ops.api.ProbeResult
import com.toto.elementallife.ops.api.ProbeStatus
import kotlinx.coroutines.delay
import java.util.UUID

/**
 * DEBUG-only stand-in. UI MUST show a mock watermark when this engine is active.
 * Never use as production "success" signal.
 */
class MockNetworkEngine(
    override val id: String = "mock",
    private val succeed: Boolean = true,
    private val simulatedRttMs: Long = 42,
) : NetworkEngine {
    override val isDebugMock: Boolean = true

    private val active = mutableSetOf<String>()

    override suspend fun start(config: EngineConfig): EngineHandle {
        delay(50)
        val session = UUID.randomUUID().toString().take(8)
        active.add(session)
        return EngineHandle(
            engineId = id,
            sessionId = session,
            localSocksHost = "127.0.0.1",
            localSocksPort = 1080,
        )
    }

    override suspend fun stop(handle: EngineHandle) {
        active.remove(handle.sessionId)
    }

    override suspend fun health(handle: EngineHandle): ProbeResult {
        delay(30)
        return if (succeed && handle.sessionId in active) {
            ProbeResult(
                target = "mock://health",
                via = id,
                status = ProbeStatus.Ok(simulatedRttMs, "DEBUG mock OK — not a real tunnel"),
            )
        } else {
            ProbeResult(
                target = "mock://health",
                via = id,
                status = ProbeStatus.Fail("DEBUG mock failed or session inactive"),
            )
        }
    }
}
