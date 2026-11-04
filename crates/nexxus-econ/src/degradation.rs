//! Uptime degradation ladder (spec 4.3, MANIFESTO): 24 h freeze, 14 d warning,
//! 28 d degraded. Pure functions over offline duration — no I/O.

use crate::{DEGRADED_AFTER_DAYS, FREEZE_REWARDS_AFTER_HOURS, POR_RESET_ROUNDS, WARNING_AFTER_DAYS};

/// Node health derived from continuous offline time.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Health {
    /// Online, no penalties.
    Online,
    /// Offline > 24 h: rewards for the current epoch are frozen.
    RewardsFrozen,
    /// Offline > 14 days: `warning_14d`, emergency chunk re-replication on other nodes.
    Warning14d,
    /// Offline > 28 days: unvested vesting burned, replication moved to archive pool.
    Degraded28d,
}

impl Health {
    pub fn as_str(&self) -> &'static str {
        match self {
            Health::Online => "online",
            Health::RewardsFrozen => "rewards_frozen_24h",
            Health::Warning14d => "warning_14d",
            Health::Degraded28d => "degraded_28d",
        }
    }

    /// True when chunks must be treated as at-risk and re-replicated elsewhere.
    pub fn needs_emergency_replication(&self) -> bool {
        matches!(self, Health::Warning14d | Health::Degraded28d)
    }

    /// True when unvested rewards must be burned (slashing).
    pub fn burns_unvested(&self) -> bool {
        matches!(self, Health::Degraded28d)
    }
}

/// Map a continuous offline duration to health. `offline_hours` is the raw input;
/// days are derived from it (24 h = 1 day).
pub fn health_from_offline(offline_hours: u64) -> Health {
    let days = offline_hours / 24;
    if days >= DEGRADED_AFTER_DAYS {
        Health::Degraded28d
    } else if days >= WARNING_AFTER_DAYS {
        Health::Warning14d
    } else if offline_hours >= FREEZE_REWARDS_AFTER_HOURS {
        Health::RewardsFrozen
    } else {
        Health::Online
    }
}

/// `ResetDowntimePenalty` (spec 4.3): penalty resets only after
/// `POR_RESET_ROUNDS` consecutive successful PoR rounds.
pub fn reset_downtime_penalty(por_rounds_passed: u8) -> bool {
    por_rounds_passed >= POR_RESET_ROUNDS
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ladder_steps() {
        assert_eq!(health_from_offline(0), Health::Online);
        assert_eq!(health_from_offline(23), Health::Online);
        assert_eq!(health_from_offline(24), Health::RewardsFrozen);
        assert_eq!(health_from_offline(24 * 13), Health::RewardsFrozen);
        assert_eq!(health_from_offline(24 * 14), Health::Warning14d);
        assert_eq!(health_from_offline(24 * 27), Health::Warning14d);
        assert_eq!(health_from_offline(24 * 28), Health::Degraded28d);
        assert_eq!(health_from_offline(24 * 365), Health::Degraded28d);
    }

    #[test]
    fn replication_and_burn_flags() {
        assert!(!Health::Online.needs_emergency_replication());
        assert!(!Health::RewardsFrozen.needs_emergency_replication());
        assert!(Health::Warning14d.needs_emergency_replication());
        assert!(Health::Degraded28d.needs_emergency_replication());
        assert!(!Health::Warning14d.burns_unvested());
        assert!(Health::Degraded28d.burns_unvested());
    }

    #[test]
    fn penalty_reset_needs_three_por_rounds() {
        assert!(!reset_downtime_penalty(0));
        assert!(!reset_downtime_penalty(2));
        assert!(reset_downtime_penalty(3));
        assert!(reset_downtime_penalty(10));
    }
}
