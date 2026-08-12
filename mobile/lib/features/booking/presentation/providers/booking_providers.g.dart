// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'booking_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// The guest's trips, paginated.

@ProviderFor(BookingsList)
final bookingsListProvider = BookingsListProvider._();

/// The guest's trips, paginated.
final class BookingsListProvider
    extends $NotifierProvider<BookingsList, PagedState<BookingDto>> {
  /// The guest's trips, paginated.
  BookingsListProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'bookingsListProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$bookingsListHash();

  @$internal
  @override
  BookingsList create() => BookingsList();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(PagedState<BookingDto> value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<PagedState<BookingDto>>(value),
    );
  }
}

String _$bookingsListHash() => r'402a4931cb238466f985679ea1063885ae1ce334';

/// The guest's trips, paginated.

abstract class _$BookingsList extends $Notifier<PagedState<BookingDto>> {
  PagedState<BookingDto> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref =
        this.ref as $Ref<PagedState<BookingDto>, PagedState<BookingDto>>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<PagedState<BookingDto>, PagedState<BookingDto>>,
              PagedState<BookingDto>,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
  }
}

/// Trips split the way they are actually used: "where am I going and can I
/// still change it" versus "find me that invoice". One reverse-chronological
/// list serves neither.

@ProviderFor(upcomingTrips)
final upcomingTripsProvider = UpcomingTripsProvider._();

/// Trips split the way they are actually used: "where am I going and can I
/// still change it" versus "find me that invoice". One reverse-chronological
/// list serves neither.

