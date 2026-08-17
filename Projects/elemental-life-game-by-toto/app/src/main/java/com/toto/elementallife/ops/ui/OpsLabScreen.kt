package com.toto.elementallife.ops.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.toto.elementallife.ops.OpsLabController
import com.toto.elementallife.ops.terminal.SimpleXChatScreen
import kotlinx.coroutines.launch

/**
 * L2 ops lab: evaluate engines, build bridge, readiness gate, then optional terminal.
 * DEBUG mock watermark shown when mock engine is active.
 */
@Composable
fun OpsLabScreen(
    onClose: () -> Unit,
    modifier: Modifier = Modifier,
    controller: OpsLabController = remember { OpsLabController(useMockEngine = true) },
) {
    val scope = rememberCoroutineScope()
    val log by controller.log.collectAsState()
    val scores by controller.scores.collectAsState()
    val readiness by controller.readiness.collectAsState()
    val usingMock by controller.usingMock.collectAsState()
    var busy by remember { mutableStateOf(false) }
    var showTerminal by remember { mutableStateOf(false) }

    if (showTerminal && readiness?.ready == true) {
        SimpleXChatScreen(onClose = { showTerminal = false }, modifier = modifier)
        return
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(Color(0xFF0D0D0E))
            .statusBarsPadding()
            .padding(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onClose) {
                Icon(Icons.Default.ArrowBack, contentDescription = "Back", tint = Color.White)
            }
            Column(Modifier.weight(1f)) {
                Text(
                    "OPS LAB / BRIDGE",
                    color = Color(0xFF81C784),
                    fontWeight = FontWeight.Black,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 14.sp,
                )
                Text(
                    "V2Ray · OpenVPN · Tor → SMP/XFTP gate",
                    color = Color.Gray,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace,
                )
            }
        }

        if (usingMock) {
            Card(
                modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF3E2723)),
                border = BorderStroke(1.dp, Color(0xFFFFB74D)),
            ) {
                Text(
                    "⚠ DEBUG MOCK ENGINE ACTIVE — not a real tunnel",
                    modifier = Modifier.padding(10.dp),
                    color = Color(0xFFFFB74D),
                    fontWeight = FontWeight.Bold,
                    fontSize = 11.sp,
                )
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Button(
                onClick = {
                    scope.launch {
                        busy = true
                        controller.probeDirectInternet()
                        busy = false
                    }
                },
                enabled = !busy,
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF1E2F23)),
            ) { Text("Probe net", fontSize = 11.sp, color = Color(0xFF81C784)) }

            Button(
                onClick = {
                    scope.launch {
                        busy = true
                        controller.runEvaluation()
                        busy = false
                    }
                },
                enabled = !busy,
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF1E2F23)),
            ) { Text("Evaluate", fontSize = 11.sp, color = Color(0xFF81C784)) }

            Button(
                onClick = {
                    scope.launch {
                        busy = true
                        controller.buildBestBridge()
                        busy = false
                    }
                },
                enabled = !busy,
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF1E2F23)),
            ) { Text("Bridge", fontSize = 11.sp, color = Color(0xFF81C784)) }
        }

        if (busy) {
            Spacer(Modifier.height(8.dp))
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = Color(0xFF81C784))
        }

        Spacer(Modifier.height(8.dp))
        Text("SCORES", color = Color.LightGray, fontSize = 10.sp, fontWeight = FontWeight.Bold)
        scores.forEach { s ->
            Text(
                "${s.config.engineId}: ${"%.0f".format(s.score)}  ${s.lastProbe?.status}",
                color = Color.White,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
            )
        }

        readiness?.let { r ->
            Spacer(Modifier.height(8.dp))
            Card(
                colors = CardDefaults.cardColors(containerColor = Color(0xFF141416)),
                border = BorderStroke(1.dp, if (r.ready) Color(0xFF81C784) else Color(0xFF555555)),
                shape = RoundedCornerShape(8.dp),
            ) {
                Column(Modifier.padding(10.dp)) {
                    Text(
                        if (r.ready) "READINESS: GREEN" else "READINESS: GATED",
                        color = if (r.ready) Color(0xFF81C784) else Color(0xFFFFB74D),
                        fontWeight = FontWeight.Bold,
                        fontSize = 12.sp,
                    )
                    Text("SMP: ${r.smp.status}", color = Color.LightGray, fontSize = 10.sp)
                    Text("XFTP: ${r.xftp.status}", color = Color.LightGray, fontSize = 10.sp)
                    if (r.ready) {
                        Button(
                            onClick = { showTerminal = true },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF388E3C)),
                        ) {
                            Text("Open chat terminal", color = Color.White, fontSize = 11.sp)
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(8.dp))
        Text("LOG", color = Color.LightGray, fontSize = 10.sp, fontWeight = FontWeight.Bold)
        Column(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .background(Color(0xFF070708), RoundedCornerShape(8.dp))
                .padding(8.dp),
        ) {
            log.forEach { line ->
                Text("> $line", color = Color(0xFFB0BEC5), fontSize = 9.sp, fontFamily = FontFamily.Monospace)
            }
        }
    }
}
