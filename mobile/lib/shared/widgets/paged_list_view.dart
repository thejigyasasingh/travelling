import 'package:flutter/material.dart';

import '../../core/error/failure.dart';
import '../../core/theme/app_theme.dart';
import '../paged_state.dart';
import 'state_views.dart';

/// An infinitely-scrolling list over [PagedState].
///
/// Three decisions are worth naming:
///
/// **The trigger is a scroll extent, not a sentinel widget at the bottom.** A
/// "load more" widget only fires once it is built, which on a fast fling is
/// already too late and produces a visible stall. Firing at 400 logical pixels
/// from the end means the next page is usually there before the user reaches
/// it.
///
/// **A failed page keeps the list.** Page four failing shows a retry row under
/// pages one to three; it does not blank the screen, because the content
/// already on it is still perfectly good.
///
/// **`loadMore` is safe to call on every scroll frame.** The notifier guards on
/// `canLoadMore`, so the widget does not need its own debounce — and a guard in
/// two places is a guard that eventually disagrees with itself.
class PagedListView<T> extends StatefulWidget {
  const PagedListView({
    required this.state,
    required this.itemBuilder,
    required this.onLoadMore,
    required this.onRefresh,
    required this.onRetry,
    super.key,
    this.emptyTitle = 'Nothing here yet',
    this.emptyDescription,
    this.emptyIcon,
    this.emptyAction,
    this.skeletonBuilder,
    this.skeletonCount = 5,
    this.padding = const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
    this.separator = const SizedBox(height: 12),
    this.header,
  });

  final PagedState<T> state;
  final Widget Function(BuildContext context, T item, int index) itemBuilder;
  final Future<void> Function() onLoadMore;
  final Future<void> Function() onRefresh;
  final VoidCallback onRetry;

  final String emptyTitle;
  final String? emptyDescription;
  final IconData? emptyIcon;
  final Widget? emptyAction;

  final Widget Function(BuildContext context)? skeletonBuilder;
  final int skeletonCount;
  final EdgeInsets padding;
  final Widget separator;
  final Widget? header;

  @override
  State<PagedListView<T>> createState() => _PagedListViewState<T>();
}

class _PagedListViewState<T> extends State<PagedListView<T>> {
  final _controller = ScrollController();

  static const _loadMoreThreshold = 400.0;

  @override
  void initState() {
    super.initState();
    _controller.addListener(_onScroll);
  }

  @override
  void dispose() {
    _controller
      ..removeListener(_onScroll)
      ..dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_controller.hasClients) return;
    final remaining =
        _controller.position.maxScrollExtent - _controller.position.pixels;
    if (remaining <= _loadMoreThreshold) {
      // Fire-and-forget: the notifier no-ops unless there is a page to fetch.
      widget.onLoadMore();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;

    if (state.isInitialLoading) {
      return _SkeletonList(
        builder: widget.skeletonBuilder,
        count: widget.skeletonCount,
        padding: widget.padding,
        separator: widget.separator,
      );
    }

    final initialError = state.initialError;
    if (initialError != null && state.items.isEmpty) {
      return ErrorView(failure: initialError, onRetry: widget.onRefresh);
    }

    if (state.isEmpty) {
      return RefreshIndicator(
        onRefresh: widget.onRefresh,
        // A scrollable is required for pull-to-refresh to work at all, and an
        // empty state that cannot be pulled leaves the user stuck.
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            if (widget.header != null) widget.header!,
            SizedBox(
              height: MediaQuery.sizeOf(context).height * 0.55,
              child: EmptyView(
                title: widget.emptyTitle,
                description: widget.emptyDescription,
                icon: widget.emptyIcon,
                action: widget.emptyAction,
              ),
            ),
          ],
        ),
      );
    }

    final headerCount = widget.header != null ? 1 : 0;

    return RefreshIndicator(
      onRefresh: widget.onRefresh,
      child: ListView.separated(
        controller: _controller,
        physics: const AlwaysScrollableScrollPhysics(),
        padding: widget.padding,
        itemCount: headerCount + state.rowCount,
        separatorBuilder: (_, index) =>
            index < headerCount ? const SizedBox.shrink() : widget.separator,
        itemBuilder: (context, index) {
          if (widget.header != null && index == 0) return widget.header!;
          final itemIndex = index - headerCount;

          if (itemIndex < state.items.length) {
            return widget.itemBuilder(context, state.items[itemIndex], itemIndex);
          }
          return _TrailingRow(state: state, onRetry: widget.onRetry);
        },
      ),
    );
  }
}

/// The row after the last item: a spinner, a retry, or nothing.
class _TrailingRow<T> extends StatelessWidget {
  const _TrailingRow({required this.state, required this.onRetry});

  final PagedState<T> state;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final pageError = state.pageError;

    if (pageError != null) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 24),
        child: Column(
          children: [
            Text(
              pageError.message,
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              textAlign: TextAlign.center,
            ),
            Gap.sm,
            OutlinedButton(
              onPressed: onRetry,
              child: const Text('Load more'),
            ),
          ],
        ),
      );
    }

    if (state.hasMore) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 28),
        child: Center(
          child: SizedBox(
            width: 22,
            height: 22,
            child: CircularProgressIndicator(strokeWidth: 2.5),
          ),
        ),
      );
    }

    return const SizedBox.shrink();
  }
}

class _SkeletonList extends StatelessWidget {
  const _SkeletonList({
    required this.builder,
    required this.count,
    required this.padding,
    required this.separator,
  });

  final Widget Function(BuildContext context)? builder;
  final int count;
  final EdgeInsets padding;
  final Widget separator;

  @override
  Widget build(BuildContext context) => ListView.separated(
        padding: padding,
        itemCount: count,
        separatorBuilder: (_, _) => separator,
        itemBuilder: (context, _) =>
            builder?.call(context) ??
            const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ShimmerBox(height: 160, radius: 16),
                Gap.sm,
                ShimmerBox(width: 200),
                Gap.xs,
                ShimmerBox(width: 120, height: 12),
              ],
            ),
      );
}
