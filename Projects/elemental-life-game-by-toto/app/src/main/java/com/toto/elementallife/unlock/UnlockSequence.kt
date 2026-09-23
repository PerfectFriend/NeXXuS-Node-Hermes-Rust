# HOT
package com.toto.elementallife.unlock

/**
 * UX gate: sequence of control taps within a time window opens L2 ops.
 * Not cryptographic security — mild obfuscation only.
 */
sealed class UnlockEvent {
    data class Tap(val controlId: String) : UnlockEvent()
}

class UnlockSequence(
    private val code: List<UnlockEvent> = DEFAULT_CODE,
    private val windowMs: Long = 12_000L,
    private val clock: () -> Long = { System.currentTimeMillis() },
) {
    private val buffer = ArrayDeque<Pair<UnlockEvent, Long>>()

    fun onEvent(event: UnlockEvent): Boolean {
        val now = clock()
        buffer.addLast(event to now)
        while (buffer.isNotEmpty() && now - buffer.first().second > windowMs) {
            buffer.removeFirst()
        }
        if (buffer.size > code.size) {
            // keep only latest window candidates of code length * 2
            while (buffer.size > code.size * 2) buffer.removeFirst()
        }
        return matchesSuffix()
    }

    fun reset() {
        buffer.clear()
    }

    private fun matchesSuffix(): Boolean {
        if (buffer.size < code.size) return false
        val tail = buffer.toList().takeLast(code.size)
        val start = tail.first().second
        val end = tail.last().second
        if (end - start > windowMs) return false
        return tail.map { it.first } == code
    }

    companion object {
        /** Default: 7 taps on the green adjust-dialog control (legacy). */
        val DEFAULT_CODE: List<UnlockEvent> = List(7) { UnlockEvent.Tap(ControlIds.GREEN_ADJUST) }
    }
}

object ControlIds {
    const val GREEN_ADJUST = "green_adjust"
    const val PLAY = "play"
    const val STEP = "step"
    const val PRESET_EDEN = "preset_eden"
}
