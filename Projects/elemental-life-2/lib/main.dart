import 'dart:io';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/services.dart';
import 'package:flutter/rendering.dart';

import 'elemental_life.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ElementalLifeGameApp());
}

/// ElementalLifeGameApp handles orchestration of elementallifegameapp functionality.
class ElementalLifeGameApp extends StatelessWidget {
  const ElementalLifeGameApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Elemental Life',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF020617),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF38BDF8),
          secondary: Color(0xFF58F58F),
          surface: Color(0xFF0F172A),
          error: Color(0xFFFB7185),
        ),
        cardTheme: const CardThemeData(
          color: Color(0xFF0F172A),
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(22))),
        ),
        sliderTheme: const SliderThemeData(
          activeTrackColor: Color(0xFF38BDF8),
          inactiveTrackColor: Color(0xFF1E293B),
          thumbColor: Color(0xFFDBEAFE),
          overlayColor: Color(0x3338BDF8),
        ),
      ),
      home: const ElementalLifeGame(),
    );
  }
}

/// ElementalLifeGame handles orchestration of elementallifegame functionality.
class ElementalLifeGame extends StatefulWidget {
  const ElementalLifeGame({super.key});

  @override
  State<ElementalLifeGame> createState() => _ElementalLifeGameState();
}

class _ElementalLifeGameState extends State<ElementalLifeGame> with SingleTickerProviderStateMixin {
  late ElementalLife _simulation;
  late Ticker _ticker;
  late String _presetKey;
  final GlobalKey<_LifeCanvasState> _canvasKey = GlobalKey<_LifeCanvasState>();

  bool _running = true;
  int _speed = 30;
  int _brushState = 1;
  Duration _lastStep = Duration.zero;