final class UpcomingTripsProvider
    extends
        $FunctionalProvider<
          List<BookingDto>,
          List<BookingDto>,
          List<BookingDto>
        >
    with $Provider<List<BookingDto>> {
  /// Trips split the way they are actually used: "where am I going and can I
  /// still change it" versus "find me that invoice". One reverse-chronological
  /// list serves neither.
  UpcomingTripsProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'upcomingTripsProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$upcomingTripsHash();

  @$internal
  @override
  $ProviderElement<List<BookingDto>> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  List<BookingDto> create(Ref ref) {
    return upcomingTrips(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(List<BookingDto> value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<List<BookingDto>>(value),
    );
  }
}

String _$upcomingTripsHash() => r'56c26423903c55f0c19c3f6cd33316c8b08c066f';

@ProviderFor(pastTrips)
final pastTripsProvider = PastTripsProvider._();

final class PastTripsProvider
    extends
        $FunctionalProvider<
          List<BookingDto>,
          List<BookingDto>,
          List<BookingDto>
        >
    with $Provider<List<BookingDto>> {
  PastTripsProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'pastTripsProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$pastTripsHash();

  @$internal
  @override
  $ProviderElement<List<BookingDto>> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  List<BookingDto> create(Ref ref) {
    return pastTrips(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(List<BookingDto> value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<List<BookingDto>>(value),
    );
  }
}

String _$pastTripsHash() => r'cd984a66ee583a914294ac693e3e5b8ace0cf051';

/// One booking.
///
/// Polls while payment is settling: the webhook confirms a booking server-side
/// moments after the gateway callback, and a guest staring at "payment pending"
/// with no way to know it has cleared will pay again. Polling stops the moment
/// the status settles — a confirmed booking never changes on its own.

@ProviderFor(BookingDetail)
final bookingDetailProvider = BookingDetailFamily._();

/// One booking.
///
/// Polls while payment is settling: the webhook confirms a booking server-side
/// moments after the gateway callback, and a guest staring at "payment pending"
/// with no way to know it has cleared will pay again. Polling stops the moment
/// the status settles — a confirmed booking never changes on its own.
final class BookingDetailProvider
    extends $AsyncNotifierProvider<BookingDetail, BookingDto> {
  /// One booking.
  ///
  /// Polls while payment is settling: the webhook confirms a booking server-side
  /// moments after the gateway callback, and a guest staring at "payment pending"
  /// with no way to know it has cleared will pay again. Polling stops the moment
  /// the status settles — a confirmed booking never changes on its own.
  BookingDetailProvider._({
    required BookingDetailFamily super.from,
    required String super.argument,
  }) : super(
         retry: null,
         name: r'bookingDetailProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$bookingDetailHash();

  @override
  String toString() {
    return r'bookingDetailProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  BookingDetail create() => BookingDetail();

  @override
  bool operator ==(Object other) {
    return other is BookingDetailProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$bookingDetailHash() => r'ea1aebe6164d07d2462049413fa98898529e4885';

/// One booking.
///
/// Polls while payment is settling: the webhook confirms a booking server-side
/// moments after the gateway callback, and a guest staring at "payment pending"
/// with no way to know it has cleared will pay again. Polling stops the moment
/// the status settles — a confirmed booking never changes on its own.

final class BookingDetailFamily extends $Family
    with
        $ClassFamilyOverride<
          BookingDetail,
          AsyncValue<BookingDto>,
          BookingDto,
          FutureOr<BookingDto>,
          String
        > {
  BookingDetailFamily._()
    : super(
        retry: null,
        name: r'bookingDetailProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// One booking.
  ///
  /// Polls while payment is settling: the webhook confirms a booking server-side
  /// moments after the gateway callback, and a guest staring at "payment pending"
  /// with no way to know it has cleared will pay again. Polling stops the moment
  /// the status settles — a confirmed booking never changes on its own.

  BookingDetailProvider call(String bookingId) =>
      BookingDetailProvider._(argument: bookingId, from: this);

  @override
  String toString() => r'bookingDetailProvider';
}

/// One booking.
///
/// Polls while payment is settling: the webhook confirms a booking server-side
/// moments after the gateway callback, and a guest staring at "payment pending"
/// with no way to know it has cleared will pay again. Polling stops the moment
/// the status settles — a confirmed booking never changes on its own.

abstract class _$BookingDetail extends $AsyncNotifier<BookingDto> {
  late final _$args = ref.$arg as String;
  String get bookingId => _$args;

  FutureOr<BookingDto> build(String bookingId);
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AsyncValue<BookingDto>, BookingDto>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<AsyncValue<BookingDto>, BookingDto>,
              AsyncValue<BookingDto>,
              Object?,
              Object?
            >;
    element.handleCreate(ref, () => build(_$args));
  }
}

@ProviderFor(refundPreview)
final refundPreviewProvider = RefundPreviewFamily._();

final class RefundPreviewProvider
    extends
        $FunctionalProvider<
          AsyncValue<RefundPreviewDto>,
          RefundPreviewDto,
          FutureOr<RefundPreviewDto>
        >
    with $FutureModifier<RefundPreviewDto>, $FutureProvider<RefundPreviewDto> {
  RefundPreviewProvider._({
    required RefundPreviewFamily super.from,
    required String super.argument,
  }) : super(
         retry: null,
         name: r'refundPreviewProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$refundPreviewHash();

  @override
  String toString() {
    return r'refundPreviewProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  $FutureProviderElement<RefundPreviewDto> $createElement(
    $ProviderPointer pointer,
  ) => $FutureProviderElement(pointer);

  @override
  FutureOr<RefundPreviewDto> create(Ref ref) {
    final argument = this.argument as String;
    return refundPreview(ref, argument);
  }

  @override
  bool operator ==(Object other) {
    return other is RefundPreviewProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$refundPreviewHash() => r'd02e775e70b6f2f42d2dec88fbb92e0ad73a6660';

final class RefundPreviewFamily extends $Family
    with $FunctionalFamilyOverride<FutureOr<RefundPreviewDto>, String> {
  RefundPreviewFamily._()
    : super(
        retry: null,
        name: r'refundPreviewProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  RefundPreviewProvider call(String bookingId) =>
      RefundPreviewProvider._(argument: bookingId, from: this);

  @override
  String toString() => r'refundPreviewProvider';
}
