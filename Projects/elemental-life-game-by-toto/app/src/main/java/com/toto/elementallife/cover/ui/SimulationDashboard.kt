package com.toto.elementallife.cover.ui

import androidx.compose.animation.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.toto.elementallife.cover.db.SavedPresetEntity
import com.toto.elementallife.cover.model.CellState
import com.toto.elementallife.cover.model.HexGrid
import com.toto.elementallife.cover.model.SimRules
import com.toto.elementallife.cover.viewmodel.SimulationViewModel
import com.toto.elementallife.ops.ui.OpsLabScreen
import com.toto.elementallife.unlock.ControlIds
import com.toto.elementallife.unlock.UnlockEvent
import com.toto.elementallife.unlock.UnlockSequence
import kotlinx.coroutines.delay

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SimulationDashboard(
    viewModel: SimulationViewModel,
    modifier: Modifier = Modifier
) {
    val unlockSequence = remember { UnlockSequence() }
    var showOpsLab by remember { mutableStateOf(false) }
    var onionStatusLog by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(onionStatusLog) {
        if (onionStatusLog != null) {
            delay(5000)
            onionStatusLog = null
        }
    }

    Box(modifier = Modifier.fillMaxSize()) {
    val grid by viewModel.gridState.collectAsState()
    val rules by viewModel.rulesState.collectAsState()
    val isPlaying by viewModel.isPlaying.collectAsState()
    val speedMs by viewModel.speedMs.collectAsState()
    val activeBrush by viewModel.activeBrush.collectAsState()
    val brushSize by viewModel.brushSize.collectAsState()
    val generationCount by viewModel.generationCount.collectAsState()
    val savedPresets by viewModel.savedPresets.collectAsState()

    val isPremium by viewModel.isPremium.collectAsState()
    var showBuyDialog by remember { mutableStateOf(false) }
    var activationCode by remember { mutableStateOf("") }
    var activationError by remember { mutableStateOf<String?>(null) }

    var showRulesConfig by remember { mutableStateOf(false) }
    var presetNameInput by remember { mutableStateOf("") }
    val counts = remember(grid) { grid.getElementCounts() }
    val totalCells = grid.cols * grid.rows

    // Compute Ecosystem balance diagnostics
    val (statusTitle, statusDesc) = remember(counts) {
        rules.getEcosystemStatus(
            ashesCount = counts[CellState.ASHES] ?: 0,
            earthCount = counts[CellState.EARTH] ?: 0,
            waterCount = counts[CellState.WATER] ?: 0,
            vaporCount = counts[CellState.VAPOR] ?: 0,
            fireCount = counts[CellState.FIRE] ?: 0,
            grassCount = counts[CellState.GRASS] ?: 0
        )
    }

    var showAdjustDialog by remember { mutableStateOf(false) }
    var isFullscreen by remember { mutableStateOf(false) }
    var scale by remember { mutableStateOf(1.0f) }
    var pan by remember { mutableStateOf(Offset.Zero) }

    if (showAdjustDialog) {
        AlertDialog(
            onDismissRequest = { showAdjustDialog = false },
            confirmButton = {
                Button(
                    onClick = { showAdjustDialog = false },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF388E3C))
                ) {
                    Text("DONE", fontWeight = FontWeight.Bold, color = Color.White)
                }
            },
            title = {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Icon(imageVector = Icons.Default.Tune, contentDescription = "Adjust settings", tint = Color(0xFF81C784))
                        Text(
                            text = "ECOSYSTEM ADJUSTMENTS ⚙️",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                    }

                    // Bright green unnamed button for user to tap (made very visible temporarily)
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(CircleShape)
                            .background(Color(0xFF4CAF50))
                            .clickable {
                                if (unlockSequence.onEvent(UnlockEvent.Tap(ControlIds.GREEN_ADJUST))) {
                                    unlockSequence.reset()
                                    viewModel.pauseSimulation()
                                    showAdjustDialog = false
                                    showOpsLab = true
                                }
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        // Cover UI: looks like a decorative control (unlock is gesture-coded).
                        Text(
                            text = "·",
                            color = Color.White,
                            fontWeight = FontWeight.Black,
                            fontSize = 12.sp
                        )
                    }
                }
            },
            text = {
                Column(
                    modifier = Modifier.verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    // 1. TIMING SPEED CONTROL
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(
                            text = "CLOCK DELAY SPEEDS",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF4FC3F7)
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            Text(
                                text = "Delay: ${speedMs}ms",
                                fontSize = 12.sp,
                                color = Color.LightGray,
                                modifier = Modifier.width(90.dp)
                            )
                            Slider(
                                value = speedMs.toFloat(),
                                onValueChange = { viewModel.updateSpeed(it.toLong()) },
                                valueRange = 80f..800f,
                                modifier = Modifier.weight(1f),
                                colors = SliderDefaults.colors(
                                    thumbColor = Color(0xFF42A5F5),
                                    activeTrackColor = Color(0xFF1E88E5)
                                )
                            )
                        }
                    }

                    HorizontalDivider(color = Color(0x33FFFFFF), thickness = 1.dp)

                    // 2. FIELD DIMENSIONS (Columns & Rows)
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(
                            text = "GRID SHAPE & DIMENSIONS",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF81C784)
                        )

                        var targetCols by remember(grid.cols) { mutableStateOf(grid.cols) }
                        var targetRows by remember(grid.rows) { mutableStateOf(grid.rows) }

                        // Columns control
                        Column {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "Width (Columns): $targetCols",
                                    fontSize = 12.sp,
                                    color = Color.LightGray
                                )
                                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                    IconButton(
                                        onClick = {
                                            val newCols = (targetCols - 2).coerceIn(10, 45)
                                            targetCols = newCols
                                            viewModel.updateGridSize(newCols, targetRows)
                                        },
                                        modifier = Modifier.size(28.dp).background(Color(0xFF2C2C2C), RoundedCornerShape(6.dp))
                                    ) {
                                        Text("-", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                    }
                                    IconButton(
                                        onClick = {
                                            val newCols = (targetCols + 2).coerceIn(10, 45)
                                            targetCols = newCols
                                            viewModel.updateGridSize(newCols, targetRows)
                                        },
                                        modifier = Modifier.size(28.dp).background(Color(0xFF2C2C2C), RoundedCornerShape(6.dp))
                                    ) {
                                        Text("+", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                    }
                                }
                            }
                            Slider(
                                value = targetCols.toFloat(),
                                onValueChange = { targetCols = it.toInt() },
                                onValueChangeFinished = { viewModel.updateGridSize(targetCols, targetRows) },
                                valueRange = 10f..45f,
                                colors = SliderDefaults.colors(
                                    thumbColor = Color(0xFF81C784),
                                    activeTrackColor = Color(0xFF4CAF50)
                                )
                            )
                        }

                        // Rows control
                        Column {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "Height (Rows): $targetRows",
                                    fontSize = 12.sp,
                                    color = Color.LightGray
                                )
                                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                    IconButton(
                                        onClick = {
                                            val newRows = (targetRows - 2).coerceIn(10, 45)
                                            targetRows = newRows
                                            viewModel.updateGridSize(targetCols, newRows)
                                        },
                                        modifier = Modifier.size(28.dp).background(Color(0xFF2C2C2C), RoundedCornerShape(6.dp))
                                    ) {
                                        Text("-", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                    }
                                    IconButton(
                                        onClick = {
                                            val newRows = (targetRows + 2).coerceIn(10, 45)
                                            targetRows = newRows
                                            viewModel.updateGridSize(targetCols, newRows)
                                        },
                                        modifier = Modifier.size(28.dp).background(Color(0xFF2C2C2C), RoundedCornerShape(6.dp))
                                    ) {
                                        Text("+", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                    }
                                }
                            }
                            Slider(
                                value = targetRows.toFloat(),
                                onValueChange = { targetRows = it.toInt() },
                                onValueChangeFinished = { viewModel.updateGridSize(targetCols, targetRows) },
                                valueRange = 10f..45f,
                                colors = SliderDefaults.colors(
                                    thumbColor = Color(0xFF81C784),
                                    activeTrackColor = Color(0xFF4CAF50)
                                )
                            )
                        }
                    }

                    HorizontalDivider(color = Color(0x33FFFFFF), thickness = 1.dp)

                    // 3. SEEDING & CLEARING QUICK ACTIONS
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(
                            text = "SANDBOX QUICK UTILITIES",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.LightGray
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            Button(
                                onClick = { viewModel.seedRandomGrid() },
                                modifier = Modifier.weight(1f),
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF1976D2)),
                                shape = RoundedCornerShape(8.dp),
                                contentPadding = PaddingValues(vertical = 6.dp)
                            ) {
                                Text("Seed🎲", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = Color.White)
                            }

                            Button(
                                onClick = { viewModel.clearGrid(CellState.EARTH) },
                                modifier = Modifier.weight(1f),
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF5D4037)),
                                shape = RoundedCornerShape(8.dp),
                                contentPadding = PaddingValues(vertical = 6.dp)
                            ) {
                                Text("Clear🪨", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = Color.White)
                            }

                            Button(
                                onClick = { viewModel.clearGrid(CellState.ASHES) },
                                modifier = Modifier.weight(1f),
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF37474F)),
                                shape = RoundedCornerShape(8.dp),
                                contentPadding = PaddingValues(vertical = 6.dp)
                            ) {
                                Text("Ashes🪵", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = Color.White)
                            }
                        }
                    }
                }
            },
            containerColor = Color(0xFF1E1E1E),
            shape = RoundedCornerShape(24.dp)
        )
    }

    if (isFullscreen) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xFF0F0F0F))
        ) {
            HexFieldCanvas(
                grid = grid,
                onPaintCell = { c, r ->
                    if (isPremium) {
                        viewModel.paintCell(c, r)
                    } else {
                        showBuyDialog = true
                    }
                },
                modifier = Modifier.fillMaxSize(),
                scale = scale,
                pan = pan,
                onScalePanChange = { s, p ->
                    scale = s
                    pan = p
                }
            )

            // Floating Top Info Bar
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
                    .align(Alignment.TopCenter)
                    .clickable { showAdjustDialog = true },
                colors = CardDefaults.cardColors(containerColor = Color(0xDD121212)),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.dp, Color(0x3381C784))
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = "FULLSCREEN SENSORY AREA",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Black,
                                color = Color(0xFF81C784)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Icon(
                                imageVector = Icons.Default.Tune,
                                contentDescription = "Adjust settings",
                                tint = Color(0xFF81C784),
                                modifier = Modifier.size(12.dp)
                            )
                        }
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = "Gen $generationCount | $statusTitle",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                    }
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        // Centering helper / zoom reset
                        IconButton(
                            onClick = { scale = 1.0f; pan = Offset.Zero },
                            modifier = Modifier
                                .size(36.dp)
                                .background(Color(0xFF2C2C2C), CircleShape)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Refresh,
                                contentDescription = "Reset Zoom",
                                tint = Color.LightGray,
                                modifier = Modifier.size(16.dp)
                            )
                        }
                        // Close Fullscreen Button
                        IconButton(
                            onClick = { isFullscreen = false },
                            modifier = Modifier
                                .size(36.dp)
                                .background(Color(0xFFE53935), CircleShape)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Close,
                                contentDescription = "Exit Fullscreen",
                                tint = Color.White,
                                modifier = Modifier.size(16.dp)
                            )
                        }
                    }
                }
            }

            // Floating controls on bottom
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
                    .align(Alignment.BottomCenter),
                colors = CardDefaults.cardColors(containerColor = Color(0xDD131313)),
                shape = RoundedCornerShape(20.dp),
                border = BorderStroke(1.dp, Color(0xFF2C2C2C))
            ) {
                Column(
                    modifier = Modifier.padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    // Cell size slider with touch controls (possibility of cell size change by the touch!)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Text(
                            text = "Cell Zoom: ${String.format("%.1fx", scale)}",
                            fontSize = 11.sp,
                            color = Color.LightGray,
                            modifier = Modifier.width(90.dp)
                        )
                        Slider(
                            value = scale,
                            onValueChange = { scale = it },
                            valueRange = 0.4f..5.0f,
                            modifier = Modifier.weight(1f),
                            colors = SliderDefaults.colors(
                                thumbColor = Color(0xFF42A5F5),
                                activeTrackColor = Color(0xFF1E88E5)
                            )
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            IconButton(
                                onClick = { scale = (scale - 0.2f).coerceIn(0.4f, 5.0f) },
                                modifier = Modifier.size(26.dp).background(Color(0xFF2C2C2C), RoundedCornerShape(4.dp))
                            ) {
                                Text("-", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                            }
                            IconButton(
                                onClick = { scale = (scale + 0.2f).coerceIn(0.4f, 5.0f) },
                                modifier = Modifier.size(26.dp).background(Color(0xFF2C2C2C), RoundedCornerShape(4.dp))
                            ) {
                                Text("+", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                            }
                        }
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        // Sim action buttons
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(
                                onClick = {
                                    if (isPlaying) viewModel.pauseSimulation() else viewModel.startSimulation()
                                },
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = if (isPlaying) Color(0xFFE53935) else Color(0xFF4CAF50)
                                ),
                                shape = RoundedCornerShape(8.dp),
                                contentPadding = PaddingValues(horizontal = 12.dp, vertical = 2.dp),
                                modifier = Modifier.height(32.dp)
                            ) {
                                Icon(
                                    imageVector = if (isPlaying) Icons.Default.Lock else Icons.Default.PlayArrow,
                                    contentDescription = "Simulate",
                                    tint = Color.White,
                                    modifier = Modifier.size(12.dp)
                                )
                                Spacer(modifier = Modifier.width(4.dp))
                                Text(if (isPlaying) "Pause" else "Play", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = Color.White)
                            }

                            Button(
                                onClick = { viewModel.oneStep() },
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF2E2E2E)),
                                shape = RoundedCornerShape(8.dp),
                                enabled = !isPlaying,
                                contentPadding = PaddingValues(horizontal = 12.dp, vertical = 2.dp),
                                modifier = Modifier.height(32.dp)
                            ) {
                                Text("Step ↗", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = Color.White)
                            }
                        }

                        // Brush species picker
                        Row(
                            horizontalArrangement = Arrangement.spacedBy(4.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            CellState.values().forEach { state ->
                                val isSelected = activeBrush == state
                                Box(
                                    modifier = Modifier
                                        .size(28.dp)
                                        .clip(CircleShape)
                                        .background(state.color)
                                        .border(
                                            width = if (isSelected) 2.dp else 0.dp,
                                            color = if (isSelected) Color.White else Color.Transparent,
                                            shape = CircleShape
                                        )
                                        .clickable { viewModel.setActiveBrush(state) },
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                         text = when (state) {
                                             CellState.ASHES -> "🪵"
                                             CellState.EARTH -> "🪨"
                                             CellState.WATER -> "💧"
                                             CellState.VAPOR -> "💨"
                                             CellState.FIRE -> "🔥"
                                             CellState.GRASS -> "🌱"
                                         },
                                         fontSize = 11.sp
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    } else {
        Column(
            modifier = modifier
                .fillMaxSize()
                .background(Color(0xFF121212)) // Pure deep slate black
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // --- HEADER SECTION ---
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "ELEMENTAL LIFE GAME",
                        fontSize = 20.sp,
                        fontWeight = FontWeight.Black,
                        color = Color(0xFF81C784),
                        style = MaterialTheme.typography.headlineMedium
                    )
                    Text(
                        text = "Cellular Sandbox by ToTo",
                        fontSize = 12.sp,
                        color = Color.LightGray,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF1E1E1E)),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text(
                        text = "GEN $generationCount",
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF4FC3F7),
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
                    )
                }
            }

            if (!isPremium) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { showBuyDialog = true },
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF1E1C15)),
                    shape = RoundedCornerShape(14.dp),
                    border = BorderStroke(1.5.dp, Color(0xFFFFD700))
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                            modifier = Modifier.weight(1f)
                        ) {
                            Text(text = "👑", fontSize = 24.sp)
                            Column {
                                Text(
                                    text = "ELEMENTAL LIFE - PRO",
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.Black,
                                    color = Color(0xFFFFD700)
                                )
                                Text(
                                    text = "Unlock 20+ beautiful symmetric patterns & manual brush!",
                                    fontSize = 11.sp,
                                    color = Color.LightGray
                                )
                            }
                        }
                        Button(
                            onClick = { showBuyDialog = true },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD700)),
                            shape = RoundedCornerShape(8.dp),
                            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 2.dp),
                            modifier = Modifier.height(28.dp)
                        ) {
                            Text("BUY", color = Color.Black, fontWeight = FontWeight.Black, fontSize = 11.sp)
                        }
                    }
                }
            }

            // --- ECOSYSTEM STATUS CARD ---
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { showAdjustDialog = true },
                colors = CardDefaults.cardColors(containerColor = Color(0xFF1E1E1E)),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.dp, Color(0x3381C784))
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Row(
                        modifier = Modifier.weight(1f),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Box(
                            modifier = Modifier
                                .size(48.dp)
                                .background(Color(0xFF2E2E2E), CircleShape),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(text = "🌍", fontSize = 24.sp)
                        }
                        Spacer(modifier = Modifier.width(16.dp))
                        Column {
                            Text(
                                text = statusTitle,
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color.White
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "$statusDesc (Tap to Adjust ⚙️)",
                                fontSize = 12.sp,
                                color = Color.LightGray,
                                lineHeight = 16.sp
                            )
                        }
                    }
                    Icon(
                        imageVector = Icons.Default.Tune,
                        contentDescription = "Adjust settings",
                        tint = Color(0xFF81C784),
                        modifier = Modifier
                            .padding(start = 8.dp)
                            .size(24.dp)
                    )
                }
            }

            // --- THE HEX FIELD CANVAS PANEL ---
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(2.dp, Color(0xFF2C2C2C), RoundedCornerShape(24.dp)),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF0F0F0F)),
                shape = RoundedCornerShape(24.dp)
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(8.dp),
                    contentAlignment = Alignment.Center
                ) {
                    HexFieldCanvas(
                        grid = grid,
                        onPaintCell = { c, r ->
                            if (isPremium) {
                                viewModel.paintCell(c, r)
                            } else {
                                showBuyDialog = true
                            }
                        },
                        modifier = Modifier
                            .fillMaxWidth(0.98f)
                            .aspectRatio(grid.cols.toFloat() / (grid.rows.toFloat() * 0.88f)),
                        scale = scale,
                        pan = pan,
                        onScalePanChange = { s, p ->
                            scale = s
                            pan = p
                        }
                    )
                }
            }

            // --- SANDBOX MAIN PLAY CONTROLS ---
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Button(
                    onClick = {
                        if (isPlaying) viewModel.pauseSimulation() else viewModel.startSimulation()
                    },
                    modifier = Modifier.weight(1.6f),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (isPlaying) Color(0xFFE53935) else Color(0xFF4CAF50)
                    ),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Icon(
                        imageVector = if (isPlaying) Icons.Default.Lock else Icons.Default.PlayArrow,
                        contentDescription = if (isPlaying) "Pause" else "Play",
                        tint = Color.White
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = if (isPlaying) "Pause" else "Simulate",
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                }

                Button(
                    onClick = { viewModel.oneStep() },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF2E2E2E)),
                    shape = RoundedCornerShape(12.dp),
                    enabled = !isPlaying
                ) {
                    Text(text = "Step ↗", fontWeight = FontWeight.Bold, color = Color.White)
                }

                IconButton(
                    onClick = { viewModel.resetGrid() },
                    modifier = Modifier
                        .size(44.dp)
                        .background(Color(0xFF2E2E2E), RoundedCornerShape(12.dp))
                ) {
                    Icon(imageVector = Icons.Default.Refresh, contentDescription = "Reset Grid", tint = Color.LightGray)
                }

                IconButton(
                    onClick = { isFullscreen = true },
                    modifier = Modifier
                        .size(44.dp)
                        .background(Color(0xFF2E2E2E), RoundedCornerShape(12.dp))
                ) {
                    Icon(imageVector = Icons.Default.AspectRatio, contentDescription = "Fullscreen", tint = Color.LightGray)
                }
            }

        // --- BRUSH PALETTE ENGINE (PAINTING SELECTION) ---
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "SANDBOX BRUSH TOOL",
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF81C784)
                )
                if (!isPremium) {
                    Text(
                        text = "LOCKED 🔒",
                        fontSize = 10.sp,
                        fontWeight = FontWeight.ExtraBold,
                        color = Color(0xFFFFD700)
                    )
                }
            }

            if (!isPremium) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { showBuyDialog = true },
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF1C1A14)),
                    border = BorderStroke(1.dp, Color(0x33FFD700)),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Text("✏️", fontSize = 22.sp)
                        Column {
                            Text("Drawing elements manually is premium", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFFD700))
                            Text("Touch here to unlock manual grid layout brushes!", fontSize = 10.sp, color = Color.Gray)
                        }
                    }
                }
            } else {
                // Brush Element Selector
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    CellState.values().forEach { state ->
                        val isSelected = activeBrush == state
                        val borderGlow = if (isSelected) BorderStroke(2.dp, Color.White) else null
                        
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            modifier = Modifier
                                .clickable { viewModel.setActiveBrush(state) }
                                .padding(4.dp)
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(38.dp)
                                    .clip(CircleShape)
                                    .background(state.color)
                                    .then(if (isSelected) Modifier.border(2.dp, Color.White, CircleShape) else Modifier),
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    text = when (state) {
                                        CellState.ASHES -> "🪵"
                                        CellState.EARTH -> "🪨"
                                        CellState.WATER -> "💧"
                                        CellState.VAPOR -> "💨"
                                        CellState.FIRE -> "🔥"
                                        CellState.GRASS -> "🌱"
                                    },
                                    fontSize = 16.sp
                                )
                            }
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = when (state) {
                                    CellState.ASHES -> "Ashes"
                                    CellState.EARTH -> "Earth"
                                    CellState.WATER -> "Water"
                                    CellState.VAPOR -> "Vapor"
                                    CellState.FIRE -> "Fire"
                                    CellState.GRASS -> "Grass"
                                },
                                fontSize = 10.sp,
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                color = if (isSelected) Color.White else Color.Gray
                            )
                        }
                    }
                }

                // Brush Size Selector
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "Brush radius:",
                        fontSize = 12.sp,
                        color = Color.LightGray
                    )
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        listOf(
                            Triple(1, "Single (1px)", "1"),
                            Triple(2, "Medium (7px)", "3"),
                            Triple(3, "Large (19px)", "7")
                        ).forEach { (size, label, shortLabel) ->
                            val isSelected = brushSize == size
                            Button(
                                onClick = { viewModel.setBrushSize(size) },
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = if (isSelected) Color(0xFF42A5F5) else Color(0xFF2C2C2C)
                                ),
                                contentPadding = PaddingValues(horizontal = 12.dp, vertical = 2.dp),
                                shape = RoundedCornerShape(8.dp),
                                modifier = Modifier.height(28.dp)
                            ) {
                                Text(
                                    text = label,
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color.White
                                )
                            }
                        }
                    }
                }
            }
        }

        // --- PRESET WORLD GENERATORS ---
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = "FREE WORLD PRESET ARCHETYPES",
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF81C784)
            )

            LazyRow(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                val presetsList = listOf(
                    Triple("eden", "Balanced Eden 🌿", "Sustainable loop"),
                    Triple("fire", "Forest Fire 🔥", "Combustible spread"),
                    Triple("lake", "Great Lake 🌊", "Aggressive lakes"),
                    Triple("oasis", "Rain Oasis 🌧️", "Vapor clouds"),
                    Triple("volcano", "Magma Springs 🌋", "Volcanic vapor")
                )
                items(presetsList) { (key, title, subtitle) ->
                    Card(
                        modifier = Modifier
                            .width(150.dp)
                            .clickable { viewModel.loadPreset(key) },
                        colors = CardDefaults.cardColors(containerColor = Color(0xFF1E1E1E)),
                        shape = RoundedCornerShape(12.dp),
                        border = BorderStroke(1.dp, Color(0xFF2C2C2C))
                    ) {
                        Column(
                            modifier = Modifier.padding(12.dp)
                        ) {
                            Text(text = title, fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color.White)
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(text = subtitle, fontSize = 10.sp, color = Color.Gray)
                        }
                    }
                }
            }
        }

        // --- PREMIUM SYMMETRIC ARCHETYPES (20+) ---
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "👑 PREMIUM SYMMETRIC ARCHETYPES (+20)",
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFFFFD700)
                )
                if (!isPremium) {
                    Text(
                        text = "PRO 🔒",
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Black,
                        color = Color(0xFFFFD700),
                        modifier = Modifier
                            .background(Color(0xFF2F2515), RoundedCornerShape(4.dp))
                            .border(1.dp, Color(0xFFFFD700), RoundedCornerShape(4.dp))
                            .padding(horizontal = 6.dp, vertical = 2.dp)
                    )
                }
            }

            LazyRow(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                val premiumPresetsList = listOf(
                    Triple("ring", "Radial Pulse Ring ⭕", "Concentric wave orbits"),
                    Triple("spiral", "Cosmic Spiral Leaf 🌀", "Swirling designs"),
                    Triple("stellar", "Pulsar Star 🌟", "Alternating energy arms"),
                    Triple("yinyang", "Yin-Yang Balance ☯️", "Perfect dual weight"),
                    Triple("snowflake", "Hex Snowflake ❄️", "6-fold ice lattice"),
                    Triple("cross", "Cross of Flames ✝️", "Fiery axes grid"),
                    Triple("mandala", "Sacred Mandala 💮", "Harmonic geometric loop"),
                    Triple("concentric", "Harmonic Ripples 🌊", "Overlapping water waves"),
                    Triple("portal", "Star Portal 🌌", "Central nexus gateway"),
                    Triple("tessellation", "Honeycomb Chess 🏁", "Periodic tile board"),
                    Triple("nexus", "Elemental Nexus 💎", "8 symmetric spokes"),
                    Triple("aurora", "Aurora Horizon 🌅", "Wavy vapor ribbons"),
                    Triple("shield", "Shield Rings 🛡️", "Forcefield defense layers"),
                    Triple("trinity", "Trinity Force 🔺", "Symmetric triple core"),
                    Triple("cosmic", "Cosmic Egg 🥚", "Concentrated mass core"),
                    Triple("crystal", "Crystal Lattice 💎", "Repeated hex clusters"),
                    Triple("lava", "Lava Chamber 🌋", "Bubbling symmetric magma"),
                    Triple("spiral_cloud", "Cloud Whirlwind 💨", "Splay vapor vortex"),
                    Triple("emerald", "Emerald Palace 🏰", "Hexagonal grass castle"),
                    Triple("phoenix", "Ashes Phoenix 🦅", "Symmetric bird of fire")
                )

                items(premiumPresetsList) { (key, title, subtitle) ->
                    Card(
                        modifier = Modifier
                            .width(165.dp)
                            .clickable {
                                if (isPremium) {
                                    viewModel.loadPreset(key)
                                } else {
                                    showBuyDialog = true
                                }
                            },
                        colors = CardDefaults.cardColors(
                            containerColor = if (isPremium) Color(0xFF1E1E1E) else Color(0x771E1E1E)
                        ),
                        shape = RoundedCornerShape(12.dp),
                        border = BorderStroke(1.dp, if (isPremium) Color(0xFF42A5F5) else Color(0x33FFD700))
                    ) {
                        Column(
                            modifier = Modifier.padding(12.dp)
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = title, 
                                    fontSize = 12.sp, 
                                    fontWeight = FontWeight.Bold, 
                                    color = if (isPremium) Color.White else Color.LightGray,
                                    modifier = Modifier.weight(1f)
                                )
                                if (!isPremium) {
                                    Icon(
                                        imageVector = Icons.Default.Lock, 
                                        contentDescription = "Locked", 
                                        tint = Color(0xFFFFD700),
                                        modifier = Modifier.size(12.dp)
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(text = subtitle, fontSize = 10.sp, color = Color.Gray)
                        }
                    }
                }
            }
        }

        // --- REAL TIME ELEMENTS COUNTER PILLS ---
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = Color(0xFF161616)),
            shape = RoundedCornerShape(16.dp),
            border = BorderStroke(1.dp, Color(0xFF2C2C2C))
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text(
                    text = "REAL-TIME SPECIES STATUS",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.LightGray
                )

                // Render horizontal bars representing density
                counts.forEach { (state, count) ->
                    val pct = if (totalCells > 0) count.toFloat() / totalCells else 0f
                    val formattedPct = String.format("%.1f%%", pct * 100)

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text(
                            text = when (state) {
                                CellState.ASHES -> "🪵"
                                CellState.EARTH -> "🪨"
                                CellState.WATER -> "💧"
                                CellState.VAPOR -> "💨"
                                CellState.FIRE -> "🔥"
                                CellState.GRASS -> "🌱"
                            } + " " + state.displayName,
                            fontSize = 11.sp,
                            color = Color.White,
                            modifier = Modifier.width(100.dp)
                        )
                        Box(
                            modifier = Modifier
                                .weight(1f)
                                .height(6.dp)
                                .clip(RoundedCornerShape(3.dp))
                                .background(Color(0xFF2C2C2C))
                        ) {
                            Box(
                                modifier = Modifier
                                    .fillMaxHeight()
                                    .fillMaxWidth(pct)
                                    .background(state.color)
                            )
                        }
                        Text(
                            text = "$count ($formattedPct)",
                            fontSize = 11.sp,
                            color = Color.LightGray,
                            textAlign = TextAlign.End,
                            modifier = Modifier.width(70.dp)
                        )
                    }
                }
            }
        }

        // --- ROOM CUSTOM PRESETS SAVER / LOADERS ---
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "PERSISTENT CUSTOM SANDBOXES",
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF81C784)
                )
                if (!isPremium) {
                    Icon(
                        imageVector = Icons.Default.Lock, 
                        contentDescription = "Locked", 
                        tint = Color(0xFFFFD700),
                        modifier = Modifier.size(12.dp)
                    )
                }
            }

            if (!isPremium) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { showBuyDialog = true },
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF1C1B17)),
                    border = BorderStroke(1.dp, Color(0x33FFD700)),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text("💾", fontSize = 20.sp)
                        Column {
                            Text("Simulated Layout Saving Locked", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFFD700))
                            Text("Saving custom arrangements requires PRO. Tap to purchase full version!", fontSize = 10.sp, color = Color.Gray)
                        }
                    }
                }
            } else {
                // Save Field Input
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    OutlinedTextField(
                        value = presetNameInput,
                        onValueChange = { presetNameInput = it },
                        placeholder = { Text("E.g. Dry Highlands", fontSize = 12.sp) },
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(12.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = Color(0xFF4caf50),
                            unfocusedBorderColor = Color(0xFF2c2c2c),
                            focusedContainerColor = Color(0xFF1E1E1E),
                            unfocusedContainerColor = Color(0xFF1E1E1E)
                        ),
                        maxLines = 1
                    )
                    Button(
                        onClick = {
                            viewModel.saveCustomPreset(presetNameInput.trim())
                            presetNameInput = ""
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF388E3C)),
                        shape = RoundedCornerShape(12.dp),
                        contentPadding = PaddingValues(horizontal = 16.dp)
                    ) {
                        Text("Save", fontWeight = FontWeight.Bold, color = Color.White)
                    }
                }

                // Load Saved list
                if (savedPresets.isNotEmpty()) {
                    LazyRow(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(savedPresets) { item ->
                            Card(
                                modifier = Modifier
                                    .width(160.dp)
                                    .clickable { viewModel.loadCustomPreset(item) },
                                colors = CardDefaults.cardColors(containerColor = Color(0xFF1E1E1E)),
                                shape = RoundedCornerShape(12.dp),
                                border = BorderStroke(1.dp, Color(0x3342A5F5))
                            ) {
                                Column(
                                    modifier = Modifier.padding(10.dp)
                                ) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(
                                            text = item.name,
                                            fontSize = 12.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = Color.White,
                                            modifier = Modifier.weight(1f)
                                        )
                                        IconButton(
                                            onClick = { viewModel.deleteCustomPreset(item) },
                                            modifier = Modifier.size(24.dp)
                                        ) {
                                            Icon(
                                                imageVector = Icons.Default.Delete,
                                                contentDescription = "Delete Preset",
                                                tint = Color.Gray,
                                                modifier = Modifier.size(14.dp)
                                            )
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(
                                        text = "Tap to load sandbox",
                                        fontSize = 9.sp,
                                        color = Color.LightGray
                                    )
                                }
                            }
                        }
                    }
                } else {
                    Text(
                        text = "No saved sandboxes yet. Arrange some elements and hit Save!",
                        fontSize = 11.sp,
                        color = Color.Gray,
                        modifier = Modifier.padding(vertical = 4.dp)
                    )
                }
            }
        }

        // --- EXPANDABLE ELEMENTAL RULES TUNER (SLIDERS) ---
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = Color(0xFF131313)),
            shape = RoundedCornerShape(16.dp),
            border = BorderStroke(1.dp, Color(0xFF2C2C2C))
        ) {
            Column(
                modifier = Modifier.padding(16.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { showRulesConfig = !showRulesConfig },
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(imageVector = Icons.Default.Settings, contentDescription = "Rules icon", tint = Color(0xFF81C784))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "CUSTOM PHYSICS ENGINE RULES",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                    }
                    Text(
                        text = if (showRulesConfig) "Hide ▲" else "Tune ▼",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF42A5F5)
                    )
                }

                AnimatedVisibility(visible = showRulesConfig) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        RuleSlider(
                            label = "Fire Spread Speed",
                            description = "How fast fire consumes adjacent dry grass.",
                            value = rules.fireSpreadChance,
                            onValueChange = { viewModel.updateRule { r -> r.copy(fireSpreadChance = it) } }
                        )

                        RuleSlider(
                            label = "Water-Fire Mutuality Rate",
                            description = "Probability water & fire both transform on contact (water -> air/vapor, fire -> earth).",
                            value = rules.fireExtinguishChance,
                            onValueChange = { viewModel.updateRule { r -> r.copy(fireExtinguishChance = it) } }
                        )

                        RuleSlider(
                            label = "Fire Natural Burnout",
                            description = "Probability fire burns itself out to ashes without water.",
                            value = rules.fireBurnoutChance,
                            onValueChange = { viewModel.updateRule { r -> r.copy(fireBurnoutChance = it) } }
                        )

                        RuleSlider(
                            label = "Grass Spreading Growth",
                            description = "Chance grass re-seeds to adjacent earth or ashes.",
                            value = rules.grassGrowChance,
                            onValueChange = { viewModel.updateRule { r -> r.copy(grassGrowChance = it) } }
                        )

                        RuleSlider(
                            label = "Spontaneous Combustion Rate",
                            description = "How quickly dry grass catches fire under water starvation.",
                            value = rules.grassDieNoWaterChance,
                            onValueChange = { viewModel.updateRule { r -> r.copy(grassDieNoWaterChance = it) } }
                        )

                        RuleSlider(
                            label = "Grass Transpiration Humidity",
                            description = "Chance wet grass vaporizes adjacent water to generate air clouds.",
                            value = rules.grassTranspireChance,
                            onValueChange = { viewModel.updateRule { r -> r.copy(grassTranspireChance = it) } }
                        )

                        RuleSlider(
                            label = "Vapor Rain/Condensation",
                            description = "How easily vapor clouds precipitate back into liquid water.",
                            value = rules.vaporCondenseChance,
                            onValueChange = { viewModel.updateRule { r -> r.copy(vaporCondenseChance = it) } }
                        )

                        RuleSlider(
                            label = "Vapor Wind-Drift Speed",
                            description = "How aggressively clouds drift across empty hexes.",
                            value = rules.vaporDriftChance,
                            onValueChange = { viewModel.updateRule { r -> r.copy(vaporDriftChance = it) } }
                        )

                        RuleSlider(
                            label = "Water Lake Aggregation (Flow)",
                            description = "Chance isolated water flows together to create deep lakes.",
                            value = rules.waterClumpChance,
                            onValueChange = { viewModel.updateRule { r -> r.copy(waterClumpChance = it) } }
                        )

                        Button(
                            onClick = { viewModel.resetRulesToDefault() },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF2C2C2C)),
                            modifier = Modifier.align(Alignment.CenterHorizontally),
                            shape = RoundedCornerShape(10.dp)
                        ) {
                            Text("Reset Physics to Equilibrium Defaults", fontSize = 11.sp, color = Color.White)
                        }
                    }
                }
            }
        }
    }

    // --- MONETIZATION DUAL-STAGE PURCHASE GATEWAY DIALOG ---
    if (showBuyDialog) {
        AlertDialog(
            onDismissRequest = { showBuyDialog = false },
            confirmButton = {},
            dismissButton = {
                TextButton(onClick = { showBuyDialog = false }) {
                    Text("CLOSE", color = Color.Gray, fontWeight = FontWeight.Bold)
                }
            },
            title = {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Text("👑 ELEMENTAL PRO 👑", fontSize = 19.sp, fontWeight = FontWeight.Black, color = Color(0xFFFFD700))
                    Text("Full Cellular Automata Power by ToTo", fontSize = 11.sp, color = Color.Gray)
                }
            },
            text = {
                Column(
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                    modifier = Modifier.verticalScroll(rememberScrollState())
                ) {
                    Text(
                        text = "Take complete control of the simulated ecosystem with premium tools:",
                        fontSize = 12.sp,
                        color = Color.White
                    )
                    
                    val features = listOf(
                        "✏️ Manual Canvas Draw Brush: Draw water, grass, fire, vapor, earth, or embers anywhere!",
                        "🌀 +20 Symmetrical Masterpieces: Instant snowflake, yin-yang, cosmic egg, and sacred mandala configurations.",
                        "💾 Infinite Persistence: Save, name, and restore custom sandboxes directly to the device database.",
                        "⚙️ Sandbox Physics: Fully customize rule probabilities & select brush size ranges.",
                        "💎 Absolute computational efficiency with high-density grids."
                    )
                    
                    features.forEach { feature ->
                        Row(
                            verticalAlignment = Alignment.Top,
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            Text("✨", fontSize = 11.sp, color = Color(0xFFFFD700))
                            Text(feature, fontSize = 11.sp, color = Color.LightGray)
                        }
                    }
                    
                    Spacer(modifier = Modifier.height(4.dp))

                    Button(
                        onClick = {
                            viewModel.unlockPremium(true)
                            showBuyDialog = false
                        },
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD700)),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Icon(imageVector = Icons.Default.ShoppingCart, contentDescription = "Simulate payment", tint = Color.Black)
                            Text("1-TAP SIMULATE PURCHASE ($1.99)", color = Color.Black, fontWeight = FontWeight.Black, fontSize = 12.sp)
                        }
                    }

                    HorizontalDivider(color = Color(0x33FFFFFF), thickness = 1.dp)

                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(
                            text = "Or Decrypt Secret Promo / Dev Passcode:",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF81C784)
                        )
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            OutlinedTextField(
                                value = activationCode,
                                onValueChange = { 
                                    activationCode = it
                                    activationError = null
                                },
                                placeholder = { Text("E.g. ToTo", fontSize = 11.sp, color = Color.Gray) },
                                modifier = Modifier.weight(1f),
                                maxLines = 1,
                                shape = RoundedCornerShape(8.dp),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedBorderColor = Color(0xFF81C784),
                                    unfocusedBorderColor = Color(0xFF2C2C2C),
                                    focusedContainerColor = Color(0xFF1E1E1E),
                                    unfocusedContainerColor = Color(0xFF1E1E1E)
                                )
                            )
                            Button(
                                onClick = {
                                    val code = activationCode.trim().lowercase()
                                    if (code == "toto" || code == "elemental" || code == "pro" || code == "premium" || code == "free") {
                                        viewModel.unlockPremium(true)
                                        showBuyDialog = false
                                    } else {
                                        activationError = "Invalid code. Tip: Try 'ToTo'!"
                                    }
                                },
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF388E3C)),
                                shape = RoundedCornerShape(8.dp),
                                modifier = Modifier.height(40.dp)
                            ) {
                                Text("DECRYPT", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = Color.White)
                            }
                        }
                        if (activationError != null) {
                            Text(activationError!!, fontSize = 10.sp, color = Color(0xFFFF5252))
                        }
                    }
                }
            },
            containerColor = Color(0xFF1E1E1E),
            shape = RoundedCornerShape(24.dp)
        )
    }
}

    if (showOpsLab) {
        OpsLabScreen(
            onClose = {
                showOpsLab = false
                onionStatusLog = "Ops lab closed. Cover simulation resumed."
            },
            modifier = Modifier.fillMaxSize()
        )
    }

    // Floating Onion Disconnect Toast/Overlay Notification
    AnimatedVisibility(
        visible = onionStatusLog != null,
        enter = slideInVertically(initialOffsetY = { it / 2 }) + fadeIn(),
        exit = slideOutVertically(targetOffsetY = { it / 2 }) + fadeOut(),
        modifier = Modifier
            .align(Alignment.BottomCenter)
            .padding(16.dp)
            .navigationBarsPadding()
    ) {
        onionStatusLog?.let { msg ->
            Card(
                colors = CardDefaults.cardColors(containerColor = Color(0xFF0F1512)),
                border = BorderStroke(1.5.dp, Color(0xFF4CAF50)),
                shape = RoundedCornerShape(12.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 8.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .widthIn(max = 450.dp)
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(CircleShape)
                            .background(Color(0xFF1E2F23)),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("🧅", fontSize = 18.sp)
                    }
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "SIMPLEX PROCESS LOGS",
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Black,
                            color = Color(0xFF4CAF50),
                            fontFamily = FontFamily.Monospace
                        )
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = msg,
                            color = Color.White,
                            fontSize = 11.sp,
                            lineHeight = 15.sp
                        )
                    }
                    IconButton(
                        onClick = { onionStatusLog = null },
                        modifier = Modifier.size(24.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Close log",
                            tint = Color.Gray,
                            modifier = Modifier.size(16.dp)
                        )
                    }
                }
            }
        }
    }
}
}

@Composable
private fun RuleSlider(
    label: String,
    description: String,
    value: Float,
    onValueChange: (Float) -> Unit
) {
    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(text = label, fontSize = 12.sp, fontWeight = FontWeight.Bold, color = Color.White)
            Text(text = String.format("%.0f%%", value * 100), fontSize = 12.sp, fontWeight = FontWeight.Bold, color = Color(0xFF4FC3F7))
        }
        Text(text = description, fontSize = 10.sp, color = Color.Gray, lineHeight = 14.sp)
        Spacer(modifier = Modifier.height(2.dp))
        Slider(
            value = value,
            onValueChange = onValueChange,
            valueRange = 0.0f..1.0f,
            colors = SliderDefaults.colors(
                thumbColor = Color(0xFF81C784),
                activeTrackColor = Color(0xFF4CAF50)
            )
        )
    }
}
