package com.toto.elementallife.ops

import com.toto.elementallife.ops.api.BridgeSession
import com.toto.elementallife.ops.api.EngineConfig
import com.toto.elementallife.ops.api.ProbeResult
import com.toto.elementallife.ops.api.ProbeStatus
import com.toto.elementallife.ops.api.Readiness
import com.toto.elementallife.ops.api.ScoredConfig
import com.toto.elementallife.ops.bridge.DefaultBridgeOrchestrator
import com.toto.elementallife.ops.engines.MockNetworkEngine
import com.toto.elementallife.ops.engines.OpenVpnEngineStub
import com.toto.elementallife.ops.engines.TorEngineStub
import com.toto.elementallife.ops.engines.V2RayEngineStub
import com.toto.elementallife.ops.probe.JvmConnectivityProbe
import com.toto.elementallife.ops.simplex.SimplexReachabilityProbe
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Facade for L2 ops UI: evaluate engines, build bridge, gate terminal. */
class OpsLabController(
    useMockEngine: Boolean = true,
) {
    private val probe = JvmConnectivityProbe()
    private val engines = buildMap {
        put("tor", TorEngineStub())
        put("openvpn", OpenVpnEngineStub())
        put("v2ray", V2RayEngineStub())
        if (useMockEngine) put("mock", MockNetworkEngine(succeed = true))
    }
    private val simplex = SimplexReachabilityProbe(probe)
    private val bridge = DefaultBridgeOrchestrator(engines, simplex)

    private val _log = MutableStateFlow<List<String>>(emptyList())
    val log: StateFlow<List<String>> = _log.asStateFlow()

    private val _scores = MutableStateFlow<List<ScoredConfig>>(emptyList())
    val scores: StateFlow<List<ScoredConfig>> = _scores.asStateFlow()

    private val _session = MutableStateFlow<BridgeSession?>(null)
    val session: StateFlow<BridgeSession?> = _session.asStateFlow()

    private val _readiness = MutableStateFlow<Readiness?>(null)
    val readiness: StateFlow<Readiness?> = _readiness.asStateFlow()

    private val _usingMock = MutableStateFlow(useMockEngine)
    val usingMock: StateFlow<Boolean> = _usingMock.asStateFlow()

    private fun append(msg: String) {
        _log.value = (_log.value + msg).takeLast(80)
    }

    suspend fun runEvaluation() {
        append("Evaluating engine candidates…")
        val candidates = listOf(
            EngineConfig("v2ray", "V2Ray/Xray"),
            EngineConfig("openvpn", "OpenVPN"),
            EngineConfig("tor", "Tor"),
            EngineConfig("mock", "DEBUG Mock"),
        ).filter { engines.containsKey(it.engineId) }
        val scored = bridge.evaluate(candidates)
        _scores.value = scored
        scored.forEach { s ->
            val st = s.lastProbe?.status
            append("  ${s.config.displayName}: score=${"%.1f".format(s.score)} status=$st")
        }
    }

    suspend fun buildBestBridge() {
        val chain = _scores.value.filter { it.score > 0 }.ifEmpty {
            _scores.value.take(1)
        }
        if (chain.isEmpty()) {
            append("No scored configs — run evaluation first")
            return
        }
        append("Building bridge from ${chain.map { it.config.engineId }}…")
        val session = bridge.build(chain)
        _session.value = session
        append("Bridge session ${session.id} hops=${session.hops.size} egress=${session.egress}")

        // Prefer path-through-proxy when implemented; fall back to direct probe (honest status).
        var smp = simplex.pingSmp(session.egress)
        var xftp = simplex.pingXftp(session.egress)
        if (!smp.isSuccess) {
            append("SMP via egress failed — trying direct baseline…")
            smp = simplex.pingSmp(null)
        }
        if (!xftp.isSuccess) {
            append("XFTP via egress failed — trying direct baseline…")
            xftp = simplex.pingXftp(null)
        }

        val mockOnly = session.hops.all { it.engineId == "mock" }
        val terminalEnabled = smp.isSuccess && xftp.isSuccess
        val ready = Readiness(smp = smp, xftp = xftp, terminalEnabled = terminalEnabled)
        _readiness.value = ready
        append("SMP: ${ready.smp.status}")
        append("XFTP: ${ready.xftp.status}")
        if (mockOnly) append("Note: bridge hops are DEBUG mock — not production path")
        if (ready.ready) {
            append("TERMINAL READY — chat may start (services reachable)")
        } else {
            append("Terminal gated OFF — SMP/XFTP not both reachable")
        }
    }

    suspend fun probeDirectInternet(): ProbeResult {
        append("Direct TCP probe 1.1.1.1:443…")
        val r = probe.probeTcp("1.1.1.1", 443, via = "direct")
        append("  -> ${r.status}")
        return r
    }
}
