package com.example.model

data class SimRules(
    val fireSpreadChance: Float = 0.70f,      // Probability that Fire spreads into dry Grass neighbors
    val fireExtinguishChance: Float = 0.85f,  // Probability that Fire touching Water changes both (Water -> Vapor/Air, Fire -> Earth)
    val fireBurnoutChance: Float = 0.35f,     // Probability that active Fire burns out on its own into Ashes
    val grassGrowChance: Float = 0.20f,       // Probability that Grass seeds into adjacent Earth/Ashes near Water
    val grassDieNoWaterChance: Float = 0.80f, // Probability that Grass dries out and combusts to Fire if it has 0 Water neighbors
    val grassTranspireChance: Float = 0.15f,  // Probability that Grass adjacent to 2+ Water cells transpirates one into Vapor
    val vaporCondenseChance: Float = 0.08f,   // Probability that gaseous Vapor condenses back to liquid Water on cool Earth
    val vaporDriftChance: Float = 0.60f,      // Probability that wind drifts Vapor to adjacent empty/Earth cells
    val waterClumpChance: Float = 0.25f,      // Probability that isolated Water seeps/flows toward neighboring Water (Lakes)
    val lakeAggregationChance: Float = 0.30f  // Probability that dry ground near multiple Water cells absorbs water, expanding lakes
) {
    // Custom label explanation for a game state
    fun getEcosystemStatus(
        ashesCount: Int,
        earthCount: Int,
        waterCount: Int,
        vaporCount: Int,
        fireCount: Int,
        grassCount: Int
    ): Pair<String, String> {
        val total = (ashesCount + earthCount + waterCount + vaporCount + fireCount + grassCount).coerceAtLeast(1)
        val firePct = fireCount.toFloat() / total
        val grassPct = grassCount.toFloat() / total
        val waterPct = (waterCount + vaporCount).toFloat() / total
        val earthPct = earthCount.toFloat() / total

        return when {
            firePct > 0.15f -> Pair(
                "Wildfire Infestation 🔥",
                "Fires are spreading uncontrolled across the environment! Increase humidity, plant hydrated grass, or let moisture condense."
            )
            grassPct > 0.40f && waterPct < 0.10f -> Pair(
                "Arid Grasslands 🌾",
                "Grass is dominant, but water levels are critically low. High risk of a complete wildfire breakout if ignition occurs!"
            )
            waterPct > 0.45f -> Pair(
                "Flooded Swamp 🌊",
                "Water is oversaturating the map, turning open areas into lakes. Vapor condensation is high."
            )
            grassCount == 0 && fireCount == 0 -> Pair(
                "Barren Wasteland 🪨",
                "The environment is completely desolate with no active plant or fire life. Re-seed grass manually using your brush!"
            )
            grassPct > 0.15f && waterPct > 0.12f && firePct == 0.0f -> Pair(
                "Lush Safe Oasis 🌿",
                "A peaceful, fire-free ecosystem. Grass is steadily growing around healthy lakes. Introduce spark to see live-action containment."
            )
            grassPct > 0.10f && waterPct > 0.10f && firePct > 0.01f -> Pair(
                "Perfect Balance ☯️",
                "Superb equilibrium! Fire and Water are in constant tension, with Vapor clouds seeding rain and Grass re-colonizing ash fields safely."
            )
            else -> Pair(
                "Ecosystem Stable 🌎",
                "The elements are co-existing. Monitor how water vaporizes into clouds and flows into lakes to maintain growth."
            )
        }
    }
}
