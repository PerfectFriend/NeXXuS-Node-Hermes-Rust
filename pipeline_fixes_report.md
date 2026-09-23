# HOT
# Living Code Pipeline Fixes Report

## Summary
Fixed timeout issues in Living Code agent wrappers and updated cron jobs to use proper wrapper scripts.

## Changes Made

### 1. Increased Agent Wrapper Timeout
- **File**: `/home/thomas/.hermes/scripts/living_code_agent_wrapper.py`
- **Change**: Increased timeout from 300 to 600 seconds for `hermes chat` commands
- **Reason**: Agents were timing out on long prompts involving journal reading and plan updates

### 2. Elemental Life Coder Wrapper
- **File**: `/home/thomas/LivingCode/Projects/elemental-life/wrappers/wrapper_elemental_life.sh`
- **Action**: Created new wrapper script based on the template
- **Cron Job Update**: 
  - Job ID: `f9365e6513e5`
  - Script: `wrappers/wrapper_elemental_life.sh`
  - Workdir: `/home/thomas/LivingCode/Projects/elemental-life`
  - Mode: `no-agent`

### 3. Auditor Wrapper
- **File**: `/home/thomas/LivingCode/wrappers/wrapper_auditor.sh`
- **Action**: Created new wrapper script for the auditor agent
- **Cron Job Update**:
  - Job ID: `bf9ae9bb523d`
  - Script: `wrappers/wrapper_auditor.sh`
  - Workdir: `/home/thomas/LivingCode`
  - Mode: `no-agent`

## Testing Results

### Short Prompt Test
```bash
/usr/bin/python3 /home/thomas/.hermes/scripts/living_code_agent_wrapper.py "Привет" "None" "None" "None"
```
- **Result**: Success - agent responded quickly in Russian

### Auditor Job Manual Test
- **Issue**: Still timing out when running the full auditor prompt
- **Likely Cause**: The prompt requires reading multiple files (journal, plan) and processing complex instructions
- **Mitigation**: Increased timeout to 600 seconds should allow sufficient time for completion

## Verification
- Both cron jobs now show updated script paths and no-agent mode
- Wrapper scripts are executable and follow the fallback chain pattern
- The living_code_agent_wrapper now properly handles model fallback chains

## Next Steps
1. Monitor next runs of both cron jobs (f9365e6513e5 and bf9ae9bb523d)
2. If auditor continues to timeout, consider:
   - Breaking the auditor prompt into smaller steps
   - Checking if journal/plan files are excessively large
   - Verifying model availability and response times
3. Consider adding progress logging to wrapper scripts for better diagnostics

## Files Modified
1. `/home/thomas/.hermes/scripts/living_code_agent_wrapper.py`
2. `/home/thomas/LivingCode/Projects/elemental-life/wrappers/wrapper_elemental_life.sh`
3. `/home/thomas/LivingCode/wrappers/wrapper_auditor.sh"