import 'dart:math' as math;
import 'dart:typed_data';

/// ElementalState handles orchestration of elementalstate functionality.
class ElementalState {
  const ElementalState({required this.index, required this.key, required this.label, required this.color, required this.glow});
  final int index;
  final String key;
  final String label;
  final int color;
  final int glow;
}

/// Constant for elementalstates.
const elementalStates = <ElementalState>[
  ElementalState(index: 0, key: 'void', label: 'Void', color: 0xFF07111F, glow: 0xFF111827),
  ElementalState(index: 1, key: 'life', label: 'Life', color: 0xFF58F58F, glow: 0xFF22C55E),
  ElementalState(index: 2, key: 'earth', label: 'Earth', color: 0xFFC08445, glow: 0xFFD97706),
  ElementalState(index: 3, key: 'water', label: 'Water', color: 0xFF38BDF8, glow: 0xFF0EA5E9),
  ElementalState(index: 4, key: 'air', label: 'Air', color: 0xFFDBEAFE, glow: 0xFF93C5FD),
  ElementalState(index: 5, key: 'fire', label: 'Fire', color: 0xFFFB7185, glow: 0xFFEF4444),
];

/// Constant for beatenby.
const beatenBy = <int, int>{2: 4, 3: 2, 4: 5, 5: 3};

/// ElementalLifeRules handles orchestration of elementalliferules functionality.
class ElementalLifeRules {
  const ElementalLifeRules({this.birth = 3, this.elementMin = 2, this.elementMax = 4, this.elementBirth = 3, this.interactionStrength = 0.65, this.decay = 0.002, this.chaos = 0.001, this.fireDuration = 2});
  final int birth, elementMin, elementMax, elementBirth;
  final double interactionStrength, decay, chaos;
  final int fireDuration;

  ElementalLifeRules copyWith({int? birth, int? elementMin, int? elementMax, int? elementBirth, double? interactionStrength, double? decay, double? chaos, int? fireDuration}) {
    return ElementalLifeRules(
      birth: birth ?? this.birth,
      elementMin: elementMin ?? this.elementMin,
      elementMax: elementMax ?? this.elementMax,
      elementBirth: elementBirth ?? this.elementBirth,
      interactionStrength: interactionStrength ?? this.interactionStrength,
      decay: decay ?? this.decay,
      chaos: chaos ?? this.chaos,
      fireDuration: fireDuration ?? this.fireDuration,
    );
  }
}

/// ElementalLifePreset handles orchestration of elementallifepreset functionality.
class ElementalLifePreset {
  const ElementalLifePreset({required this.key, required this.label, required this.stateCount, required this.rules});
  final String key, label;
  final int stateCount;
  final ElementalLifeRules rules;
}

/// Constant for defaultliferules.
const defaultLifeRules = ElementalLifeRules();

/// Constant for lifepresets.
const lifePresets = <ElementalLifePreset>[
  ElementalLifePreset(key: 'classic', label: 'Classic Life', stateCount: 2, rules: ElementalLifeRules(birth: 3, elementMin: 1, elementMax: 4, elementBirth: 3, interactionStrength: 0, decay: 0.0005, chaos: 0.0002, fireDuration: 2)),
  ElementalLifePreset(key: 'balanced', label: 'Elemental Balance', stateCount: 6, rules: defaultLifeRules),
  ElementalLifePreset(key: 'pulsation', label: 'Pulsation', stateCount: 6, rules: ElementalLifeRules(birth: 3, elementMin: 2, elementMax: 4, elementBirth: 3, interactionStrength: 0.75, decay: 0.0015, chaos: 0.0008, fireDuration: 2)),
  ElementalLifePreset(key: 'garden', label: 'Garden World', stateCount: 5, rules: ElementalLifeRules(birth: 3, elementMin: 1, elementMax: 5, elementBirth: 2, interactionStrength: 0.45, decay: 0.001, chaos: 0.0008, fireDuration: 1)),
  ElementalLifePreset(key: 'calm', label: 'Calm Elements', stateCount: 6, rules: ElementalLifeRules(birth: 4, elementMin: 3, elementMax: 4, elementBirth: 4, interactionStrength: 0.35, decay: 0.001, chaos: 0.0004, fireDuration: 1)),
];

/// Leader handles orchestration of leader functionality.
class Leader {
  const Leader(this.state, this.count);
  final int state, count;
}

