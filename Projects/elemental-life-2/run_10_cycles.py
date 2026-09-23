# HOT
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from elemental_life_2_core import ElementalLife2Engine

engine = ElementalLife2Engine()
print(f"Starting state: cycle={engine.state.cycle}, subcycle={engine.state.subcycle}, status={engine.state.status}")
for i in range(10):
    result = engine.evolve()
    print(f"Cycle {i+1}: {result['message']} (subcycle={result['subcycle']})")
    if result['status'] != 'success':
        print(f"Warning: evolution returned status {result['status']}")
print(f"Final state: cycle={engine.state.cycle}, subcycle={engine.state.subcycle}, status={engine.state.status}")
# Save state
engine.save_state("engine_state.json")
print("State saved to engine_state.json")