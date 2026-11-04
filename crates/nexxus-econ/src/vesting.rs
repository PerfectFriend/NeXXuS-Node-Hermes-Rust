//! Linear 8-week (56-day) vesting of earned rewards — anti "download and switch off".
//! Ported from the TS baseline vesting logic; integer math only.

use nexxus_core::types::Money;

use crate::VESTING_LOCK_DAYS;

/// A vesting schedule for one reward grant: `total` micro-NEXX unlocking linearly
/// over `VESTING_LOCK_DAYS` days from grant time.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VestingSchedule {
    pub total: Money,
    pub elapsed_days: u64,
    burned: Money,
}

impl VestingSchedule {
    pub fn new(total: Money) -> Self {
        Self {
            total,
            elapsed_days: 0,
            burned: Money::zero(),
        }
    }

    /// Advance the schedule by `days` (idempotent accumulation).
    pub fn advance(&mut self, days: u64) {
        self.elapsed_days = self.elapsed_days.saturating_add(days);
    }

    /// Amount vested (unlocked) so far. Linear: total * elapsed / LOCK, clamped.
    pub fn vested(&self) -> Money {
        if self.elapsed_days >= VESTING_LOCK_DAYS {
            return self.total;
        }
        Money(self.total.0 * self.elapsed_days as i64 / VESTING_LOCK_DAYS as i64)
    }

    /// Amount still locked (not yet vested and not burned).
    pub fn unvested(&self) -> Money {
        Money(self.total.0 - self.vested().0 - self.burned.0)
    }

    pub fn is_fully_vested(&self) -> bool {
        self.elapsed_days >= VESTING_LOCK_DAYS
    }

    /// Burn the unvested remainder (28-day offline slashing, spec 4.3).
    /// Returns the burned amount; already-vested funds are untouched.
    pub fn burn_unvested(&mut self) -> Money {
        let burned = self.unvested();
        self.burned = Money(self.burned.0 + burned.0);
        burned
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn linear_vesting_halfway() {
        let mut s = VestingSchedule::new(Money(1_120_000_000_000)); // 1120 NEXX
        s.advance(28); // half of 56 days
        assert_eq!(s.vested().to_decimal_string(), "560");
        assert_eq!(s.unvested().to_decimal_string(), "560");
        assert!(!s.is_fully_vested());
    }

    #[test]
    fn fully_vested_at_56_days() {
        let mut s = VestingSchedule::new(Money(56_000_000));
        s.advance(56);
        assert!(s.is_fully_vested());
        assert_eq!(s.vested(), s.total);
        assert_eq!(s.unvested().0, 0);
    }

    #[test]
    fn beyond_lock_stays_clamped() {
        let mut s = VestingSchedule::new(Money(100_000_000));
        s.advance(365);
        assert_eq!(s.vested(), s.total);
    }

    #[test]
    fn burn_unvested_keeps_vested_part() {
        let mut s = VestingSchedule::new(Money(1_120_000_000_000));
        s.advance(28);
        let burned = s.burn_unvested();
        assert_eq!(burned.to_decimal_string(), "560");
        assert_eq!(s.vested().to_decimal_string(), "560");
        assert_eq!(s.unvested().0, 0);
        assert!(!s.is_fully_vested()); // 28 из 56 дней — не полностью
    }
}