/// ElementalLife handles orchestration of elementallife functionality.
class ElementalLife {
  ElementalLife({int width = 110, int height = 78, int stateCount = 6, ElementalLifeRules rules = defaultLifeRules})
    : width = width, height = height, rules = rules, cells = Uint8List(width * height), next = Uint8List(width * height), fireTicks = Uint8List(width * height) {
    this.stateCount = stateCount;
    computeStats();
  }

  final math.Random _random = math.Random();
  int width, height, stateCount = 6;
  ElementalLifeRules rules;
  Uint8List cells, next, fireTicks;
  int generation = 0;
  Map<String, int> stats = <String, int>{};

  void applyRules(ElementalLifeRules newRules) => rules = newRules;

  void setStateCount(int count) {
    stateCount = count.clamp(2, 6);
    for (var i = 0; i < cells.length; i += 1) {
      if (cells[i] >= stateCount) cells[i] = 0;
    }
  }

  void resize(int newWidth, int newHeight) {
    final oldWidth = width, oldHeight = height, oldCells = cells;
    width = newWidth.clamp(20, 260);
    height = newHeight.clamp(20, 220);
    cells = Uint8List(width * height);
    next = Uint8List(width * height);
    fireTicks = Uint8List(width * height);
    final copyWidth = math.min(oldWidth, width), copyHeight = math.min(oldHeight, height);
    for (var y = 0; y < copyHeight; y += 1) {
      for (var x = 0; x < copyWidth; x += 1) {
        cells[y * width + x] = oldCells[y * oldWidth + x];
      }
    }
    generation = 0;
    computeStats();
  }

  void randomize([double density = 0.22]) {
    // All cells are Life (state 1) or Elements (states 2-5), never Void
    for (var i = 0; i < cells.length; i += 1) {
      if (_random.nextDouble() < 0.68) {
        cells[i] = 1; // Life - primary seeded cell
      } else {
        cells[i] = _random.nextInt(4) + 2; // Elements (Earth, Water, Air, Fire)
      }
    }
    generation = 0;
    fireTicks.fillRange(0, fireTicks.length, 0);
    computeStats();
  }

  void clear() {
    cells.fillRange(0, cells.length, 0);
    next.fillRange(0, next.length, 0);
    fireTicks.fillRange(0, fireTicks.length, 0);
    generation = 0;
    computeStats();
  }

  void paint(int x, int y, int state) {
    if (x < 0 || y < 0 || x >= width || y >= height) return;
    if (state < 0 || state >= stateCount) return;
    cells[y * width + x] = state;
    fireTicks[y * width + x] = 0;
    computeStats();
  }

  void step() {
    next.fillRange(0, next.length, 0);
    final counts = Uint8List(elementalStates.length);
    final newFireTicks = Uint8List(width * height);

    for (var y = 0; y < height; y += 1) {
      for (var x = 0; x < width; x += 1) {
        fillNeighborCounts(x, y, counts);
        next[y * width + x] = resolve(y * width + x, counts, newFireTicks);
      }
    }

    final temp = cells;
    cells = next;
    next = temp;
    fireTicks = newFireTicks;
    generation += 1;
    computeStats();
  }

  void fillNeighborCounts(int x, int y, Uint8List counts) {
    counts.fillRange(0, counts.length, 0);
    final xm = x == 0 ? width - 1 : x - 1;
    final xp = x == width - 1 ? 0 : x + 1;
    final ym = y == 0 ? height - 1 : y - 1;
    final yp = y == height - 1 ? 0 : y + 1;

    void countCell(int col) => counts[cells[col]] += 1;
    countCell(ym * width + xm);
    countCell(ym * width + x);
    countCell(ym * width + xp);
    countCell(y * width + xm);
    countCell(y * width + xp);
    countCell(yp * width + xm);
    countCell(yp * width + x);
    countCell(yp * width + xp);
  }

  int aliveCount(Uint8List counts) {
    var total = 0;
    for (var state = 1; state < stateCount; state += 1) {
      total += counts[state];
    }
    return total;
  }

  Leader dominant(Uint8List counts) {
    var idx = 1, best = counts[1];
    for (var state = 2; state < stateCount; state += 1) {
      final c = counts[state];
      if (c > best) { best = c; idx = state; }
    }
    return Leader(idx, best);
  }

int resolve(int index, Uint8List counts, Uint8List newFireTicks) {
    final state = cells[index];
    if (state == 0) return _resolveVoid(counts);
    if (state == 1) return _resolveLife(index, counts);
    if (state == 5) return _resolveFire(index, counts, newFireTicks);
    return _resolveElement(state, counts, index);
  }

