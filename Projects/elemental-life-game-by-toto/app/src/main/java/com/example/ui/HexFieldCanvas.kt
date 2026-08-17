package com.example.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.isSpecified
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import com.example.model.CellState
import com.example.model.HexGrid
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

@Composable
fun HexFieldCanvas(
    grid: HexGrid,
    onPaintCell: (col: Int, row: Int) -> Unit,
    modifier: Modifier = Modifier,
    scale: Float = 1f,
    pan: Offset = Offset.Zero,
    onScalePanChange: ((Float, Offset) -> Unit)? = null
) {
    val cols = grid.cols
    val rows = grid.rows

    val currentOnPaintCell by rememberUpdatedState(onPaintCell)

    Canvas(
        modifier = modifier
            .fillMaxSize()
            .pointerInput(cols, rows, scale, pan) {
                awaitEachGesture {
                    var isZooming = false
                    val down = awaitFirstDown(requireUnconsumed = false)
                    
                    val w = size.width.toFloat()
                    val h = size.height.toFloat()
                    
                    while (true) {
                        val event = awaitPointerEvent()
                        val activeChanges = event.changes.filter { it.pressed }
                        
                        if (activeChanges.isEmpty()) {
                            break
                        }
                        
                        if (activeChanges.size > 1 && onScalePanChange != null) {
                            isZooming = true
                            
                            val p1 = activeChanges[0]
                            val p2 = activeChanges[1]
                            
                            val prevDiff = p1.previousPosition - p2.previousPosition
                            val currDiff = p1.position - p2.position
                            
                            val distPrev = kotlin.math.sqrt(prevDiff.x * prevDiff.x + prevDiff.y * prevDiff.y)
                            val distCurrent = kotlin.math.sqrt(currDiff.x * currDiff.x + currDiff.y * currDiff.y)
                            
                            val centroidPrev = (p1.previousPosition + p2.previousPosition) / 2f
                            val centroidCurrent = (p1.position + p2.position) / 2f
                            
                            var newScale = scale
                            if (distPrev > 0f) {
                                val zoomFactor = distCurrent / distPrev
                                newScale = (scale * zoomFactor).coerceIn(0.4f, 8.0f)
                            }
                            
                            val panDelta = centroidCurrent - centroidPrev
                            val newPanUnconstrained = pan + panDelta
                            
                            val maxPanX = (w / 2f) * kotlin.math.max(0f, newScale - 1f)
                            val maxPanY = (h / 2f) * kotlin.math.max(0f, newScale - 1f)
                            val newPan = Offset(
                                newPanUnconstrained.x.coerceIn(-maxPanX, maxPanX),
                                newPanUnconstrained.y.coerceIn(-maxPanY, maxPanY)
                            )
                            
                            onScalePanChange(newScale, newPan)
                            
                            activeChanges.forEach { it.consume() }
                        } else if (activeChanges.size == 1) {
                            if (!isZooming) {
                                val change = activeChanges.first()
                                val maxPanX = (w / 2f) * kotlin.math.max(0f, scale - 1f)
                                val maxPanY = (h / 2f) * kotlin.math.max(0f, scale - 1f)
                                val constrainedPan = Offset(
                                    pan.x.coerceIn(-maxPanX, maxPanX),
                                    pan.y.coerceIn(-maxPanY, maxPanY)
                                )
                                val mappedPos = Offset(
                                    (change.position.x - constrainedPan.x - w / 2f) / scale + w / 2f,
                                    (change.position.y - constrainedPan.y - h / 2f) / scale + h / 2f
                                )
                                detectAndPaintHex(
                                    mappedPos,
                                    w,
                                    h,
                                    cols,
                                    rows,
                                    currentOnPaintCell
                                )
                                change.consume()
                            }
                        }
                    }
                }
            }
    ) {
        val width = size.width
        val height = size.height
        
        val maxPanX = (width / 2f) * kotlin.math.max(0f, scale - 1f)
        val maxPanY = (height / 2f) * kotlin.math.max(0f, scale - 1f)
        val constrainedPan = Offset(
            pan.x.coerceIn(-maxPanX, maxPanX),
            pan.y.coerceIn(-maxPanY, maxPanY)
        )
        
        drawContext.transform.translate(constrainedPan.x, constrainedPan.y)
        drawContext.transform.scale(scale, scale, pivot = Offset(width / 2f, height / 2f))

        val path = Path()

        // Calculate maximum fitting radius
        // horizontal_space = (cols + 0.5) * sqrt(3) * r
        // vertical_space = (rows * 1.5 + 0.5) * r
        val extColSpan = cols + 0.5f
        val extRowSpan = rows * 0.75f + 0.25f // 1.5 / 2 = 0.75 spacing factor
        
        val rFromWidth = width / (extColSpan * sqrt(3f))
        val rFromHeight = height / (extRowSpan * 2f)
        val radius = Math.min(rFromWidth, rFromHeight) * 0.96f // slightly smaller for margins

        val colSpacing = sqrt(3f) * radius
        val rowSpacing = 1.5f * radius

        val gridOriginX = (width - extColSpan * colSpacing) / 2f + colSpacing / 2f
        val gridOriginY = (height - (rows * 1.5f - 0.5f) * radius) / 2f + radius

        // 1st Draw backgrounds / ground layer (Earth and Ashes and Grid lines)
        for (row in 0 until rows) {
            val isEven = row % 2 == 0
            val cy = gridOriginY + row * rowSpacing
            val cx = gridOriginX + colSpacing * if (isEven) {
                row / 2 // wait, col spacing increment:
                0f
            } else {
                0.5f
            }

            for (col in 0 until cols) {
                val hexCx = cx + col * colSpacing
                val hexCy = cy

                val state = grid.getCell(col, row)
                
                // Construct path
                path.reset()
                for (i in 0..5) {
                    val angleRad = (Math.PI / 180.0) * (30.0 + i * 60.0)
                    val px = hexCx + radius * cos(angleRad).toFloat()
                    val py = hexCy + radius * sin(angleRad).toFloat()
                    if (i == 0) path.moveTo(px, py) else path.lineTo(px, py)
                }
                path.close()

                // Color configuration:
                // For Earth and Ashes: draw base solid color
                // For Water, Fire, Grass, Vapor: we draw customized effects
                when (state) {
                    CellState.EARTH, CellState.ASHES -> {
                        drawPath(path = path, color = state.color)
                    }
                    CellState.WATER -> {
                        // Radiant deep water
                        val waterBrush = Brush.radialGradient(
                            colors = listOf(Color(0xFF64B5F6), Color(0xFF1976D2), Color(0xFF0D47A1)),
                            center = Offset(hexCx, hexCy),
                            radius = radius * 1.1f
                        )
                        drawPath(path = path, brush = waterBrush)
                    }
                    CellState.FIRE -> {
                        // Rising hot fire gradient
                        val fireBrush = Brush.linearGradient(
                            colors = listOf(Color(0xFFFFEE58), Color(0xFFFF9800), Color(0xFFD84315)),
                            start = Offset(hexCx, hexCy + radius),
                            end = Offset(hexCx, hexCy - radius)
                        )
                        drawPath(path = path, brush = fireBrush)
                    }
                    CellState.GRASS -> {
                        // Flamboyant foliage radial green
                        val foliageBrush = Brush.radialGradient(
                            colors = listOf(Color(0xFF81C784), Color(0xFF388E3C), Color(0xFF1B5E20)),
                            center = Offset(hexCx, hexCy),
                            radius = radius * 1.1f
                        )
                        drawPath(path = path, brush = foliageBrush)
                    }
                    CellState.VAPOR -> {
                        // Translucent mist cloud on top of base Earth/Ashes
                        // Draw standard background earth first so vapors float above
                        drawPath(path = path, color = CellState.EARTH.color)
                        
                        val vaporBrush = Brush.radialGradient(
                            colors = listOf(Color(0xE6E0F7FA), Color(0x99B2EBF2), Color(0x1A00E5FF)),
                            center = Offset(hexCx, hexCy),
                            radius = radius * 1.2f
                        )
                        drawPath(path = path, brush = vaporBrush)
                    }
                }

                // Draw a beautiful grid outline for definition
                val outlineColor = Color(0x33FFFFFF) // soft glowing separation line
                drawPath(
                    path = path,
                    color = outlineColor,
                    style = Stroke(width = 1f)
                )

                // Optional graphic assets or symbols inside cells to add ultimate craftsman feedback
                if (state == CellState.GRASS) {
                    // Draw a tiny sprout sign in the center
                    drawCircle(
                        color = Color(0xB3FFFFFF),
                        radius = radius * 0.15f,
                        center = Offset(hexCx, hexCy)
                    )
                } else if (state == CellState.FIRE) {
                    // Draw hot particle spark
                    drawCircle(
                        color = Color(0xE6FFFF00),
                        radius = radius * 0.18f,
                        center = Offset(hexCx, hexCy - radius * 0.3f)
                    )
                } else if (state == CellState.ASHES) {
                    // Draw tiny ashes speckle
                    drawCircle(
                        color = Color(0x4D000000),
                        radius = radius * 0.12f,
                        center = Offset(hexCx + radius * 0.2f, hexCy + radius * 0.2f)
                    )
                }
            }
        }
    }
}

