# HOT
package com.toto.elementallife

import com.toto.elementallife.ops.api.EngineConfig
import com.toto.elementallife.ops.api.ProbeStatus
import com.toto.elementallife.ops.engines.MockNetworkEngine
import com.toto.elementallife.ops.engines.TorEngineStub
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class OpsEngineTest {
    @Test
    fun mockEngineReportsDebugAndHealthy() = runBlocking {
        val eng = MockNetworkEngine(succeed = true)
        assertTrue(eng.isDebugMock)
        val h = eng.start(EngineConfig("mock", "Mock"))
        val health = eng.health(h)
        assertTrue(health.status is ProbeStatus.Ok)
        eng.stop(h)
        val after = eng.health(h)
        assertTrue(after.status is ProbeStatus.Fail)
    }

    @Test
    fun torStubNeverClaimsSuccess() = runBlocking {
        val eng = TorEngineStub()
        assertFalse(eng.isDebugMock)
        val h = eng.start(EngineConfig("tor", "Tor"))
        val health = eng.health(h)
        assertTrue(health.status is ProbeStatus.Fail)
    }
}
