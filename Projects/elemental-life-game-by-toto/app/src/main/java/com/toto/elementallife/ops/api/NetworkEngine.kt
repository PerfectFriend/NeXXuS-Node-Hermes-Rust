# HOT
package com.toto.elementallife.ops.api

/**
 * Pluggable tunnel / proxy engine (Tor, OpenVPN, V2Ray, mock…).
 * Implementations must never report success without a real health probe
 * unless [isDebugMock] is true (DEBUG watermark required in UI).
 */
interface NetworkEngine {
    val id: String
    val isDebugMock: Boolean get() = false

    suspend fun start(config: EngineConfig): EngineHandle
    suspend fun stop(handle: EngineHandle)
    suspend fun health(handle: EngineHandle): ProbeResult
}

interface BridgeOrchestrator {
    suspend fun evaluate(candidates: List<EngineConfig>): List<ScoredConfig>
    suspend fun build(chain: List<ScoredConfig>): BridgeSession
    suspend fun readiness(session: BridgeSession): Readiness
}

interface SimplexReachability {
    suspend fun pingSmp(proxy: LocalProxy?): ProbeResult
    suspend fun pingXftp(proxy: LocalProxy?): ProbeResult
}

interface ConnectivityProbe {
    /** TCP connect + optional TLS/HTTP HEAD. */
    suspend fun probeTcp(host: String, port: Int, via: String = "direct"): ProbeResult
    suspend fun probeHttp(url: String, via: String = "direct", proxy: LocalProxy? = null): ProbeResult
}