/**
 * Perform Euclidean search to find which Hex cell center was touched.
 */
private fun detectAndPaintHex(
    touch: Offset,
    canvasW: Float,
    canvasH: Float,
    cols: Int,
    rows: Int,
    onPaintCell: (col: Int, row: Int) -> Unit
) {
    if (!touch.isSpecified || !touch.x.isFinite() || !touch.y.isFinite()) return
    if (canvasW <= 0f || canvasH <= 0f) return

    val extColSpan = cols + 0.5f
    val extRowSpan = rows * 0.75f + 0.25f
    
    val rFromWidth = canvasW / (extColSpan * sqrt(3f))
    val rFromHeight = canvasH / (extRowSpan * 2f)
    val radius = Math.min(rFromWidth, rFromHeight) * 0.96f

    // Ensure we have a valid positive radius to avoid division or rendering errors
    if (radius <= 0f) return

    val colSpacing = sqrt(3f) * radius
    val rowSpacing = 1.5f * radius

    val gridOriginX = (canvasW - extColSpan * colSpacing) / 2f + colSpacing / 2f
    val gridOriginY = (canvasH - (rows * 1.5f - 0.5f) * radius) / 2f + radius

    val estimatedRow = Math.round((touch.y - gridOriginY) / rowSpacing).toInt()
    val rStart = (estimatedRow - 2).coerceAtLeast(0)
    val rEnd = (estimatedRow + 2).coerceAtMost(rows - 1)

    var bestCol = -1
    var bestRow = -1
    var minDistanceSq = Float.MAX_VALUE

    for (row in rStart..rEnd) {
        val isEven = row % 2 == 0
        val cy = gridOriginY + row * rowSpacing
        val cx = gridOriginX + colSpacing * if (isEven) 0f else 0.5f

        val estimatedCol = Math.round((touch.x - cx) / colSpacing).toInt()
        val cStart = (estimatedCol - 2).coerceAtLeast(0)
        val cEnd = (estimatedCol + 2).coerceAtMost(cols - 1)

        for (col in cStart..cEnd) {
            val hexCx = cx + col * colSpacing
            val hexCy = cy

            val dx = touch.x - hexCx
            val dy = touch.y - hexCy
            val distSq = dx * dx + dy * dy
            if (distSq < minDistanceSq) {
                minDistanceSq = distSq
                bestCol = col
                bestRow = row
            }
        }
    }

    if (bestCol != -1 && bestRow != -1) {
        // Confirm touch occurred within reasonable bounds of the hexagon
        if (minDistanceSq < (radius * 1.5f) * (radius * 1.5f)) {
            onPaintCell(bestCol, bestRow)
        }
    }
}
