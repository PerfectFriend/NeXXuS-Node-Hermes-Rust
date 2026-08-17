package com.toto.elementallife.ops.simplex

import com.toto.elementallife.ops.api.ConnectivityProbe
import com.toto.elementallife.ops.api.LocalProxy
import com.toto.elementallife.ops.api.ProbeResult
import com.toto.elementallife.ops.api.ProbeStatus
import com.toto.elementallife.ops.api.SimplexReachability

/**
 * TCP-level reachability toward configured SMP/XFTP hosts.
 * Full SMP protocol handshake lands in a later evolution cycle (real SimpleX core).
 */
class SimplexReachabilityProbe(
    private val probe: ConnectivityProbe,
    private val smpHost: String = DEFAULT_SMP_HOST,
    private val smpPort: Int = DEFAULT_SMP_PORT,
    private val xftpHost: String = DEFAULT_XFTP_HOST,
    private val xftpPort: Int = DEFAULT_XFTP_PORT,
) : SimplexReachability {

    override suspend fun pingSmp(proxy: LocalProxy?): ProbeResult {
        // Proxy-aware TCP for arbitrary hosts needs a SOCKS-capable stack;
        // for now probe direct and annotate via. Full proxy bind = next run.
        val via = proxy?.let { "proxy ${it.host}:${it.port}" } ?: "direct"
        if (proxy != null) {
            // Honest: we do not yet tunnel TCP through SOCKS here.
            return ProbeResult(
                target = "$smpHost:$smpPort",
                via = via,
                status = ProbeStatus.Fail(
                    "SMP via SOCKS not wired yet — configure direct or integrate OkHttp/SOCKS tunnel",
                ),
            )
        }
        return probe.probeTcp(smpHost, smpPort, via = via).let {
            when (val s = it.status) {
                is ProbeStatus.Ok -> it.copy(
                    status = ProbeStatus.Ok(s.rttMs, "TCP to SMP host OK (protocol handshake pending)"),
                )
                else -> it
            }
        }
    }

    override suspend fun pingXftp(proxy: LocalProxy?): ProbeResult {
        val via = proxy?.let { "proxy ${it.host}:${it.port}" } ?: "direct"
        if (proxy != null) {
            return ProbeResult(
                target = "$xftpHost:$xftpPort",
                via = via,
                status = ProbeStatus.Fail("XFTP via SOCKS not wired yet"),
            )
        }
        return probe.probeTcp(xftpHost, xftpPort, via = via).let {
            when (val s = it.status) {
                is ProbeStatus.Ok -> it.copy(
                    status = ProbeStatus.Ok(s.rttMs, "TCP to XFTP host OK (protocol handshake pending)"),
                )
                else -> it
            }
        }
    }

    companion object {
        // Public SimpleX bootstrap hosts — override via config later.
        const val DEFAULT_SMP_HOST = "smp12.simplex.im"
        const val DEFAULT_SMP_PORT = 5223
        const val DEFAULT_XFTP_HOST = "xftp.simplex.im"
        const val DEFAULT_XFTP_PORT = 443
    }
}
