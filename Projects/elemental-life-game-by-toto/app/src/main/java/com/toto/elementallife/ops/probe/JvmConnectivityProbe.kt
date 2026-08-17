package com.toto.elementallife.ops.probe

import com.toto.elementallife.ops.api.ConnectivityProbe
import com.toto.elementallife.ops.api.LocalProxy
import com.toto.elementallife.ops.api.ProbeResult
import com.toto.elementallife.ops.api.ProbeStatus
import com.toto.elementallife.ops.api.ProxyType
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.InetSocketAddress
import java.net.Proxy
import java.net.Socket
import java.net.URL

/** Baseline TCP/HTTP probes (direct or via local SOCKS/HTTP proxy). */
class JvmConnectivityProbe(
    private val connectTimeoutMs: Int = 5_000,
    private val readTimeoutMs: Int = 5_000,
) : ConnectivityProbe {

    override suspend fun probeTcp(host: String, port: Int, via: String): ProbeResult =
        withContext(Dispatchers.IO) {
            val start = System.currentTimeMillis()
            try {
                Socket().use { socket ->
                    socket.connect(InetSocketAddress(host, port), connectTimeoutMs)
                }
                val rtt = System.currentTimeMillis() - start
                ProbeResult(target = "$host:$port", via = via, status = ProbeStatus.Ok(rtt, "TCP connect OK"))
            } catch (t: Throwable) {
                ProbeResult(
                    target = "$host:$port",
                    via = via,
                    status = ProbeStatus.Fail(t.message ?: "TCP failed", t),
                )
            }
        }

    override suspend fun probeHttp(url: String, via: String, proxy: LocalProxy?): ProbeResult =
        withContext(Dispatchers.IO) {
            val start = System.currentTimeMillis()
            try {
                val javaProxy = proxy?.toJavaProxy()
                val conn = if (javaProxy != null) {
                    URL(url).openConnection(javaProxy)
                } else {
                    URL(url).openConnection()
                } as HttpURLConnection
                conn.connectTimeout = connectTimeoutMs
                conn.readTimeout = readTimeoutMs
                conn.requestMethod = "HEAD"
                conn.instanceFollowRedirects = true
                conn.connect()
                val code = conn.responseCode
                conn.disconnect()
                val rtt = System.currentTimeMillis() - start
                if (code in 200..399) {
                    ProbeResult(target = url, via = via, status = ProbeStatus.Ok(rtt, "HTTP $code"))
                } else {
                    ProbeResult(target = url, via = via, status = ProbeStatus.Fail("HTTP $code"))
                }
            } catch (t: Throwable) {
                ProbeResult(target = url, via = via, status = ProbeStatus.Fail(t.message ?: "HTTP failed", t))
            }
        }

    private fun LocalProxy.toJavaProxy(): Proxy {
        val type = when (this.type) {
            ProxyType.SOCKS5 -> Proxy.Type.SOCKS
            ProxyType.HTTP -> Proxy.Type.HTTP
        }
        return Proxy(type, InetSocketAddress(host, port))
    }
}
