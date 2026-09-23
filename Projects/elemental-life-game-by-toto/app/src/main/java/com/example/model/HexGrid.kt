# HOT
package com.example.model

import kotlin.random.Random

class HexGrid(
    val cols: Int,
    val rows: Int,
    initialCells: IntArray? = null
) {
    var cells: IntArray = initialCells ?: IntArray(cols * rows) { CellState.EARTH.value }
        private set

    init {
        if (initialCells == null) {
            resetToEmpty()
        }
    }

    fun getCell(col: Int, row: Int): CellState {
        if (col in 0 until cols && row in 0 until rows) {
            return CellState.fromValue(cells[row * cols + col])
        }
        return CellState.ASHES
    }

    fun setCell(col: Int, row: Int, state: CellState) {
        if (col in 0 until cols && row in 0 until rows) {
            cells[row * cols + col] = state.value
        }
    }

    fun getNeighborIndices(col: Int, row: Int): List<Int> {
        val neighbors = mutableListOf<Int>()
        val isEvenRow = (row % 2 == 0)
        
        // Pointy-topped hexagon with even-r offset row coordinates
        val offsets = if (isEvenRow) {
            listOf(
                Pair(-1, 0),  // Left
                Pair(1, 0),   // Right
                Pair(0, -1),  // Top-Right
                Pair(-1, -1), // Top-Left
                Pair(0, 1),   // Bottom-Right
                Pair(-1, 1)   // Bottom-Left
            )
        } else {
            listOf(
                Pair(-1, 0),  // Left
                Pair(1, 0),   // Right
                Pair(1, -1),  // Top-Right
                Pair(0, -1),  // Top-Left
                Pair(1, 1),   // Bottom-Right
                Pair(0, 1)    // Bottom-Left
            )
        }

        for ((dc, dr) in offsets) {
            val nc = col + dc
            val nr = row + dr
            if (nc in 0 until cols && nr in 0 until rows) {
                neighbors.add(nr * cols + nc)
            }
        }
        return neighbors
    }

    fun resetToEmpty() {
        for (i in cells.indices) {
            cells[i] = CellState.EARTH.value
        }
        // Place some water in the center as base
        val centerCol = cols / 2
        val centerRow = rows / 2
        setCell(centerCol, centerRow, CellState.WATER)
        setCell(centerCol + 1, centerRow, CellState.WATER)
        setCell(centerCol, centerRow + 1, CellState.WATER)
    }

    fun getElementCounts(): Map<CellState, Int> {
        val counts = mutableMapOf<CellState, Int>()
        CellState.values().forEach { counts[it] = 0 }
        for (v in cells) {
            val state = CellState.fromValue(v)
            counts[state] = counts[state]!! + 1
        }
        return counts
    }

    /**
     * Compute the next state of the ecosystem.
     * Incorporates rule parameters and adheres strictly to ecological balances.
     */
    fun computeNextStep(rules: SimRules): HexGrid {
        val nextCells = cells.clone()
        val random = Random.Default

        // Keep track of actions to resolve swaps or conservation (e.g. transpiration, drift)
        // Set of indices that already performed a cooperative swap in this generation
        val processedIndices = mutableSetOf<Int>()

        for (i in cells.indices) {
            if (processedIndices.contains(i)) continue

            val col = i % cols
            val row = i / cols
            val stateVal = cells[i]
            val state = CellState.fromValue(stateVal)

            val neighbors = getNeighborIndices(col, row)
            val neighborStates = neighbors.map { cells[it] }

            val waterCount = neighborStates.count { it == CellState.WATER.value }
            val fireCount = neighborStates.count { it == CellState.FIRE.value }
            val grassCount = neighborStates.count { it == CellState.GRASS.value }
            val vaporCount = neighborStates.count { it == CellState.VAPOR.value }
            val earthCount = neighborStates.count { it == CellState.EARTH.value }
            val ashesCount = neighborStates.count { it == CellState.ASHES.value }

            if (waterCount in 5..6) {
                nextCells[i] = CellState.WATER.value
            } else if (state == CellState.WATER && grassCount in 5..6) {
                nextCells[i] = CellState.GRASS.value
            } else {
                when (state) {
                CellState.ASHES -> {
                    // Rule: ashes/earth going to grass having 1 grass and 1 water near
                    if (grassCount >= 1 && waterCount >= 1 && fireCount == 0) {
                        if (random.nextFloat() < rules.grassGrowChance) {
                            nextCells[i] = CellState.GRASS.value
                        }
                    } else if (fireCount == 0 && random.nextFloat() < 0.03f) {
                        nextCells[i] = CellState.EARTH.value // organic decay back to standard soil
                    }
                }

                CellState.EARTH -> {
                    // water always migrate to earth to become both grass
                    val waterNeighbors = neighbors.filter { cells[it] == CellState.WATER.value && !processedIndices.contains(it) }
                    if (waterNeighbors.isNotEmpty()) {
                        val targetWaterIdx = waterNeighbors.random()
                        nextCells[i] = CellState.GRASS.value
                        nextCells[targetWaterIdx] = CellState.GRASS.value
                        processedIndices.add(targetWaterIdx)
                        processedIndices.add(i)
                    } else {
                        // Rule: ashes/earth going to grass having 1 grass and 1 water near
                        if (grassCount >= 1 && waterCount >= 1 && fireCount == 0) {
                            if (random.nextFloat() < rules.grassGrowChance * 1.4f) { // earth is more fertile
                                nextCells[i] = CellState.GRASS.value
                            }
                        }
                        // Lake Expansion / Swamping: Earth transforms to Water when bordering multiple Water cells
                        else if (waterCount >= 3 && fireCount == 0) {
                            if (random.nextFloat() < rules.lakeAggregationChance) {
                                nextCells[i] = CellState.WATER.value
                            }
                        }
                    }
                }

                CellState.GRASS -> {
                    // Rule: grass with 6 grass near or 1 fire and 0 water near become fire next step, fire can become only instead of grass
                    if (grassCount == 6 || (fireCount == 1 && waterCount == 0)) {
                        nextCells[i] = CellState.FIRE.value
                    }
                    // Rule: Transpiration from Grass adjacent to 2+ water
                    else if (waterCount >= 2 && random.nextFloat() < rules.grassTranspireChance) {
                        // Find a neighboring Water cell to vaporize
                        val waterNeighbors = neighbors.filter { cells[it] == CellState.WATER.value && !processedIndices.contains(it) }
                        if (waterNeighbors.isNotEmpty()) {
                            val targetWaterIdx = waterNeighbors.random()
                            nextCells[targetWaterIdx] = CellState.VAPOR.value
                            processedIndices.add(targetWaterIdx)
                        }
                    }
                }

                CellState.WATER -> {
                    // Symmetrical Water and Fire meeting rule
                    var waterProcessedByFire = false
                    if (fireCount > 0) {
                        val fireNeighbors = neighbors.filter { cells[it] == CellState.FIRE.value && !processedIndices.contains(it) }
                        if (fireNeighbors.isNotEmpty()) {
                            val targetFireIdx = fireNeighbors.random()
                            nextCells[i] = CellState.EARTH.value           // 1 water becoming earth
                            nextCells[targetFireIdx] = CellState.VAPOR.value // fire become air (VAPOR)
                            processedIndices.add(targetFireIdx)
                            processedIndices.add(i)
                            waterProcessedByFire = true
                        }
                    }
                    
                    if (!waterProcessedByFire) {
                        // water always migrate to earth to become both grass
                        val earthNeighbors = neighbors.filter { cells[it] == CellState.EARTH.value && !processedIndices.contains(it) }
                        if (earthNeighbors.isNotEmpty()) {
                            val targetEarthIdx = earthNeighbors.random()
                            nextCells[i] = CellState.GRASS.value
                            nextCells[targetEarthIdx] = CellState.GRASS.value
                            processedIndices.add(targetEarthIdx)
                            processedIndices.add(i)
                        }
                        // Lake Collection: Seepage of isolated water towards bigger pools
                        else if (waterCount == 0 && random.nextFloat() < rules.waterClumpChance) {
                            // Find an adjacent Earth/Ashes cell that borders some water
                            val flowCandidates = neighbors.filter { neighborIdx ->
                                val nState = CellState.fromValue(cells[neighborIdx])
                                (nState == CellState.EARTH || nState == CellState.ASHES) && !processedIndices.contains(neighborIdx) &&
                                        getNeighborIndices(neighborIdx % cols, neighborIdx / cols).any { cells[it] == CellState.WATER.value }
                            }
                            if (flowCandidates.isNotEmpty()) {
                                val destination = flowCandidates.random()
                                nextCells[i] = cells[destination] // Water seeps away, leaving empty ground
                                nextCells[destination] = CellState.WATER.value // Destination becomes Water (clumped!)
                                processedIndices.add(destination)
                                processedIndices.add(i)
                            }
                        }
                    }
                }

                CellState.VAPOR -> {
                    // air with 0 fire near become water!
                    if (fireCount == 0) {
                        nextCells[i] = CellState.WATER.value
                    }
                    // Wind Drift: Vapor swaps with neighboring Earth/Ashes/Ashes to simulate wind currents
                    else if (random.nextFloat() < rules.vaporDriftChance) {
                        // Swap with a neighboring dry cell
                        val dryGrounds = neighbors.filter { cellIdx ->
                            val s = CellState.fromValue(cells[cellIdx])
                            (s == CellState.EARTH || s == CellState.ASHES) && !processedIndices.contains(cellIdx)
                        }
                        if (dryGrounds.isNotEmpty()) {
                            val targetIdx = dryGrounds.random()
                            // Swapping states
                            nextCells[i] = cells[targetIdx]
                            nextCells[targetIdx] = CellState.VAPOR.value
                            processedIndices.add(targetIdx)
                            processedIndices.add(i)
                        }
                    }
                }

                CellState.FIRE -> {
                    if (waterCount > 0) {
                        val waterNeighbors = neighbors.filter { cells[it] == CellState.WATER.value && !processedIndices.contains(it) }
                        if (waterNeighbors.isNotEmpty()) {
                            val targetWaterIdx = waterNeighbors.random()
                            nextCells[targetWaterIdx] = CellState.EARTH.value // 1 water becoming earth
                            nextCells[i] = CellState.VAPOR.value              // fire become air (VAPOR)
                            processedIndices.add(targetWaterIdx)
                            processedIndices.add(i)
                        } else {
                            // Symmetrical fallback if water already processed it, make sure this cell is still air
                            nextCells[i] = CellState.VAPOR.value
                            processedIndices.add(i)
                        }
                    } else {
                        // and fire not meet any water - next step becoming earth
                        nextCells[i] = CellState.EARTH.value
                        processedIndices.add(i)
                    }
                }
            }
        }
    }

        // --- GLOBAL WATER QUANTITY FEEDBACK LAYER (Persistent Water Volume) ---
        // Ensuring water conservation remains extremely stable and doesn't drift
        val resultingGrid = HexGrid(cols, rows, nextCells)
        val initialCounts = getElementCounts()
        val initialWaterVolume = (initialCounts[CellState.WATER] ?: 0) + (initialCounts[CellState.VAPOR] ?: 0)
        
        val newCounts = resultingGrid.getElementCounts()
        val newWaterVolume = (newCounts[CellState.WATER] ?: 0) + (newCounts[CellState.VAPOR] ?: 0)
        
        val deficit = initialWaterVolume - newWaterVolume
        val resultingCells = resultingGrid.cells

        if (deficit > 0) {
            // We lost water/vapor! Let's replenish by turning some random dry empty nodes (Ashes/Earth) with neighbors into Vapor
            var turned = 0
            val candidates = resultingCells.indices.filter {
                val s = CellState.fromValue(resultingCells[it])
                s == CellState.ASHES || s == CellState.EARTH
            }.shuffled()
            for (idx in candidates) {
                if (turned >= deficit) break
                resultingCells[idx] = CellState.VAPOR.value
                turned++
            }
        } else if (deficit < 0) {
            // We created extra water! Let's turn some isolated Water/Vapor back into Earth or Ashes
            var dryed = 0
            val excessCount = -deficit
            val waterVaporIndices = resultingCells.indices.filter {
                val s = CellState.fromValue(resultingCells[it])
                s == CellState.WATER || s == CellState.VAPOR
            }.shuffled()
            for (idx in waterVaporIndices) {
                if (dryed >= excessCount) break
                resultingCells[idx] = CellState.EARTH.value
                dryed++
            }
        }

        return resultingGrid
    }

    // --- PRESET WORLD GENERATORS ---
    companion object {
        fun createForestFirePreset(cols: Int, rows: Int): HexGrid {
            val grid = HexGrid(cols, rows)
            // Fill 70% with Grass, some Earth pockets, some water on sides, and ignite a fire in the center
            for (col in 0 until cols) {
                for (row in 0 until rows) {
                    val distToCenter = Math.hypot((col - cols/2).toDouble(), (row - rows/2).toDouble())
                    when {
                        distToCenter < 2.5 -> grid.setCell(col, row, CellState.FIRE)
                        distToCenter < 8.0 -> {
                            if (Random.nextFloat() < 0.85f) {
                                grid.setCell(col, row, CellState.GRASS)
                            } else {
                                grid.setCell(col, row, CellState.EARTH)
                            }
                        }
                        col == 1 || col == cols - 2 || row == 1 || row == rows - 2 -> {
                            grid.setCell(col, row, CellState.WATER)
                        }
                        else -> {
                            grid.setCell(col, row, CellState.GRASS)
                        }
                    }
                }
            }
            return grid
        }

        fun createGreatLakePreset(cols: Int, rows: Int): HexGrid {
            val grid = HexGrid(cols, rows)
            val centerCol = cols / 2.0
            val centerRow = rows / 2.0
            val maxRadius = Math.min(cols, rows) / 2.0

            for (col in 0 until cols) {
                for (row in 0 until rows) {
                    val d = Math.hypot(col - centerCol, row - centerRow)
                    when {
                        d < maxRadius * 0.45 -> {
                            grid.setCell(col, row, CellState.WATER)
                        }
                        d < maxRadius * 0.55 -> {
                            // Muddy outline / wet vapor surrounding
                            grid.setCell(col, row, CellState.VAPOR)
                        }
                        d < maxRadius * 0.85 -> {
                            grid.setCell(col, row, CellState.GRASS)
                        }
                        else -> {
                            grid.setCell(col, row, CellState.EARTH)
                        }
                    }
                }
            }
            return grid
        }

        fun createBalancedEdenPreset(cols: Int, rows: Int): HexGrid {
            val grid = HexGrid(cols, rows)
            // Balanced distributions of small ponds, nice fields of grass, patches of earth, and active clouds.
            for (col in 0 until cols) {
                for (row in 0 until rows) {
                    val r = Random.nextFloat()
                    when {
                        r < 0.22f -> grid.setCell(col, row, CellState.WATER)
                        r < 0.35f -> grid.setCell(col, row, CellState.GRASS)
                        r < 0.45f -> grid.setCell(col, row, CellState.VAPOR)
                        r < 0.85f -> grid.setCell(col, row, CellState.EARTH)
                        else -> grid.setCell(col, row, CellState.ASHES)
                    }
                }
            }
            // Add a spark of life in the center
            grid.setCell(cols / 2, rows / 2, CellState.FIRE)
            return grid
        }

        fun createVolcanicPreset(cols: Int, rows: Int): HexGrid {
            val grid = HexGrid(cols, rows)
            // Fire channels in center representing magma flows, bounded by earth walls, with water springs evaporating into clouds
            for (col in 0 until cols) {
                for (row in 0 until rows) {
                    // Let's create a core fire stream
                    val isCenterSlice = Math.abs(col - cols / 2) <= 1
                    val isMagmaChamber = Math.abs(row - rows / 2) <= 2 && Math.abs(col - cols/2) <= 2
                    val isSpring = (col == 3 && row == 3) || (col == cols - 4 && row == rows - 4)

                    when {
                        isMagmaChamber || (isCenterSlice && row % 4 != 0) -> {
                            grid.setCell(col, row, CellState.FIRE)
                        }
                        isSpring -> {
                            grid.setCell(col, row, CellState.WATER)
                        }
                        Random.nextFloat() < 0.15f -> {
                            grid.setCell(col, row, CellState.VAPOR)
                        }
                        Random.nextFloat() < 0.60f -> {
                            grid.setCell(col, row, CellState.ASHES)
                        }
                        else -> {
                            grid.setCell(col, row, CellState.EARTH)
                        }
                    }
                }
            }
            return grid
        }

        fun createRainOasisPreset(cols: Int, rows: Int): HexGrid {
            val grid = HexGrid(cols, rows)
            // Desert (all Earth and Ashes), with huge clouds of Vapor. Watch them condense and ignite life!
            for (col in 0 until cols) {
                for (row in 0 until rows) {
                    val r = Random.nextFloat()
                    when {
                        r < 0.35f -> grid.setCell(col, row, CellState.VAPOR)
                        r < 0.70f -> grid.setCell(col, row, CellState.EARTH)
                        else -> grid.setCell(col, row, CellState.ASHES)
                    }
                }
            }
            return grid
        }

        fun createPremiumPreset(cols: Int, rows: Int, presetType: String): HexGrid {
            val grid = HexGrid(cols, rows)
            val cx = cols / 2.0
            val cy = rows / 2.0
            for (col in 0 until cols) {
                for (row in 0 until rows) {
                    val dx = col - cx
                    val dy = (row - cy) * 1.15
                    val r = Math.hypot(dx, dy)
                    val theta = Math.atan2(dy, dx)
                    
                    val cellState = when (presetType) {
                        "ring" -> {
                            when {
                                r < 1.5 -> CellState.FIRE
                                r in 3.5..5.0 -> CellState.WATER
                                r in 7.0..8.5 -> CellState.GRASS
                                r in 11.0..12.5 -> CellState.VAPOR
                                else -> CellState.EARTH
                            }
                        }
                        "spiral" -> {
                            val leaf = Math.sin(6 * theta + r * 0.3)
                            when {
                                r < 2.0 -> CellState.WATER
                                r < 10.0 && leaf > 0.4 -> CellState.GRASS
                                r < 10.0 && leaf < -0.4 -> CellState.VAPOR
                                else -> CellState.EARTH
                            }
                        }
                        "stellar" -> {
                            val star = Math.sin(6 * theta)
                            when {
                                r < 1.0 -> CellState.FIRE
                                r < 9.0 && star > 0.6 -> CellState.FIRE
                                r < 9.0 && star < -0.6 -> CellState.WATER
                                r < 12.0 -> CellState.EARTH
                                else -> CellState.ASHES
                            }
                        }
                        "yinyang" -> {
                            val isTop = dy > 0
                            val distLeftEye = Math.hypot(dx + 3, dy)
                            val distRightEye = Math.hypot(dx - 3, dy)
                            when {
                                r < 10.0 -> {
                                    if (distLeftEye < 1.8) CellState.FIRE
                                    else if (distRightEye < 1.8) CellState.WATER
                                    else if (isTop) CellState.WATER
                                    else CellState.EARTH
                                }
                                else -> CellState.VAPOR
                            }
                        }
                        "snowflake" -> {
                            val pattern = Math.cos(6 * theta)
                            when {
                                r < 1.5 -> CellState.WATER
                                r < 11.0 && Math.abs(pattern) > 0.7 -> {
                                    if (r.toInt() % 3 == 0) CellState.WATER else CellState.VAPOR
                                }
                                r < 12.0 -> CellState.EARTH
                                else -> CellState.ASHES
                            }
                        }
                        "cross" -> {
                            val isCross = Math.abs(dx) < 1.2 || Math.abs(dy) < 1.2
                            when {
                                isCross && r < 12.0 -> if (Random.nextFloat() < 0.6) CellState.FIRE else CellState.ASHES
                                r < 8.0 -> CellState.GRASS
                                else -> CellState.EARTH
                            }
                        }
                        "mandala" -> {
                            val ringIdx = (r / 2.5).toInt()
                            when (ringIdx % 4) {
                                0 -> CellState.GRASS
                                1 -> CellState.WATER
                                2 -> CellState.VAPOR
                                else -> CellState.EARTH
                            }
                        }
                        "concentric" -> {
                            val wave = Math.sin(r * 1.5)
                            when {
                                wave > 0.5 -> CellState.WATER
                                wave < -0.5 -> CellState.GRASS
                                else -> CellState.EARTH
                            }
                        }
                        "portal" -> {
                            val starArms = Math.sin(5 * theta)
                            when {
                                r < 3.0 -> CellState.FIRE
                                r < 7.0 && starArms > 0.3 -> CellState.FIRE
                                r in 7.0..9.0 -> CellState.WATER
                                else -> CellState.VAPOR
                            }
                        }
                        "tessellation" -> {
                            val cellX = (col / 3) % 2
                            val cellY = (row / 3) % 2
                            if ((cellX + cellY) % 2 == 0) CellState.EARTH else CellState.GRASS
                        }
                        "nexus" -> {
                            val spoke = Math.cos(8 * theta)
                            when {
                                r < 2.0 -> CellState.FIRE
                                r < 10.0 && spoke > 0.7 -> CellState.FIRE
                                r < 10.0 && spoke < -0.7 -> CellState.VAPOR
                                else -> CellState.ASHES
                            }
                        }
                        "aurora" -> {
                            val waveOffset = Math.sin(dx * 0.4) * 3
                            val dyWave = Math.abs(dy - waveOffset)
                            when {
                                dyWave < 1.5 -> CellState.VAPOR
                                dyWave < 3.5 -> CellState.GRASS
                                else -> CellState.EARTH
                            }
                        }
                        "shield" -> {
                            val hexDist = Math.max(Math.abs(dx), Math.max(Math.abs(dx * 0.5 + dy * 0.866), Math.abs(dx * 0.5 - dy * 0.866)))
                            when {
                                hexDist < 2.0 -> CellState.WATER
                                hexDist in 4.0..5.5 -> CellState.GRASS
                                hexDist in 8.0..9.5 -> CellState.FIRE
                                else -> CellState.EARTH
                            }
                        }
                        "trinity" -> {
                            val angleDeg = Math.toDegrees(theta) + 180
                            when {
                                r < 1.5 -> CellState.ASHES
                                r < 10.0 -> {
                                    when {
                                        angleDeg in 0.0..120.0 -> CellState.FIRE
                                        angleDeg in 120.0..240.0 -> CellState.WATER
                                        else -> CellState.GRASS
                                    }
                                }
                                else -> CellState.EARTH
                            }
                        }
                        "cosmic" -> {
                            val ellipseR = Math.sqrt(dx * dx * 0.5 + dy * dy * 1.5)
                            when {
                                ellipseR < 2.0 -> CellState.FIRE
                                ellipseR in 4.0..6.0 -> CellState.WATER
                                ellipseR in 8.0..10.0 -> CellState.GRASS
                                else -> CellState.ASHES
                            }
                        }
                        "crystal" -> {
                            val gridCol = col % 5
                            val gridRow = row % 5
                            if (gridCol == 2 && gridRow == 2) CellState.WATER
                            else if (gridCol in 1..3 && gridRow in 1..3) CellState.GRASS
                            else CellState.EARTH
                        }
                        "lava" -> {
                            val lavaPattern = Math.sin(dx * 0.5) * Math.cos(dy * 0.5)
                            when {
                                lavaPattern > 0.4 -> CellState.FIRE
                                lavaPattern < -0.4 -> CellState.ASHES
                                else -> CellState.EARTH
                            }
                        }
                        "spiral_cloud" -> {
                            val spiralArm = Math.sin(3 * theta + r * 0.5)
                            when {
                                r < 12.0 && spiralArm > 0.3 -> CellState.VAPOR
                                r < 12.0 && spiralArm < -0.3 -> CellState.WATER
                                else -> CellState.EARTH
                            }
                        }
                        "emerald" -> {
                            val isHex = Math.max(Math.abs(dx), Math.max(Math.abs(dx * 0.5 + dy * 0.866), Math.abs(dx * 0.5 - dy * 0.866))) < 8.0
                            when {
                                isHex -> if (r < 2.5) CellState.WATER else CellState.GRASS
                                else -> CellState.EARTH
                            }
                        }
                        "phoenix" -> {
                            val wing = Math.abs(dx) * 1.5 - dy
                            val body = Math.abs(dx) < 1.5 && dy in -3.0..5.0
                            when {
                                body -> CellState.FIRE
                                wing in 0.0..3.0 && dy > -2.0 -> CellState.FIRE
                                r < 10.0 -> CellState.ASHES
                                else -> CellState.EARTH
                            }
                        }
                        else -> CellState.EARTH
                    }
                    grid.setCell(col, row, cellState)
                }
            }
            return grid
        }
    }
}
