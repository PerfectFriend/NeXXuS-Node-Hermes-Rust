import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:life_elements_game/main.dart';

/// Reads the numeric value shown in the "Generation" metric card.
/// Walks up from the label to the metric's Column and takes its last Text.
int generationOf(WidgetTester tester) {
  final label = find.text('Generation').evaluate().single;
  final column = label.findAncestorWidgetOfExactType<Column>()!;
  final value = column.children.whereType<Text>().last;
  return int.parse(value.data!);
}

void main() {
  testWidgets('app renders with title, tabs and stats panel', (WidgetTester tester) async {
    await tester.pumpWidget(const ElementalLifeGameApp());

    expect(find.text('Elemental Life'), findsOneWidget);
    expect(find.text('Stats'), findsOneWidget);
    expect(find.text('Controls'), findsOneWidget);
    expect(find.text('Logic'), findsOneWidget);
    expect(find.text('Generation'), findsOneWidget);
    expect(find.text('Build'), findsOneWidget);
  });

  testWidgets('Step button advances generation exactly once while paused', (WidgetTester tester) async {
    await tester.pumpWidget(const ElementalLifeGameApp());

    // Open the Controls tab and pause the auto-run ticker first, so that
    // generation changes below come only from explicit user actions.
    await tester.tap(find.text('Controls'));
    await tester.pump(const Duration(milliseconds: 100));
    await tester.tap(find.text('Pause').hitTestable());
    await tester.pumpAndSettle();

    // Read the frozen generation from the Stats tab.
    await tester.tap(find.text('Stats'));
    await tester.pumpAndSettle();
    final before = generationOf(tester);
    expect(before, greaterThanOrEqualTo(0));

    // Step exactly once from the Controls tab.
    await tester.tap(find.text('Controls'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Step').hitTestable());
    await tester.pumpAndSettle();

    // The Stats tab must now show exactly one more generation.
    await tester.tap(find.text('Stats'));
    await tester.pumpAndSettle();
    expect(generationOf(tester), before + 1);
  });
}
