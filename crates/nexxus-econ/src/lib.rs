//! NeXXUs economics: 16 GB sections, barter quota, 56-day vesting, degradation, anti-loop.
//! Separate crate with its own release cycle (ADR-0004). All money is integer micro-NEXX.

pub mod degradation;
pub mod sections;
pub mod vesting;

/// 16 GB fixed storage sections (barter base unit).
pub const SECTION_SIZE_GB: u64 = 16;
/// Minimum base storage requirement.
pub const BASE_SECTION_MIN_GB: u64 = 16;
/// Base vault reward for the first 16 GB: exactly 2 GB (1/8th).
pub const BASE_VAULT_REWARD_GB: u64 = 2;
/// Expanded vault ratio: 12.5% of every additional byte.
pub const EXPANDED_VAULT_RATIO_NUM: u64 = 1;
pub const EXPANDED_VAULT_RATIO_DEN: u64 = 8;
/// Daily NEXX earned per GB of foreign chunks stored.
pub const DAILY_NEXX_RATE_PER_GB: i64 = 1_250_000_000; // 1.25 NEXX in micro
/// Daily NEXX paid to treasury per GB subscribed (writer fee).
pub const SUBSCRIPTION_DAILY_COST_PER_GB: i64 = 1_300_000_000; // 1.30 NEXX in micro
/// Mandatory vesting lock (8 weeks = 56 days).
pub const VESTING_LOCK_DAYS: u64 = 56;
/// Downtime > 24 h freezes the current epoch's rewards (spec 4.3).
pub const FREEZE_REWARDS_AFTER_HOURS: u64 = 24;
/// Downtime > 14 days: `warning_14d`, emergency re-replication starts (spec 4.3).
pub const WARNING_AFTER_DAYS: u64 = 14;
/// Downtime > 28 days: unvested balance burned, replication moves to archive pool (spec 4.3).
pub const DEGRADED_AFTER_DAYS: u64 = 28;
/// Consecutive PoR rounds required to reset a downtime penalty (spec 4.3).
pub const POR_RESET_ROUNDS: u8 = 3;
