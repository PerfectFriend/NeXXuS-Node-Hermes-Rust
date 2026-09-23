# HOT
package com.toto.elementallife.cover.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.toto.elementallife.cover.db.SavedPresetEntity
import com.toto.elementallife.cover.db.SimulationDatabase
import com.toto.elementallife.cover.model.CellState
import com.toto.elementallife.cover.model.HexGrid
import com.toto.elementallife.cover.model.SimRules
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlin.random.Random

class SimulationViewModel(application: Application) : AndroidViewModel(application) {

    private val db = SimulationDatabase.getDatabase(application)
    private val presetDao = db.savedPresetDao()

    private val prefs = application.getSharedPreferences("elemental_life_prefs", android.content.Context.MODE_PRIVATE)
    private val _isPremium = MutableStateFlow(prefs.getBoolean("is_premium", false))
    val isPremium: StateFlow<Boolean> = _isPremium.asStateFlow()

    fun unlockPremium(unlock: Boolean = true) {
        _isPremium.value = unlock
        prefs.edit().putBoolean("is_premium", unlock).apply()
    }

    var cols = 24
        private set
    var rows = 26
        private set

    private val _gridState = MutableStateFlow(HexGrid(cols, rows))
    val gridState: StateFlow<HexGrid> = _gridState.asStateFlow()

    private val _rulesState = MutableStateFlow(SimRules())
    val rulesState: StateFlow<SimRules> = _rulesState.asStateFlow()

    private val _isPlaying = MutableStateFlow(false)
    val isPlaying: StateFlow<Boolean> = _isPlaying.asStateFlow()

    private val _speedMs = MutableStateFlow(350L) // lower delay = faster simulation
    val speedMs: StateFlow<Long> = _speedMs.asStateFlow()

    private val _activeBrush = MutableStateFlow(CellState.GRASS)
    val activeBrush: StateFlow<CellState> = _activeBrush.asStateFlow()

    private val _brushSize = MutableStateFlow(1) // 1 = single cell, 2 = small, 3 = large
    val brushSize: StateFlow<Int> = _brushSize.asStateFlow()

    private val _generationCount = MutableStateFlow(0)
    val generationCount: StateFlow<Int> = _generationCount.asStateFlow()

    private var tickerJob: Job? = null

    // Fetch saved custom presets from Room
    val savedPresets: StateFlow<List<SavedPresetEntity>> = presetDao.getAllPresets()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    init {
        // Start out with a balanced Eden preset by default
        loadPreset("eden")
    }

    fun startSimulation() {
        if (_isPlaying.value) return
        _isPlaying.value = true
        tickerJob = viewModelScope.launch {
            while (_isPlaying.value) {
                delay(_speedMs.value)
                oneStep()
            }
        }
    }

    fun pauseSimulation() {
        _isPlaying.value = false
        tickerJob?.cancel()
        tickerJob = null
    }

    fun oneStep() {
        _gridState.value = _gridState.value.computeNextStep(_rulesState.value)
        _generationCount.value += 1
    }

    fun resetGrid() {
        seedRandomGrid()
    }

    fun seedRandomGrid() {
        pauseSimulation()
        _gridState.value = HexGrid.createBalancedEdenPreset(cols, rows)
        _generationCount.value = 0
    }

    fun clearGrid(baseState: CellState = CellState.ASHES) {
        pauseSimulation()
        val emptyCells = IntArray(cols * rows) { baseState.value }
        // Place just a tiny drop of water in the center if they cleared to Earth
        val centerIdx = (rows / 2) * cols + (cols / 2)
        if (baseState == CellState.EARTH && centerIdx in emptyCells.indices) {
            emptyCells[centerIdx] = CellState.WATER.value
        }
        _gridState.value = HexGrid(cols, rows, emptyCells)
        _generationCount.value = 0
    }

    fun updateGridSize(newCols: Int, newRows: Int) {
        pauseSimulation()
        cols = newCols.coerceIn(10, 45)
        rows = newRows.coerceIn(10, 45)
        seedRandomGrid()
    }

    fun updateSpeed(newSpeedMs: Long) {
        _speedMs.value = newSpeedMs
    }

    fun setActiveBrush(brush: CellState) {
        _activeBrush.value = brush
    }

