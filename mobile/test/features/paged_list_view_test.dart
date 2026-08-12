import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:roaming_wandering/core/error/failure.dart';
import 'package:roaming_wandering/shared/paged_state.dart';
import 'package:roaming_wandering/shared/widgets/paged_list_view.dart';

/// The infinite list, as a user experiences it.
///
/// These are widget tests rather than unit tests because the behaviours that
/// matter here are visual: does the list keep its items when a page fails, does
/// the next page load before the user reaches the bottom, does an empty result
/// offer a way out.
void main() {
  Widget harness({
    required PagedState<String> state,
    Future<void> Function()? onLoadMore,
    VoidCallback? onRetry,
  }) =>
      MaterialApp(
        home: Scaffold(
          body: PagedListView<String>(
            state: state,
            onLoadMore: onLoadMore ?? () async {},
            onRefresh: () async {},
            onRetry: onRetry ?? () {},
            emptyTitle: 'No stays match those filters',
            emptyDescription: 'Try widening the dates.',
            emptyAction: FilledButton(
              onPressed: () {},
              child: const Text('Clear filters'),
            ),
            itemBuilder: (context, item, index) =>
                SizedBox(height: 120, child: Text(item)),
          ),
        ),
      );

  testWidgets('shows skeletons on the first load, not an empty state',
      (tester) async {
    await tester.pumpWidget(harness(state: const PagedState<String>()));

    // "No results" while the first request is still in flight is a lie the
    // user will act on by changing their filters.
    expect(find.text('No stays match those filters'), findsNothing);
  });

  testWidgets('renders items once loaded', (tester) async {
    await tester.pumpWidget(
      harness(
        state: const PagedState<String>(
          items: ['Sea Breeze Villa', 'Hill House'],
          isInitialLoading: false,
        ),
      ),
    );

    expect(find.text('Sea Breeze Villa'), findsOneWidget);
    expect(find.text('Hill House'), findsOneWidget);
  });

  testWidgets('offers a way out when nothing matches', (tester) async {
    await tester.pumpWidget(
      harness(state: const PagedState<String>(isInitialLoading: false)),
    );

    expect(find.text('No stays match those filters'), findsOneWidget);
    // A dead end with no action is how a user closes the app.
    expect(find.text('Clear filters'), findsOneWidget);
  });

  testWidgets('a failed first load shows the error, not an empty list',
      (tester) async {
    await tester.pumpWidget(
      harness(
        state: const PagedState<String>(
          isInitialLoading: false,
          initialError: Failure.network(),
        ),
      ),
    );

    expect(find.text('You are offline'), findsOneWidget);
    expect(find.text('Try again'), findsOneWidget);
  });

  testWidgets('a failed page keeps the items and offers a retry',
      (tester) async {
    var retried = false;
    await tester.pumpWidget(
      harness(
        state: const PagedState<String>(
          items: ['Sea Breeze Villa'],
          nextCursor: 'page-2',
          isInitialLoading: false,
          pageError: Failure.network(),
        ),
        onRetry: () => retried = true,
      ),
    );

    // The item already on screen stays: it is still perfectly good.
    expect(find.text('Sea Breeze Villa'), findsOneWidget);

    await tester.tap(find.text('Load more'));
    expect(retried, isTrue);
  });

  testWidgets('a 409 gets no retry button', (tester) async {
    await tester.pumpWidget(
      harness(
        state: const PagedState<String>(
          isInitialLoading: false,
          initialError: Failure.api(
            status: 409,
            code: 'BOOKING_DATES_UNAVAILABLE',
            message: 'Those dates are no longer available.',
          ),
        ),
      ),
    );

    expect(find.text('Those dates are no longer available.'), findsOneWidget);
    // Retrying a conflict shows the same conflict; the button would teach the
    // user that buttons do nothing.
    expect(find.text('Try again'), findsNothing);
  });

  testWidgets('does not load the next page while the end is far away',
      (tester) async {
    var loadCalls = 0;
    await tester.pumpWidget(
      harness(
        state: PagedState<String>(
          items: List.generate(20, (i) => 'Stay $i'),
          nextCursor: 'page-2',
          isInitialLoading: false,
        ),
        onLoadMore: () async => loadCalls++,
      ),
    );

    // 20 items × 120px in a 600px viewport: a 1200px drag leaves ~1100px of
    // scroll left, well outside the 400px trigger.
    await tester.drag(find.byType(ListView), const Offset(0, -1200));
    await tester.pump();

    expect(loadCalls, isZero);
  });

  testWidgets('loads the next page before the user reaches the bottom',
      (tester) async {
    var loadCalls = 0;
    await tester.pumpWidget(
      harness(
        state: PagedState<String>(
          items: List.generate(20, (i) => 'Stay $i'),
          nextCursor: 'page-2',
          isInitialLoading: false,
        ),
        onLoadMore: () async => loadCalls++,
      ),
    );

    final controller =
        tester.widget<ListView>(find.byType(ListView)).controller!;
    // Stop 200px short of the end — inside the 400px trigger but with content
    // still below. Firing here rather than at a sentinel widget is what keeps a
    // fast fling from stalling: a bottom marker only fires once it is *built*,
    // which is already too late.
    final target = controller.position.maxScrollExtent - 200;
    await tester.drag(find.byType(ListView), Offset(0, -target));
    await tester.pump();

    expect(loadCalls, greaterThan(0));
    expect(controller.position.pixels, lessThan(controller.position.maxScrollExtent));
  });

  testWidgets('shows a spinner while the next page loads', (tester) async {
    await tester.pumpWidget(
      harness(
        state: const PagedState<String>(
          items: ['Sea Breeze Villa'],
          nextCursor: 'page-2',
          isInitialLoading: false,
        ),
      ),
    );

    expect(find.byType(CircularProgressIndicator), findsWidgets);
  });
}
