# HOT
#!/usr/bin/env python3
"""
Promotion check - called by producer at :10 each hour.
Checks all active projects for promotion readiness.
Returns exit code 0 if any promoted, 1 if none promoted, 2 on error.
"""
import sys
from promote import check_all_promotable

if __name__ == "__main__":
    try:
        promoted = check_all_promotable()
        if promoted:
            print("✅ At least one project promoted")
            sys.exit(0)
        else:
            print("ℹ️ No projects ready for promotion")
            sys.exit(0)  # Exit 0 - no promotions is normal, not an error
    except Exception as e:
        print(f"❌ Error during promotion check: {e}")
        sys.exit(2)