import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../../core/network/result.dart';
import '../../../../core/providers/repository_providers.dart';
import '../../data/models/property_models.dart';
import '../../domain/usecases/get_quote.dart';

part 'property_provider.g.dart';

/// One property.
///
/// `keepAlive` is deliberately off: a guest browses many properties in a
/// session and holding every one alive is a memory leak with a scroll view
/// attached. The repository's disk cache makes going back cheap anyway.
@riverpod
Future<PropertyDto> property(Ref ref, String identifier) async {
  final result = await ref.watch(catalogRepositoryProvider).property(identifier);
  return switch (result) {
    Ok<PropertyDto>(:final value) => value,
    Err<PropertyDto>(:final failure) => throw failure,
  };
}

/// What the guest currently has selected on a property screen.
class StaySelection {
  const StaySelection({
    this.roomTypeId = '',
    this.checkIn,
    this.checkOut,
    this.adults = 2,
    this.children = 0,
    this.rooms = 1,
  });

  final String roomTypeId;
  final String? checkIn;
  final String? checkOut;
  final int adults;
  final int children;
  final int rooms;

  StaySelection copyWith({
    String? roomTypeId,
    String? checkIn,
    String? checkOut,
    int? adults,
    int? children,
    int? rooms,
  }) =>
      StaySelection(
        roomTypeId: roomTypeId ?? this.roomTypeId,
        checkIn: checkIn ?? this.checkIn,
        checkOut: checkOut ?? this.checkOut,
        adults: adults ?? this.adults,
        children: children ?? this.children,
        rooms: rooms ?? this.rooms,
      );

  @override
  bool operator ==(Object other) =>
      other is StaySelection &&
      other.roomTypeId == roomTypeId &&
      other.checkIn == checkIn &&
      other.checkOut == checkOut &&
      other.adults == adults &&
      other.children == children &&
      other.rooms == rooms;

  @override
  int get hashCode =>
      Object.hash(roomTypeId, checkIn, checkOut, adults, children, rooms);
}

@riverpod
class StaySelectionController extends _$StaySelectionController {
  @override
  StaySelection build(String propertyId) => const StaySelection();

  void setRoom(String roomTypeId) =>
      state = state.copyWith(roomTypeId: roomTypeId);

  void setDates(String? checkIn, String? checkOut) => state = StaySelection(
        roomTypeId: state.roomTypeId,
        checkIn: checkIn,
        checkOut: checkOut,
        adults: state.adults,
        children: state.children,
        rooms: state.rooms,
      );

  void setGuests({int? adults, int? children, int? rooms}) => state =
      state.copyWith(adults: adults, children: children, rooms: rooms);
}

/// The live quote for the current selection.
///
/// Always the server's number. Nightly rates vary by date, weekends have
/// multipliers and tax is slabbed — computing it here would produce a total
/// that disagrees with the server at booking time, which the API correctly
/// rejects with a 409.
@riverpod
Future<QuoteDto?> stayQuote(Ref ref, String propertyId, int minNights) async {
  final selection = ref.watch(staySelectionControllerProvider(propertyId));
  if (selection.roomTypeId.isEmpty ||
      selection.checkIn == null ||
      selection.checkOut == null) {
    // Not an error — just nothing to price yet.
    return null;
  }

  final result = await ref.read(getQuoteProvider).call(
        QuoteRequest(
          propertyId: propertyId,
          roomTypeId: selection.roomTypeId,
          checkIn: selection.checkIn!,
          checkOut: selection.checkOut!,
          adults: selection.adults,
          children: selection.children,
          rooms: selection.rooms,
          minNights: minNights,
        ),
      );

  return switch (result) {
    Ok<QuoteDto>(:final value) => value,
    Err<QuoteDto>(:final failure) => throw failure,
  };
}