  int _resolveVoid(Uint8List counts) {
    // Void terraforming: (1 Life + 3 Water) OR (2 Life + 2 Water) OR (3 Life + 1 Water)
    final total = aliveCount(counts);
    final hasLife = counts[1];
    final hasWater = counts[3];
    
    if ((hasLife >= 1 && hasWater >= 3) || 
        (hasLife >= 2 && hasWater >= 2) || 
        (hasLife >= 3 && hasWater >= 1)) {
      return 2; // Earth
    }
    // Chaos spawn
    if (_random.nextDouble() < rules.chaos) return 1;
    return 0;
  }

  int _resolveLife(int index, Uint8List counts) {
    final total = aliveCount(counts);
    final hasWater = counts[3] >= 1;
    final hasFire = counts[5] >= 1;

    // Life with Fire neighbor → Fire (combustion)
    if (hasFire && !hasWater) return 5;

    // Standard Life rules
    if (total == 3) return 1;
    if (total < 2) return hasWater && _random.nextDouble() < 0.7 ? 1 : 0;
    if (total > 3 && !hasWater) return 0;
    return 1;
  }

  int _resolveFire(int index, Uint8List counts, Uint8List newFireTicks) {
    final currentTicks = fireTicks[index];
    final hasWater = counts[3] >= 1;

    // Fire with Water → Air immediately (water cycle starts)
    if (hasWater) {
      newFireTicks[index] = 1; // Will become Water next tick
      return 4; // Air
    }

    // Fire alone → dies after 2 ticks (tick 0 and tick 1 only)
    if (currentTicks >= 1) return 0; // After tick 1, dies
    newFireTicks[index] = 1;
    return 5;
  }

  int _resolveAir(int index, Uint8List counts) {
    // Air from Fire lifecycle → Water (rain returns consumed water)
    if (fireTicks[index] >= 1) return 3;
    // Pure Air → Water with Water neighbor
    if (counts[3] >= 1 && _random.nextDouble() < 0.85) return 3;
    // Air alone → Earth
    return 2;
  }

  int _resolveWater(int index, Uint8List counts) {
    final same = counts[3];
    // Water with Fire neighbor → Air (evaporation to extinguish Fire)
    if (counts[5] >= 1 && _random.nextDouble() < 0.7) return 4;
    // Water spread
    if (same >= 2) return 3;
    // Water alone decays
    if (same < 2 && _random.nextDouble() < 0.1) return 0;
    return 3;
  }

  int _resolveEarth(int index, Uint8List counts) {
    final lifeCount = counts[1];
    // Earth with 2-7 Life neighbors → Life grows
    if (lifeCount >= 2 && lifeCount <= 7 && _random.nextDouble() < 0.8) return 1;
    // Earth with Water → Water (erosion)
    if (counts[3] >= 1) return 3;
    // Earth spread
    if (counts[2] >= 3) return 2;
    // Earth alone decays
    if (counts[2] < 2 && _random.nextDouble() < 0.15) return 0;
    return 2;
  }

  int _resolveElement(int state, Uint8List counts, int index) {
    final same = counts[state];
    final predator = beatenBy[state]!;
    final predatorCount = counts[predator];
    final support = same + counts[1] * 0.45;

    if (state == 4) return _resolveAir(index, counts);
    if (state == 3) return _resolveWater(index, counts);
    if (state == 2) return _resolveEarth(index, counts);

    if (predatorCount >= math.max(2, (same * rules.interactionStrength).ceil()) && predatorCount >= same - 1) return predator;
    if (support >= rules.elementMin && support <= rules.elementMax) return state;
    if (same >= rules.elementBirth) return state;
    if (same < rules.elementMin && _random.nextDouble() < rules.decay) return 0;
    return state;
  }

  void computeStats() {
    final nextStats = <String, int>{'generation': generation, 'total': cells.length};
    for (final state in elementalStates) {
      nextStats[state.key] = 0;
    }
    for (var i = 0; i < cells.length; i += 1) {
      nextStats[elementalStates[cells[i]].key] = nextStats[elementalStates[cells[i]].key]! + 1;
    }
    stats = nextStats;
  }

/// Returns the current alive value.
  int get alive => (stats['total'] ?? 0) - (stats['void'] ?? 0);
}