    fun setBrushSize(size: Int) {
        _brushSize.value = size
    }

    fun updateRule(modifier: (SimRules) -> SimRules) {
        _rulesState.value = modifier(_rulesState.value)
    }

    fun resetRulesToDefault() {
        _rulesState.value = SimRules()
    }

    /**
     * Draw elements on the hexagonal Canvas using the currently selected brush and brush size.
     */
    fun paintCell(cCol: Int, rRow: Int) {
        if (!_isPremium.value) return // Block manual drawing in the Free version
        val currentBrush = _activeBrush.value
        val currentSize = _brushSize.value
        val grid = _gridState.value
        val gCols = grid.cols
        val gRows = grid.rows

        // Helper to collect cells to paint depending on brushSize
        val targetIndices = mutableSetOf<Int>()
        val centerIdx = rRow * gCols + cCol

        if (cCol in 0 until gCols && rRow in 0 until gRows) {
            targetIndices.add(centerIdx)

            if (currentSize >= 2) {
                // Add immediate neighbors (radius 1)
                val neighbors = grid.getNeighborIndices(cCol, rRow)
                targetIndices.addAll(neighbors)

                if (currentSize >= 3) {
                    // Add neighbors of neighbors (radius 2)
                    neighbors.forEach { nIdx ->
                        val nCol = nIdx % gCols
                        val nRow = nIdx / gCols
                        targetIndices.addAll(grid.getNeighborIndices(nCol, nRow))
                    }
                }
            }

            // Check if any change actually happens to avoid redundant recompositions
            var anyChanged = false
            for (idx in targetIndices) {
                if (idx in grid.cells.indices && grid.cells[idx] != currentBrush.value) {
                    anyChanged = true
                    break
                }
            }

            if (!anyChanged) {
                return
            }

            val newCells = grid.cells.clone()
            targetIndices.forEach { idx ->
                if (idx in newCells.indices) {
                    newCells[idx] = currentBrush.value
                }
            }
            _gridState.value = HexGrid(gCols, gRows, newCells)
        }
    }

    /**
     * Load official built-in preset configurations.
     */
    fun loadPreset(presetType: String) {
        pauseSimulation()
        val premiumTypes = listOf(
            "ring", "spiral", "stellar", "yinyang", "snowflake", "cross", 
            "mandala", "concentric", "portal", "tessellation", "nexus", "aurora", 
            "shield", "trinity", "cosmic", "crystal", "lava", "spiral_cloud", 
            "emerald", "phoenix"
        )
        val newGrid = when (presetType) {
            "fire" -> HexGrid.createForestFirePreset(cols, rows)
            "lake" -> HexGrid.createGreatLakePreset(cols, rows)
            "oasis" -> HexGrid.createRainOasisPreset(cols, rows)
            "volcano" -> HexGrid.createVolcanicPreset(cols, rows)
            in premiumTypes -> HexGrid.createPremiumPreset(cols, rows, presetType)
            else -> HexGrid.createBalancedEdenPreset(cols, rows) // "eden"
        }
        _gridState.value = newGrid
        _generationCount.value = 0
    }

    /**
     * Saves user's custom sandbox arrangement to Room as a CSV string.
     */
    fun saveCustomPreset(name: String) {
        viewModelScope.launch {
            val grid = _gridState.value
            val csvCells = grid.cells.joinToString(",")
            val entity = SavedPresetEntity(
                name = name.ifEmpty { "My Preset ${Random.nextInt(100, 999)}" },
                cells = csvCells,
                cols = cols,
                rows = rows
            )
            presetDao.insertPreset(entity)
        }
    }

    /**
     * Loads a previously saved custom sandbox arrangement.
     */
    fun loadCustomPreset(preset: SavedPresetEntity) {
        pauseSimulation()
        try {
            val array = preset.cells.split(",").map { it.toInt() }.toIntArray()
            val pCols = preset.cols
            val pRows = preset.rows
            if (array.size == pCols * pRows) {
                cols = pCols
                rows = pRows
                _gridState.value = HexGrid(pCols, pRows, array)
                _generationCount.value = 0
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    /**
     * Deletes a saved preset from the database.
     */
    fun deleteCustomPreset(preset: SavedPresetEntity) {
        viewModelScope.launch {
            presetDao.deletePreset(preset)
        }
    }
}