  @override
  void initState() {
    super.initState();
    final preset = _preset('balanced');
    _presetKey = preset.key;
    _simulation = ElementalLife(
      width: 110,
      height: 78,
      stateCount: preset.stateCount,
      rules: preset.rules,
    )..randomize(0.22);
    _ticker = createTicker(_tick)..start();
  }

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }

  ElementalLifePreset _preset(String key) {
    return lifePresets.firstWhere((preset) => preset.key == key, orElse: () => lifePresets[1]);
  }

  void _tick(Duration elapsed) {
    if (!_running) {
      return;
    }

    final interval = Duration(milliseconds: (1000 / _speed).round());
    final delta = elapsed - _lastStep;
    if (delta < interval) {
      return;
    }

    final steps = math.min(4, delta.inMilliseconds ~/ interval.inMilliseconds);
    for (var i = 0; i < steps; i += 1) {
      _simulation.step();
    }
    _lastStep = elapsed - Duration(milliseconds: delta.inMilliseconds % interval.inMilliseconds);

    if (mounted) {
      setState(() {});
    }
  }

  void _applyPreset(String key) {
    final preset = _preset(key);
    setState(() {
      _presetKey = key;
      _simulation.setStateCount(preset.stateCount);
      _simulation.applyRules(preset.rules);
      if (_brushState >= _simulation.stateCount) {
        _brushState = 1;
      }
      _simulation.randomize(0.22);
    });
  }

  void _randomize() {
    setState(() => _simulation.randomize(0.22));
  }

  void _clear() {
    setState(() => _simulation.clear());
  }

  void _stepOnce() {
    setState(() {
      _running = false;
      _simulation.step();
    });
  }

  void _toggleRunning() {
    setState(() => _running = !_running);
  }

  void _paintAt(ui.Offset position) {
    final box = context.findRenderObject() as RenderBox?;
    if (box == null || box.size.isEmpty) {
      return;
    }

    final x = (position.dx / box.size.width * _simulation.width).clamp(0, _simulation.width - 1).floor();
    final y = (position.dy / box.size.height * _simulation.height).clamp(0, _simulation.height - 1).floor();
    setState(() => _simulation.paint(x, y, _brushState));
  }

  Future<void> _savePng() async {
    final image = await _canvasKey.currentState?.captureImage();
    if (image == null) {
      return;
    }

    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
    image.dispose();
    if (bytes == null) {
      return;
    }

    final file = File('elemental-life-gen-${_simulation.generation}.png');
    await file.writeAsBytes(bytes.buffer.asUint8List());

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Saved ${file.absolute.path}')),
      );
    }
  }

  void _handleKey(KeyDownEvent event) {
    final key = event.logicalKey;
    if (key == LogicalKeyboardKey.space) {
      _toggleRunning();
    } else if (key == LogicalKeyboardKey.keyR) {
      _randomize();
    } else if (key == LogicalKeyboardKey.keyC) {
      _clear();
    } else if (key == LogicalKeyboardKey.keyE) {
      setState(() => _brushState = 0);
    } else if (key == LogicalKeyboardKey.keyL) {
      setState(() => _brushState = 1);
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3,
      child: Focus(
        autofocus: true,
        onKeyEvent: (_, event) {
          if (event is KeyDownEvent) {
            _handleKey(event);
          }
          return KeyEventResult.ignored;
        },
        child: Scaffold(
          appBar: AppBar(
            backgroundColor: Colors.transparent,
            elevation: 0,
            title: const Text('Elemental Life'),
            actions: [
              IconButton(
                icon: const Icon(Icons.help_outline),
                tooltip: 'About',
onPressed: () {
                   showDialog(
                     context: context,
                     builder: (context) => AlertDialog(
                       title: const Text('Elemental Life Game'),
                       content: const Text(
                         'A cellular automaton combining Conway\'s Game of Life with elemental interactions.\n\n'
                         '• Life connected to Fire ignites into Fire (combustion)\n'
                         '• Water protects Life from Fire; Fire + Water → Air → Water\n'
                         '• Fire alone burns for 1-3 ticks then dies to Void\n'
                         '• Air from Fire → Water (if Water present) or Earth\n\n'
                         'Controls: Space=Play/Pause, R=Random, C=Clear, E=Eraser, L=Life brush',
                       ),
                      actions: [
                        TextButton(onPressed: () => Navigator.pop(context), child: const Text('OK')),
                      ],
                    ),
                  );
                },
              ),
            ],
            bottom: PreferredSize(
              preferredSize: const Size.fromHeight(48),
              child: TabBar(
                indicatorColor: const Color(0xFF38BDF8),
                isScrollable: false,
                tabs: const [
                  Tab(text: 'Stats'),
                  Tab(text: 'Controls'),
                  Tab(text: 'Logic'),
                ],
              ),
            ),
          ),
          body: Container(
            color: const Color(0xFF020617),
            padding: const EdgeInsets.all(18),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(
                  child: LifeCanvas(
                    key: _canvasKey,
                    simulation: _simulation,
                    onPaintAt: _paintAt,
                  ),
                ),
                const SizedBox(width: 18),
                ConstrainedBox(
                  constraints: const BoxConstraints(minWidth: 320, maxWidth: 420),
                  child: Card(
                    clipBehavior: Clip.antiAlias,
                    child: TabBarView(
                      children: [
                        _statsTab(),
                        _controlsTab(),
                        _logicTab(),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _statsTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(18),
      child: _stats(),
    );
  }

  Widget _controlsTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(18),
      child: _controls(),
    );
  }

  Widget _logicTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(18),
      child: _logic(),
    );
  }

  Widget _stats() {
    final stats = _simulation.stats;
    final total = stats['total'] ?? 0;
    final alive = _simulation.alive;
    final alivePercent = total == 0 ? 0.0 : alive / total * 100;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(child: _metric('Generation', _simulation.generation.toString())),
            const SizedBox(width: 10),
            Expanded(child: _metric('Build', 'b61')),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(child: _metric('Alive', '${alive.toString()} (${alivePercent.toStringAsFixed(1)}%)')),
            const SizedBox(width: 10),
            Expanded(child: _metric('Target FPS', _speed.toString())),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(child: _metric('States', _simulation.stateCount.toString())),
          ],
        ),
        const SizedBox(height: 14),
        ...List.generate(_simulation.stateCount, (index) {
          final state = elementalStates[index];
          final value = stats[state.key] ?? 0;
          final percent = total == 0 ? 0.0 : value / total * 100;
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(
              children: [
                Container(
                  width: 12,
                  height: 12,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: Color(state.color),
                    boxShadow: [
                      BoxShadow(color: Color(state.glow).withValues(alpha: 0.7), blurRadius: 10),
                    ],
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    state.label,
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ),
                Text(
                  value.toString(),
                  style: const TextStyle(fontWeight: FontWeight.w800, fontFeatures: [FontFeature.tabularFigures()]),
                ),
                const SizedBox(width: 8),
                SizedBox(
                  width: 44,
                  child: Text(
                    '${percent.toStringAsFixed(1)}%',
                    textAlign: TextAlign.right,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey[500]),
                  ),
                ),
              ],
            ),
          );
        }),
      ],
    );
  }

  Widget _metric(String label, String value) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey[400])),
            const SizedBox(height: 4),
            Text(
              value,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
            ),
          ],
        ),
      ),
    );
  }

  Widget _controls() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _sectionTitle('Simulation'),
        DropdownButtonFormField<String>(
          initialValue: _presetKey,
          decoration: const InputDecoration(labelText: 'Preset', border: OutlineInputBorder(), isDense: true),
          items: lifePresets.map((preset) => DropdownMenuItem(value: preset.key, child: Text(preset.label))).toList(),
          onChanged: (value) {
            if (value != null) {
              _applyPreset(value);
            }
          },
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<int>(
          initialValue: _brushState,
          decoration: const InputDecoration(labelText: 'Paint Brush', border: OutlineInputBorder(), isDense: true),
          items: List.generate(
            _simulation.stateCount,
            (index) => DropdownMenuItem(
              value: index,
              child: Text(index == 0 ? 'Eraser / Void' : elementalStates[index].label),
            ),
          ).toList(),
          onChanged: (value) {
            if (value != null) {
              setState(() => _brushState = value);
            }
          },
        ),
        const SizedBox(height: 14),
        Row(
          children: [
            Expanded(child: FilledButton.icon(onPressed: _randomize, icon: const Icon(Icons.shuffle), label: const Text('Random'))),
            const SizedBox(width: 10),
            Expanded(child: OutlinedButton.icon(onPressed: _clear, icon: const Icon(Icons.delete_outline), label: const Text('Clear'))),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(child: FilledButton.tonalIcon(onPressed: _stepOnce, icon: const Icon(Icons.skip_next), label: const Text('Step'))),
            const SizedBox(width: 10),
            Expanded(
              child: FilledButton.tonalIcon(
                onPressed: _toggleRunning,
                icon: Icon(_running ? Icons.pause : Icons.play_arrow),
                label: Text(_running ? 'Pause' : 'Resume'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        FilledButton.icon(onPressed: _savePng, icon: const Icon(Icons.image), label: const Text('Save PNG')),
        const SizedBox(height: 18),
        _sectionTitle('World'),
        _slider('State Count', _simulation.stateCount.toDouble(), 2, 6, 4, (value) => '${value.round()} states', (value) {
          setState(() {
            _simulation.setStateCount(value.round());
            if (_brushState >= _simulation.stateCount) {
              _brushState = 1;
            }
          });
        }),
        _slider('Grid Size', _simulation.width.toDouble(), 40, 180, 14, (value) => '${value.round()}×${(value * 0.72).round()}', (value) {
          setState(() {
            final size = value.round();
            _simulation.resize(size, (size * 0.72).round());
            _simulation.randomize(0.22);
          });
        }),
        _slider('Speed', _speed.toDouble(), 1, 60, 59, (value) => '${value.round()} fps', (value) {
          setState(() => _speed = value.round());
        }),
        const SizedBox(height: 18),
        _sectionTitle('Life Rules'),
        _slider('Void Birth', _simulation.rules.birth.toDouble(), 1, 6, 5, (value) => '${value.round()} life neighbors', (value) {
          setState(() => _simulation.applyRules(_simulation.rules.copyWith(birth: value.round())));
        }),
        const SizedBox(height: 18),
        _sectionTitle('Element Rules'),
        _slider('Element Support Min', _simulation.rules.elementMin.toDouble(), 1, 6, 5, (value) => value.round().toString(), (value) {
          setState(() => _simulation.applyRules(_simulation.rules.copyWith(elementMin: value.round())));
        }),
        _slider('Element Support Max', _simulation.rules.elementMax.toDouble(), 2, 8, 6, (value) => value.round().toString(), (value) {
          setState(() => _simulation.applyRules(_simulation.rules.copyWith(elementMax: value.round())));
        }),
        _slider('Element Birth', _simulation.rules.elementBirth.toDouble(), 2, 6, 4, (value) => value.round().toString(), (value) {
          setState(() => _simulation.applyRules(_simulation.rules.copyWith(elementBirth: value.round())));
        }),
        _slider('Interaction', _simulation.rules.interactionStrength, 0, 1, 100, (value) => '${(value * 100).round()}%', (value) {
          setState(() => _simulation.applyRules(_simulation.rules.copyWith(interactionStrength: value)));
        }),
        _slider('Decay', _simulation.rules.decay, 0, 0.02, 200, (value) => '${(value * 10000).toStringAsFixed(0)}‱', (value) {
          setState(() => _simulation.applyRules(_simulation.rules.copyWith(decay: value)));
        }),
        _slider('Chaos', _simulation.rules.chaos, 0, 0.02, 200, (value) => '${(value * 10000).toStringAsFixed(0)}‱', (value) {
          setState(() => _simulation.applyRules(_simulation.rules.copyWith(chaos: value)));
        }),
        const SizedBox(height: 18),
        _sectionTitle('Fire Rules'),
        _slider('Fire Duration', _simulation.rules.fireDuration.toDouble(), 1, 3, 2, (value) => '${value.round()} ticks', (value) {
          setState(() => _simulation.applyRules(_simulation.rules.copyWith(fireDuration: value.round())));
        }),
      ],
    );
  }

  Widget _sectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Text(
        title,
        style: Theme.of(context).textTheme.titleSmall?.copyWith(
              color: Colors.grey[300],
              fontWeight: FontWeight.w800,
              letterSpacing: 0.08,
            ),
      ),
    );
  }

  Widget _slider(
    String label,
    double value,
    double min,
    double max,
    int divisions,
    String Function(double) labelFor,
    ValueChanged<double> onChanged,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label, style: Theme.of(context).textTheme.bodyMedium),
            Text(labelFor(value), style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey[400])),
          ],
        ),
        Slider(
          value: value,
          min: min,
          max: max,
          divisions: divisions,
          onChanged: onChanged,
        ),
      ],
    );
  }

  Widget _logic() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Rules of Elemental Life', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800)),
        const SizedBox(height: 10),
        _logicLine('Life connected to Fire ignites into Fire (combustion).'),
        _logicLine('Water protects adjacent Life from Fire (quenching).'),
        _logicLine('Fire lifecycle: Fire → Water → Air (if no Water) → Void.'),
        _logicLine('Fire + Water → Air (vapor) 1 tick → Water (rain).'),
        _logicLine('Fire alone burns for 1-3 ticks then dies to Void.'),
        _logicLine('Life survives on 2-3 neighbors; Water-connected Life protected.'),
        _logicLine('Life with <2 neighbors dies; without Water becomes Earth.'),
        _logicLine('Void erupts as Fire when overcrowded (8 neighbors).'),
        _logicLine('Void near Water becomes Earth.'),
        _logicLine('Earth with Life+Water neighbors converts to Life (germination).'),
        _logicLine('Air with Water neighbors becomes Water (rain).'),
        _logicLine('Water with Fire becomes Air (evaporation).'),
        _logicLine('Elemental cycle: Fire→Air→Earth→Water→Fire.'),
      ],
    );
  }

  Widget _logicLine(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(text, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey[400])),
    );
  }
}

