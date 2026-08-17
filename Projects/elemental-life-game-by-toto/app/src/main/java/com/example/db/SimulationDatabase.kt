package com.example.db

import android.content.Context
import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "saved_presets")
data class SavedPresetEntity(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    @ColumnInfo(name = "name") val name: String,
    @ColumnInfo(name = "cells") val cells: String, // Comma-separated integers (e.g. "1,2,5,0,4...")
    @ColumnInfo(name = "cols") val cols: Int,
    @ColumnInfo(name = "rows") val rows: Int,
    @ColumnInfo(name = "created_at") val createdAt: Long = System.currentTimeMillis()
)

@Dao
interface SavedPresetDao {
    @Query("SELECT * FROM saved_presets ORDER BY created_at DESC")
    fun getAllPresets(): Flow<List<SavedPresetEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertPreset(preset: SavedPresetEntity)

    @Delete
    suspend fun deletePreset(preset: SavedPresetEntity)

    @Query("DELETE FROM saved_presets WHERE id = :id")
    suspend fun deletePresetById(id: Int)
}

@Database(entities = [SavedPresetEntity::class], version = 1, exportSchema = false)
abstract class SimulationDatabase : RoomDatabase() {
    abstract fun savedPresetDao(): SavedPresetDao

    companion object {
        @Volatile
        private var INSTANCE: SimulationDatabase? = null

        fun getDatabase(context: Context): SimulationDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    SimulationDatabase::class.java,
                    "simulation_db"
                )
                .fallbackToDestructiveMigration()
                .build()
                INSTANCE = instance
                instance
            }
        }
    }
}
