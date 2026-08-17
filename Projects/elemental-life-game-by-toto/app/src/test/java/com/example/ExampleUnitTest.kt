package com.example

import org.junit.Assert.*
import org.junit.Test
import com.example.model.HexGrid
import com.example.model.CellState
import com.example.model.SimRules

class ExampleUnitTest {
  @Test
  fun addition_isCorrect() {
    assertEquals(4, 2 + 2)
  }

  @Test
  fun testWaterSurroundedByGrassBecomesGrass() {
    val grid = HexGrid(5, 5)
    // Clear and set center (2,2) to Water, and neighbors to Grass
    grid.setCell(2, 2, CellState.WATER)
    
    val neighbors = grid.getNeighborIndices(2, 2)
    // Set 5 of the neighbors of (2,2) to Grass
    neighbors.take(5).forEach { idx ->
      grid.setCell(idx % 5, idx / 5, CellState.GRASS)
    }

    val rules = SimRules()
    val nextGrid = grid.computeNextStep(rules)
    
    // Water should now be Grass
    assertEquals(CellState.GRASS, nextGrid.getCell(2, 2))
  }

  @Test
  fun testEarthSurroundedByFiveWaterBecomesWater() {
    val grid = HexGrid(5, 5)
    // Center is Earth
    grid.setCell(2, 2, CellState.EARTH)
    
    val neighbors = grid.getNeighborIndices(2, 2)
    // Set 5 of its neighbors to Water
    neighbors.take(5).forEach { idx ->
      grid.setCell(idx % 5, idx / 5, CellState.WATER)
    }

    val rules = SimRules()
    val nextGrid = grid.computeNextStep(rules)
    
    // Earth should now be Water
    assertEquals(CellState.WATER, nextGrid.getCell(2, 2))
  }
}
