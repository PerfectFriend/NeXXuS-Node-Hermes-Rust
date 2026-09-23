# HOT
package com.toto.elementallife.ops.bridge

import com.toto.elementallife.ops.api.BridgeOrchestrator
import com.toto.elementallife.ops.api.BridgeSession
import com.toto.elementallife.ops.api.EngineConfig
import com.toto.elementallife.ops.api.LocalProxy
import com.toto.elementallife.ops.api.NetworkEngine
import com.toto.elementallife.ops.api.ProbeResult
import com.toto.elementallife.ops.api.ProbeStatus
import com.toto.elementallife.ops.api.Readiness
import com.toto.elementallife.ops.api.ScoredConfig
import com.toto.elementallife.ops.api.SimplexReachability
import java.util.UUID

class DefaultBridgeOrchestrator(
    private val engines: Map<String, NetworkEngine>,
    private val simplex: SimplexReachability,
) : BridgeOrchestrator {

    override suspend fun evaluate(candidates: List<EngineConfig>): List<ScoredConfig> {
        return candidates.map { cfg ->
            val engine = engines[cfg.engineId]
            if (engine == null) {
                ScoredConfig(
                    config = cfg,
                    score = 0.0,
                    lastProbe = ProbeResult(
                        target = cfg.engineId,
                        via = "none",
                        status = ProbeStatus.Fail("Unknown engine"),
                    ),
                )
            } else {
                val handle = engine.start(cfg)
                val health = engine.health(handle)
                engine.stop(handle)
                val score = when (val s = health.status) {
                    is ProbeStatus.Ok -> 100.0 - (s.rttMs.coerceAtMost(5000) / 50.0)
                    is ProbeStatus.Fail -> 0.0
                    else -> 10.0
                }
                ScoredConfig(config = cfg, score = score, lastProbe = health)
            }
        }.sortedByDescending { it.score }
    }

    override suspend fun build(chain: List<ScoredConfig>): BridgeSession {
        val hops = mutableListOf<com.toto.elementallife.ops.api.EngineHandle>()
        var egress: LocalProxy? = null
        for (scored in chain) {
            val engine = engines[scored.config.engineId] ?: continue
            val handle = engine.start(scored.config)
            hops.add(handle)
            if (handle.localSocksPort != null && handle.localSocksHost != null) {
                egress = LocalProxy(handle.localSocksHost!!, handle.localSocksPort!!)
            }
        }
        return BridgeSession(
            id = UUID.randomUUID().toString().take(8),
            hops = hops,
            egress = egress,
        )
    }

    override suspend fun readiness(session: BridgeSession): Readiness {
        val smp = simplex.pingSmp(session.egress)
        val xftp = simplex.pingXftp(session.egress)
        val terminalEnabled = smp.isSuccess && xftp.isSuccess
        return Readiness(smp = smp, xftp = xftp, terminalEnabled = terminalEnabled)
    }
}
