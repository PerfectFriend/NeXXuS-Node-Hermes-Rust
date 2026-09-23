# HOT
package com.toto.elementallife

import com.toto.elementallife.unlock.ControlIds
import com.toto.elementallife.unlock.UnlockEvent
import com.toto.elementallife.unlock.UnlockSequence
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UnlockSequenceTest {
    @Test
    fun sevenGreenTapsUnlocks() {
        var t = 0L
        val seq = UnlockSequence(clock = { t })
        repeat(6) {
            t += 100
            assertFalse(seq.onEvent(UnlockEvent.Tap(ControlIds.GREEN_ADJUST)))
        }
        t += 100
        assertTrue(seq.onEvent(UnlockEvent.Tap(ControlIds.GREEN_ADJUST)))
    }

    @Test
    fun timeoutResetsProgress() {
        var t = 0L
        val seq = UnlockSequence(windowMs = 1000, clock = { t })
        repeat(6) {
            t += 10
            seq.onEvent(UnlockEvent.Tap(ControlIds.GREEN_ADJUST))
        }
        t += 5000
        assertFalse(seq.onEvent(UnlockEvent.Tap(ControlIds.GREEN_ADJUST)))
    }

    @Test
    fun wrongControlDoesNotUnlock() {
        val seq = UnlockSequence(clock = { 0L })
        repeat(7) {
            assertFalse(seq.onEvent(UnlockEvent.Tap(ControlIds.PLAY)))
        }
    }
}
