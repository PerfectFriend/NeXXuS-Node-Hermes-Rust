//! 16 GB section accounting and dynamic vault quota.
//! Ported from TS `storageManager.ts` formulas, but in integer micro-NEXX / integer GB.

use nexxus_core::types::Money;

use crate::{
    BASE_VAULT_REWARD_GB, EXPANDED_VAULT_RATIO_DEN, EXPANDED_VAULT_RATIO_NUM, SECTION_SIZE_GB,
};

/// Result of carving free disk space into 16 GB barter sections.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SectionSplit {
    pub sections_16gb: u64,
    pub remainder_gb: u64,
    /// Vault quota granted to the operator for contributing sections.
    pub vault_quota_gb: u64,
}

/// Splits a free-space amount (GB, including external devices) into sections.
/// Base 16 GB yields a 2 GB vault; every extra section adds 1/8 of 16 GB = 2 GB.
/// All arithmetic is saturating — a hostile u64::MAX input must not panic or wrap.
pub fn split_into_sections(free_gb: u64) -> SectionSplit {
    let sections_16gb = free_gb / SECTION_SIZE_GB;
    let remainder_gb = free_gb % SECTION_SIZE_GB;

    let vault_quota_gb = if sections_16gb == 0 {
        0
    } else {
        let extra_gb = (sections_16gb - 1).saturating_mul(SECTION_SIZE_GB);
        BASE_VAULT_REWARD_GB.saturating_add(extra_gb.saturating_mul(EXPANDED_VAULT_RATIO_NUM) / EXPANDED_VAULT_RATIO_DEN)
    };

    SectionSplit {
        sections_16gb,
        remainder_gb,
        vault_quota_gb,
    }
}

/// Daily storer reward for a given amount of foreign GB actually held.
/// Saturates at i64::MAX micro-NEXX instead of wrapping on huge inputs.
pub fn daily_storer_reward(foreign_gb: u64) -> Money {
    let gb = i64::try_from(foreign_gb).unwrap_or(i64::MAX);
    Money(crate::DAILY_NEXX_RATE_PER_GB.saturating_mul(gb))
}

/// Daily cost paid to treasury for a subscribed GB amount.
/// Saturates at i64::MAX micro-NEXX instead of wrapping on huge inputs.
pub fn daily_subscription_cost(subscribed_gb: u64) -> Money {
    let gb = i64::try_from(subscribed_gb).unwrap_or(i64::MAX);
    Money(crate::SUBSCRIPTION_DAILY_COST_PER_GB.saturating_mul(gb))
}

/// Anti-loop Sybil invariant (README §economics):
/// `Fee_writer (1.30) > Reward_storer (1.25)` NEXX/GB/day must hold strictly.
pub fn anti_loop_invariant_holds() -> bool {
    crate::SUBSCRIPTION_DAILY_COST_PER_GB > crate::DAILY_NEXX_RATE_PER_GB
}

/// Yield per GB per day if a node stores its own data:
/// reward earned minus fee paid. Strictly negative when the invariant holds,
/// which mathematically neutralizes farming attacks.
pub fn self_dealing_yield_per_gb() -> Money {
    Money(crate::DAILY_NEXX_RATE_PER_GB - crate::SUBSCRIPTION_DAILY_COST_PER_GB)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn base_16gb_gives_2gb_vault() {
        let s = split_into_sections(16);
        assert_eq!(s.sections_16gb, 1);
        assert_eq!(s.remainder_gb, 0);
        assert_eq!(s.vault_quota_gb, 2);
    }

    #[test]
    fn extra_sections_add_one_eighth() {
        // 48 GB = 3 sections -> 2 + 2*16/8 = 2 + 4 = 6 GB
        let s = split_into_sections(48);
        assert_eq!(s.sections_16gb, 3);
        assert_eq!(s.vault_quota_gb, 6);
    }

    #[test]
    fn below_one_section_grants_nothing() {
        let s = split_into_sections(15);
        assert_eq!(s.sections_16gb, 0);
        assert_eq!(s.remainder_gb, 15);
        assert_eq!(s.vault_quota_gb, 0);
    }

    #[test]
    fn economics_are_integer_exact() {
        assert_eq!(daily_storer_reward(8).to_decimal_string(), "10");
        assert_eq!(daily_subscription_cost(10).to_decimal_string(), "13");
    }

    #[test]
    fn anti_loop_invariant_holds() {
        assert!(super::anti_loop_invariant_holds());
        // self-dealing is strictly negative: 1.25 - 1.30 = -0.05 NEXX/GB/day
        assert_eq!(super::self_dealing_yield_per_gb().to_decimal_string(), "-0.05");
    }

    #[test]
    fn huge_gb_inputs_saturate_instead_of_wrapping() {
        // Econ overflow regression: u64::MAX GB must not panic or wrap to negative.
        let r = daily_storer_reward(u64::MAX);
        assert_eq!(r.0, i64::MAX);
        let c = daily_subscription_cost(u64::MAX);
        assert_eq!(c.0, i64::MAX);
        // boundary: largest gb that fits i64
        let r = daily_storer_reward(i64::MAX as u64);
        assert_eq!(r.0, i64::MAX); // 1.25e9 * i64::MAX saturates
        // split_into_sections must not panic on u64::MAX either
        let s = split_into_sections(u64::MAX);
        assert_eq!(s.sections_16gb, u64::MAX / SECTION_SIZE_GB);
    }

    #[test]
    fn money_arithmetic_is_saturating_not_wrapping() {
        // direct invariant: reward never becomes negative due to overflow
        for gb in [0u64, 1, 16, 1_000_000, u64::MAX / 2, u64::MAX] {
            assert!(daily_storer_reward(gb).0 >= 0);
            assert!(daily_subscription_cost(gb).0 >= 0);
        }
    }
}
