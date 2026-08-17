package com.toto.elementallife.ops.engines

import com.toto.elementallife.ops.api.EngineConfig
import com.toto.elementallife.ops.api.EngineHandle
import com.toto.elementallife.ops.api.NetworkEngine
import com.toto.elementallife.ops.api.ProbeResult
import com.toto.elementallife.ops.api.ProbeStatus
import java.util.UUID

/**
 * Placeholders for real native embeds (tor-android / openvpn / xray).
 * [start] does not claim a live tunnel; [health] always fails until wired.
 */
abstract class UnimplementedEngine(override val id: String) : NetworkEngine {
    override val isDebugMock: Boolean = false
    private val sessions = mutableSetOf<String>()

    override suspend fun start(config: EngineConfig): EngineHandle {
        val sid = UUID.randomUUID().toString().take(8)
        sessions.add(sid)
        return EngineHandle(engineId = id, sessionId = sid)
    }

    override suspend fun stop(handle: EngineHandle) {
        sessions.remove(handle.sessionId)
    }

    override suspend fun health(handle: EngineHandle): ProbeResult {
        return ProbeResult(
            target = "$id://health",
            via = id,
            status = ProbeStatus.Fail(
                "Engine '$id' not integrated yet — native binding pending (see EVOLUTION research)",
            ),
        )
    }
}

class TorEngineStub : UnimplementedEngine("tor")
class OpenVpnEngineStub : UnimplementedEngine("openvpn")
class V2RayEngineStub : UnimplementedEngine("v2ray")
