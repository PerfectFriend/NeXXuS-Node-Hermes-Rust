# HOT
package com.toto.elementallife.ops.api

/** Shared probe / engine contracts for L2 networking lab. */

sealed class ProbeStatus {
    data object Idle : ProbeStatus()
    data class Running(val step: String) : ProbeStatus()
    data class Ok(val rttMs: Long, val detail: String) : ProbeStatus()
    data class Fail(val reason: String, val cause: Throwable? = null) : ProbeStatus()
}

data class ProbeResult(
    val target: String,
    val via: String,
    val status: ProbeStatus,
    val atEpochMs: Long = System.currentTimeMillis(),
) {
    val isSuccess: Boolean get() = status is ProbeStatus.Ok
}

data class EngineConfig(
    val engineId: String,
    val displayName: String,
    val params: Map<String, String> = emptyMap(),
)

data class EngineHandle(
    val engineId: String,
    val sessionId: String,
    val localSocksHost: String? = null,
    val localSocksPort: Int? = null,
)

data class LocalProxy(
    val host: String,
    val port: Int,
    val type: ProxyType = ProxyType.SOCKS5,
)

enum class ProxyType { SOCKS5, HTTP }

data class ScoredConfig(
    val config: EngineConfig,
    val score: Double,
    val lastProbe: ProbeResult?,
)

data class BridgeSession(
    val id: String,
    val hops: List<EngineHandle>,
    val egress: LocalProxy?,
    val builtAtMs: Long = System.currentTimeMillis(),
)

data class Readiness(
    val smp: ProbeResult,
    val xftp: ProbeResult,
    val terminalEnabled: Boolean,
) {
    val ready: Boolean get() = smp.isSuccess && xftp.isSuccess && terminalEnabled
}
