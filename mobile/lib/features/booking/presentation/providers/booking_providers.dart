import 'dart:async';

import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../../core/network/result.dart';
import '../../../../core/providers/repository_providers.dart';
import '../../../../shared/paged_state.dart';
import '../../data/models/booking_models.dart';
import '../../data/repositories/booking_repository.dart';
import '../../domain/entities/booking_status.dart';

part 'booking_providers.g.dart';

/// The guest's trips, paginated.
@riverpod
class BookingsList extends _$BookingsList {
  @override
  PagedState<BookingDto> build() {
    unawaited(_loadFirstPage());
    return const PagedState(isInitialLoading: true);
  }

  Future<void> _loadFirstPage() async {
    final result = await ref.read(bookingRepositoryProvider).list();
    state = switch (result) {
      Ok<BookingPage>(:final value) => PagedState(
          items: value.items,
          nextCursor: value.nextCursor,
          isInitialLoading: false,
          isStale: value.isStale,
          cachedAt: value.cachedAt,
        ),
      Err<BookingPage>(:final failure) =>
        PagedState(isInitialLoading: false, initialError: failure),
    };
  }

  Future<void> loadMore() async {
    final current = state;
    if (!current.canLoadMore) return;
    state = current.copyWith(isLoadingMore: true, pageError: null);

    final result =
        await ref.read(bookingRepositoryProvider).list(cursor: current.nextCursor);
    state = switch (result) {
      Ok<BookingPage>(:final value) => state.copyWith(
          items: [...state.items, ...value.items],
          nextCursor: value.nextCursor,
          isLoadingMore: false,
        ),
      Err<BookingPage>(:final failure) =>
        state.copyWith(isLoadingMore: false, pageError: failure),
    };
  }

  Future<void> refresh() async {
    state = state.copyWith(isRefreshing: true);
    await _loadFirstPage();
  }
}

/// Trips split the way they are actually used: "where am I going and can I
/// still change it" versus "find me that invoice". One reverse-chronological
/// list serves neither.
@riverpod
List<BookingDto> upcomingTrips(Ref ref) => ref
    .watch(bookingsListProvider)
    .items
    .where((b) => BookingStatus.parse(b.status).isActive)
    .toList(growable: false);

@riverpod
List<BookingDto> pastTrips(Ref ref) => ref
    .watch(bookingsListProvider)
    .items
    .where((b) => !BookingStatus.parse(b.status).isActive)
    .toList(growable: false);

/// One booking.
///
/// Polls while payment is settling: the webhook confirms a booking server-side
/// moments after the gateway callback, and a guest staring at "payment pending"
/// with no way to know it has cleared will pay again. Polling stops the moment
/// the status settles — a confirmed booking never changes on its own.
@riverpod
class BookingDetail extends _$BookingDetail {
  Timer? _poll;

  @override
  FutureOr<BookingDto> build(String bookingId) async {
    ref.onDispose(() => _poll?.cancel());

    final result = await ref.read(bookingRepositoryProvider).get(bookingId);
    return switch (result) {
      Ok<BookingDto>(:final value) => _schedulePoll(value),
      Err<BookingDto>(:final failure) => throw failure,
    };
  }

  BookingDto _schedulePoll(BookingDto booking) {
    _poll?.cancel();
    if (BookingStatus.parse(booking.status).isPayable) {
      _poll = Timer(const Duration(seconds: 12), () {
        ref.invalidateSelf();
      });
    }
    return booking;
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}

@riverpod
Future<RefundPreviewDto> refundPreview(Ref ref, String bookingId) async {
  final result = await ref.read(bookingRepositoryProvider).refundPreview(bookingId);
  return switch (result) {
    Ok<RefundPreviewDto>(:final value) => value,
    Err<RefundPreviewDto>(:final failure) => throw failure,
  };
}
