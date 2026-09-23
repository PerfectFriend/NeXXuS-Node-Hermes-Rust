# HOT
import re

with open('elemental_life_2_core.py', 'r', encoding='utf-8') as f:
    content = f.read()

# New evolve method text with proper indentation (4 spaces)
new_evolve_method = '''    def evolve(self, state: ElementalLife2State) -> ElementalLife2State:
        """Default evolution strategy that increments cycle and subcycle and updates metrics."""
        new_state = replace(state)
        new_state.cycle += 1
        new_state.subcycle += 1
        new_state.metrics['evolution_step'] = new_state.subcycle
        new_state.status = "EVOLVED"
        new_state.timestamp = datetime.now().isoformat()
        # Add a change log entry
        new_state.change_log.append(f"Evolution step {new_state.subcycle} at {new_state.timestamp}")
        return new_state'''

# Pattern to find the class DefaultEvolutionStrategy and replace its evolve method.
# We'll use a regex that matches from the class line until the end of the class (next class or end of file)
# but we want to keep the class docstring if any.
# Simpler: replace the entire class with a new one.
# We'll construct the new class.

new_class = '''class DefaultEvolutionStrategy(EvolutionStrategy):
    """Default evolution strategy that increments cycle and subcycle and updates metrics."""

    def evolve(self, state: ElementalLife2State) -> ElementalLife2State:
        """Default evolution strategy that increments cycle and subcycle and updates metrics."""
        new_state = replace(state)
        new_state.cycle += 1
        new_state.subcycle += 1
        new_state.metrics['evolution_step'] = new_state.subcycle
        new_state.status = "EVOLVED"
        new_state.timestamp = datetime.now().isoformat()
        # Add a change log entry
        new_state.change_log.append(f"Evolution step {new_state.subcycle} at {new_state.timestamp}")
        return new_state'''

# Find the class definition and replace it.
# We'll use regex to match the class from 'class DefaultEvolutionStrategy(EvolutionStrategy):' 
# until the next line that starts with 'class ' (with same indentation) or end of string.
# We'll use re.DOTALL to match across lines.
pattern = re.compile(r'class DefaultEvolutionStrategy\(EvolutionStrategy\):.*?(?=\nclass |\Z)', re.DOTALL)
match = pattern.search(content)
if match:
    # Replace the matched class with new_class
    content = content[:match.start()] + new_class + content[match.end():]
    print("Replaced DefaultEvolutionStrategy class")
else:
    print("Could not find DefaultEvolutionStrategy class")
    exit(1)

with open('elemental_life_2_core.py', 'w', encoding='utf-8') as f:
    f.write(content)