/// LifeCanvas handles orchestration of lifecanvas functionality.
class LifeCanvas extends StatefulWidget {
  const LifeCanvas({
    super.key,
    required this.simulation,
    required this.onPaintAt,
  });

  final ElementalLife simulation;
  final ValueChanged<ui.Offset> onPaintAt;

  @override
  State<LifeCanvas> createState() => _LifeCanvasState();
}

class _LifeCanvasState extends State<LifeCanvas> {
  final GlobalKey _boundaryKey = GlobalKey(debugLabel: 'repaintBoundary');

  Future<ui.Image?> captureImage() async {
    final renderObject = _boundaryKey.currentContext?.findRenderObject();
    if (renderObject is RenderRepaintBoundary) {
      return renderObject.toImage(pixelRatio: MediaQuery.of(context).devicePixelRatio);
    }
    return null;
  }

  void _paint(ui.Offset position) {
    widget.onPaintAt(position);
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (_, constraints) => GestureDetector(
        behavior: HitTestBehavior.translucent,
        onPanStart: (details) => _paint(details.localPosition),
        onPanUpdate: (details) => _paint(details.localPosition),
        onTapDown: (details) => _paint(details.localPosition),
        child: RepaintBoundary(
          key: _boundaryKey,
          child: Container(
            color: const Color(0xFF07111F),
            child: CustomPaint(
              size: constraints.biggest,
              painter: LifePainter(widget.simulation),
            ),
          ),
        ),
      ),
    );
  }
}

