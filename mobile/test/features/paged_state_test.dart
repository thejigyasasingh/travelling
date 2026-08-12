import 'package:flutter_test/flutter_test.dart';
import 'package:roaming_wandering/core/error/failure.dart';
import 'package:roaming_wandering/shared/paged_state.dart';

/// The states an infinite list can actually be in.
///
/// The reason this is not `AsyncValue<List<T>>`: a paged list has states that
/// type cannot express, and a user can plainly see the difference. Collapsing
/// them into "loading" or "error" is what produces a list that blanks itself
/// when the fourth page fails.
void main() {
  group('row counting', () {
    test('adds a trailing row while more pages exist', () {
      const state = PagedState<String>(
        items: ['a', 'b'],
        nextCursor: 'cursor-2',
        isInitialLoading: false,
      );
      // Two items plus the loading indicator.
      expect(state.rowCount, 3);
      expect(state.hasMore, isTrue);
    });

    test('adds no trailing row on the last page', () {
      const state = PagedState<String>(items: ['a', 'b'], isInitialLoading: false);
      expect(state.rowCount, 2);
      expect(state.hasMore, isFalse);
    });

    test('keeps a trailing row for the retry when a page failed', () {
      const state = PagedState<String>(
        items: ['a'],
        isInitialLoading: false,
        pageError: Failure.network(),
      );
      expect(state.rowCount, 2);
    });
  });

  group('load-more guard', () {
    test('allows loading when there is a next page', () {
      const state = PagedState<String>(
        items: ['a'],
        nextCursor: 'c',
        isInitialLoading: false,
      );
      expect(state.canLoadMore, isTrue);
    });

    test('refuses while a page is already loading', () {
      // The widget calls loadMore on every scroll frame; without this guard a
      // fling would fire a dozen identical requests.
      const state = PagedState<String>(
        items: ['a'],
        nextCursor: 'c',
        isInitialLoading: false,
        isLoadingMore: true,
      );
      expect(state.canLoadMore, isFalse);
    });

    test('refuses after a page error, until the user retries', () {
      const state = PagedState<String>(
        items: ['a'],
        nextCursor: 'c',
        isInitialLoading: false,
        pageError: Failure.network(),
      );
      // Otherwise scrolling at the bottom of a failed list retries forever,
      // silently, against a server that is already unhappy.
      expect(state.canLoadMore, isFalse);
    });

    test('refuses when there is no next page', () {
      const state = PagedState<String>(items: ['a'], isInitialLoading: false);
      expect(state.canLoadMore, isFalse);
    });
  });

  group('empty', () {
    test('is empty only once loading has finished without error', () {
      const loading = PagedState<String>();
      const loaded = PagedState<String>(isInitialLoading: false);
      const failed = PagedState<String>(
        isInitialLoading: false,
        initialError: Failure.network(),
      );

      // A spinner is not an empty state, and neither is an error — showing
      // "nothing found" for a failed request is a lie about the data.
      expect(loading.isEmpty, isFalse);
      expect(loaded.isEmpty, isTrue);
      expect(failed.isEmpty, isFalse);
    });
  });

  group('a failed page keeps the list', () {
    test('items survive a page error', () {
      const state = PagedState<String>(
        items: ['a', 'b', 'c'],
        nextCursor: 'c4',
        isInitialLoading: false,
      );
      final afterFailure = state.copyWith(
        isLoadingMore: false,
        pageError: const Failure.network(),
      );

      // Page four failing must not blank pages one to three — they are what
      // the user is looking at.
      expect(afterFailure.items, ['a', 'b', 'c']);
      expect(afterFailure.initialError, isNull);
    });
  });
}
