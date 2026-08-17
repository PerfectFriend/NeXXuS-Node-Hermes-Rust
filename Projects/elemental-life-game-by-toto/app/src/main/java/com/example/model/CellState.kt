package com.example.model

import androidx.compose.ui.graphics.Color

enum class CellState(val value: Int, val displayName: String, val color: Color, val description: String) {
    ASHES(0, "Ashes/Empty", Color(0xFF37474F), "Burned or inert ground. Can grow grass when watered."),
    EARTH(1, "Earth", Color(0xFF8D6E63), "Nutrient-rich stable land. Perfect substrate for grass propagation."),
    WATER(2, "Water", Color(0xFF1E88E5), "Liquid water, flows and collects into lakes. Keeps plants alive."),
    VAPOR(3, "Vapor/Air", Color(0xFF80DEEA), "Gaseous humidity or smoke. Drifts, cools, and precipitates into water."),
    FIRE(4, "Fire", Color(0xFFFF5722), "Destructive combustion. Burns grass and converts water into vapor."),
    GRASS(5, "Grass/Life", Color(0xFF4CAF50), "Flourishing organic plant life. Spreads recursively and needs water.");

    companion object {
        fun fromValue(value: Int): CellState {
            return values().firstOrNull { it.value == value } ?: ASHES
        }
    }
}
