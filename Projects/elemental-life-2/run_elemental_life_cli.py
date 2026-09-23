# HOT
#!/usr/bin/env python3
"""
Command-line interface for elemental-life-2 engine.
"""

import sys
import os
import argparse

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from elemental_life_2_core import ElementalLife2Engine

def main():
    parser = argparse.ArgumentParser(description="Run elemental-life-2 evolution engine")
    parser.add_argument("--cycles", type=int, default=0, help="Number of evolution cycles to run (default: 0 = info only, no mutation)")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--state", type=str, help="Path to state file to load/save")
    parser.add_argument("--info", action="store_true", help="Display engine information (no mutation)")
    parser.add_argument("--freeze", action="store_true", help="Freeze the engine after operations")
    parser.add_argument("--reset", action="store_true", help="Reset the engine to initial state")

    args = parser.parse_args()

    # Load or create engine
    if args.state and os.path.exists(args.state):
        print(f"Loading engine state from {args.state}")
        engine = ElementalLife2Engine.load_state(args.state)
    else:
        print("Creating new engine")
        engine = ElementalLife2Engine(config_path=args.config if args.config else None)

    # Handle reset
    if args.reset:
        result = engine.reset()
        print(result)
        if args.info:
            print_engine_info(engine)
        return

    # Display info if requested
    if args.info:
        print_engine_info(engine)

    # Run evolution cycles
    if args.cycles > 0:
        print(f"Running {args.cycles} evolution cycle(s)...")
        for i in range(args.cycles):
            result = engine.evolve()
            print(f"Cycle {i+1}: {result['message']} (Subcycle: {result['subcycle']})")
            if result["status"] == "frozen":
                break  # Цикл 14: после FROZEN дальнейшие вызовы бессмысленны (guard в evolve)

        # Save state after evolution
        state_path = args.state if args.state else "engine_state.json"  # Цикл 14: --state теперь и путь сохранения
        engine.save_state(state_path)
        print(f"State saved to {state_path}")

    # Freeze if requested
    if args.freeze:
        frozen_message = engine.freeze()
        print(frozen_message)
        # Save frozen state
        frozen_path = (args.state if args.state else "engine_state.json").rsplit(".", 1)[0] + "_frozen.json"
        engine.save_state(frozen_path)
        print(f"Frozen state saved to {frozen_path}")

def print_engine_info(engine):
    """Print current engine information."""
    print("\n=== Engine Information ===")
    print(f"Cycle: {engine.state.cycle}")
    print(f"Subcycle: {engine.state.subcycle}")
    print(f"Status: {engine.state.status}")
    print(f"Timestamp: {engine.state.timestamp}")
    print(f"Metrics: {engine.state.metrics}")
    print(f"History length: {len(engine.state_history)}")
    if engine.state.change_log:
        print(f"Recent change log entries: {engine.state.change_log[-3:]}")
    print("========================\n")

if __name__ == "__main__":
    main()