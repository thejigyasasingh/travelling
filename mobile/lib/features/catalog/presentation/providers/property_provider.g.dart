// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'property_provider.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// One property.
///
/// `keepAlive` is deliberately off: a guest browses many properties in a
/// session and holding every one alive is a memory leak with a scroll view
/// attached. The repository's disk cache makes going back cheap anyway.

@ProviderFor(property)
final propertyProvider = PropertyFamily._();

/// One property.
///
/// `keepAlive` is deliberately off: a guest browses many properties in a
/// session and holding every one alive is a memory leak with a scroll view
/// attached. The repository's disk cache makes going back cheap anyway.

final class PropertyProvider
    extends
        $FunctionalProvider<
          AsyncValue<PropertyDto>,
          PropertyDto,
          FutureOr<PropertyDto>
        >
    with $FutureModifier<PropertyDto>, $FutureProvider<PropertyDto> {
  /// One property.
  ///
  /// `keepAlive` is deliberately off: a guest browses many properties in a
  /// session and holding every one alive is a memory leak with a scroll view
  /// attached. The repository's disk cache makes going back cheap anyway.
  PropertyProvider._({
    required PropertyFamily super.from,
    required String super.argument,
  }) : super(
         retry: null,
         name: r'propertyProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$propertyHash();

  @override
  String toString() {
    return r'propertyProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  $FutureProviderElement<PropertyDto> $createElement(
    $ProviderPointer pointer,
  ) => $FutureProviderElement(pointer);

  @override
  FutureOr<PropertyDto> create(Ref ref) {
    final argument = this.argument as String;
    return property(ref, argument);
  }

  @override
  bool operator ==(Object other) {
    return other is PropertyProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$propertyHash() => r'5ba85b04b7b910fd80b1dc2376388c6fb7856bdc';

/// One property.
///
/// `keepAlive` is deliberately off: a guest browses many properties in a
/// session and holding every one alive is a memory leak with a scroll view
/// attached. The repository's disk cache makes going back cheap anyway.

final class PropertyFamily extends $Family
    with $FunctionalFamilyOverride<FutureOr<PropertyDto>, String> {
  PropertyFamily._()
    : super(
        retry: null,
        name: r'propertyProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// One property.
  ///
  /// `keepAlive` is deliberately off: a guest browses many properties in a
  /// session and holding every one alive is a memory leak with a scroll view
  /// attached. The repository's disk cache makes going back cheap anyway.

  PropertyProvider call(String identifier) =>
      PropertyProvider._(argument: identifier, from: this);

  @override
  String toString() => r'propertyProvider';
}

@ProviderFor(StaySelectionController)
final staySelectionControllerProvider = StaySelectionControllerFamily._();

final class StaySelectionControllerProvider
    extends $NotifierProvider<StaySelectionController, StaySelection> {
  StaySelectionControllerProvider._({
    required StaySelectionControllerFamily super.from,
    required String super.argument,
  }) : super(
         retry: null,
         name: r'staySelectionControllerProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$staySelectionControllerHash();

  @override
  String toString() {
    return r'staySelectionControllerProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  StaySelectionController create() => StaySelectionController();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(StaySelection value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<StaySelection>(value),
    );
  }

  @override
  bool operator ==(Object other) {
    return other is StaySelectionControllerProvider &&
        other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$staySelectionControllerHash() =>
    r'3a46ca0bf0e904a2ec321d8c3b45214624e56fd0';

final class StaySelectionControllerFamily extends $Family
    with
        $ClassFamilyOverride<
          StaySelectionController,
          StaySelection,
          StaySelection,
          StaySelection,
          String
        > {
  StaySelectionControllerFamily._()
    : super(
        retry: null,
        name: r'staySelectionControllerProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  StaySelectionControllerProvider call(String propertyId) =>
      StaySelectionControllerProvider._(argument: propertyId, from: this);

  @override
  String toString() => r'staySelectionControllerProvider';
}

abstract class _$StaySelectionController extends $Notifier<StaySelection> {
  late final _$args = ref.$arg as String;
  String get propertyId => _$args;

  StaySelection build(String propertyId);
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<StaySelection, StaySelection>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<StaySelection, StaySelection>,
              StaySelection,
              Object?,
              Object?
            >;
    element.handleCreate(ref, () => build(_$args));
  }
}

/// The live quote for the current selection.
///
/// Always the server's number. Nightly rates vary by date, weekends have
/// multipliers and tax is slabbed — computing it here would produce a total
/// that disagrees with the server at booking time, which the API correctly
/// rejects with a 409.

@ProviderFor(stayQuote)
final stayQuoteProvider = StayQuoteFamily._();

/// The live quote for the current selection.
///
/// Always the server's number. Nightly rates vary by date, weekends have
/// multipliers and tax is slabbed — computing it here would produce a total
/// that disagrees with the server at booking time, which the API correctly
/// rejects with a 409.

final class StayQuoteProvider
    extends
        $FunctionalProvider<
          AsyncValue<QuoteDto?>,
          QuoteDto?,
          FutureOr<QuoteDto?>
        >
    with $FutureModifier<QuoteDto?>, $FutureProvider<QuoteDto?> {
  /// The live quote for the current selection.
  ///
  /// Always the server's number. Nightly rates vary by date, weekends have
  /// multipliers and tax is slabbed — computing it here would produce a total
  /// that disagrees with the server at booking time, which the API correctly
  /// rejects with a 409.
  StayQuoteProvider._({
    required StayQuoteFamily super.from,
    required (String, int) super.argument,
  }) : super(
         retry: null,
         name: r'stayQuoteProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$stayQuoteHash();

  @override
  String toString() {
    return r'stayQuoteProvider'
        ''
        '$argument';
  }

  @$internal
  @override
  $FutureProviderElement<QuoteDto?> $createElement($ProviderPointer pointer) =>
      $FutureProviderElement(pointer);

  @override
  FutureOr<QuoteDto?> create(Ref ref) {
    final argument = this.argument as (String, int);
    return stayQuote(ref, argument.$1, argument.$2);
  }

  @override
  bool operator ==(Object other) {
    return other is StayQuoteProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$stayQuoteHash() => r'093c3fe2f79e548c4ec0762d7b736ab7972381e4';

/// The live quote for the current selection.
///
/// Always the server's number. Nightly rates vary by date, weekends have
/// multipliers and tax is slabbed — computing it here would produce a total
/// that disagrees with the server at booking time, which the API correctly
/// rejects with a 409.

final class StayQuoteFamily extends $Family
    with $FunctionalFamilyOverride<FutureOr<QuoteDto?>, (String, int)> {
  StayQuoteFamily._()
    : super(
        retry: null,
        name: r'stayQuoteProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// The live quote for the current selection.
  ///
  /// Always the server's number. Nightly rates vary by date, weekends have
  /// multipliers and tax is slabbed — computing it here would produce a total
  /// that disagrees with the server at booking time, which the API correctly
  /// rejects with a 409.

  StayQuoteProvider call(String propertyId, int minNights) =>
      StayQuoteProvider._(argument: (propertyId, minNights), from: this);

  @override
  String toString() => r'stayQuoteProvider';
}