/// LifePainter handles orchestration of lifepainter functionality.
class LifePainter extends CustomPainter {
  LifePainter(this.simulation);

  final ElementalLife simulation;

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) {
      return;
    }
    final bgPaint = Paint()..color = const Color(0xFF0D1321);
    canvas.drawRect(Offset.zero & size, bgPaint);
    _drawStars(canvas, size);

    final cellSize = math.max(3, (math.min(size.width / simulation.width, size.height / simulation.height)).floorToDouble()).toInt();
    final gridWidth = cellSize * simulation.width.toDouble();
    final gridHeight = cellSize * simulation.height.toDouble();
    final offsetX = ((size.width - gridWidth) / 2).floorToDouble();
    final offsetY = ((size.height - gridHeight) / 2).floorToDouble();

    final borderPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.18)
      ..strokeWidth = 1;
    canvas.drawRect(
      Rect.fromLTWH(offsetX - 0.5, offsetY - 0.5, gridWidth + 1.0, gridHeight + 1.0),
      borderPaint,
    );

    final glowPaint = Paint()
      ..style = PaintingStyle.fill
      ..maskFilter = const ui.MaskFilter.blur(ui.BlurStyle.normal, 10);

    for (var y = 0; y < simulation.height; y += 1) {
      for (var x = 0; x < simulation.width; x += 1) {
        final stateIndex = simulation.cells[y * simulation.width + x];
        if (stateIndex == 0) {
          continue;
        }

        final state = elementalStates[stateIndex];
        final rect = Rect.fromLTWH(
          offsetX + x * cellSize.toDouble() + 0.5,
          offsetY + y * cellSize.toDouble() + 0.5,
          cellSize > 1 ? cellSize.toDouble() - 1 : 1,
          cellSize > 1 ? cellSize.toDouble() - 1 : 1,
        );
        final flicker = stateIndex == 5
            ? 0.78 + 0.22 * math.sin((x * 13 + y * 7 + simulation.generation) * 0.17)
            : 1.0;

        glowPaint
          ..color = ui.Color(state.glow).withValues(alpha: stateIndex == 1 || stateIndex == 5 ? 0.24 : 0.14)
          ..maskFilter = ui.MaskFilter.blur(
            ui.BlurStyle.normal,
            (cellSize * (stateIndex == 1 || stateIndex == 5 ? 0.22 : 0.1)).toDouble());
        canvas.drawRect(rect, glowPaint);

        final cellPaint = Paint()..style = PaintingStyle.fill;
        cellPaint
          ..color = ui.Color(state.color).withValues(alpha: stateIndex == 4 ? 0.62 : flicker);
        canvas.drawRect(rect, cellPaint);

        if (cellSize >= 5 && stateIndex == 1) {
          final center = Offset(rect.left + rect.width * 0.5, rect.top + rect.height * 0.5);
          final radius = cellSize * 0.16;
          canvas.drawOval(
            Rect.fromCircle(center: center, radius: radius),
            Paint()..color = const ui.Color(0xFFDCFCE7).withValues(alpha: 0.85),
          );
        }
      }
    }

    if (cellSize >= 2) {
      final gridPaint = Paint()
        ..color = const ui.Color(0xFF64748B).withValues(alpha: 0.3)
        ..strokeWidth = 0.8;
      canvas.drawLine(Offset(offsetX, offsetY), Offset(offsetX + gridWidth, offsetY), gridPaint);
      canvas.drawLine(Offset(offsetX, offsetY + gridHeight), Offset(offsetX + gridWidth, offsetY + gridHeight), gridPaint);
      canvas.drawLine(Offset(offsetX, offsetY), Offset(offsetX, offsetY + gridHeight), gridPaint);
      canvas.drawLine(Offset(offsetX + gridWidth, offsetY), Offset(offsetX + gridWidth, offsetY + gridHeight), gridPaint);
    }
  }

  void _drawStars(Canvas canvas, Size size) {
    final count = math.min(120, (size.width * size.height / 9000).floor());
    final starPaint = Paint();
    for (var i = 0; i < count; i += 1) {
      final x = (i * 97) % size.width;
      final y = (i * 53) % size.height;
      final pulse = 0.35 + 0.35 * math.sin((simulation.generation + i) * 0.03);
      starPaint.color = const ui.Color(0xFFE2E8F0).withValues(alpha: pulse);
      canvas.drawRect(Offset(x, y) & const Size(1, 1), starPaint);
    }
  }

  @override
  bool shouldRepaint(covariant LifePainter oldDelegate) => true;
}