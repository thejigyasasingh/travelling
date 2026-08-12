import 'package:freezed_annotation/freezed_annotation.dart';

part 'failure.freezed.dart';

/// Everything that can go wrong, as a closed set.
///
/// A sealed union rather than a thrown `Exception` hierarchy, for one reason
/// that matters in a UI: the compiler forces every screen to decide what an
/// offline state looks like. `switch` over this is exhaustive, so adding a case
/// here produces a compile error in each place that renders one — which is
/// exactly where the decision belongs.
///
/// The distinction between [NetworkFailure] and [ServerFailure] is not
/// pedantry. "You are offline" invites the user to retry when they have signal;
/// "something went wrong on our side" tells them retrying now is pointless.
@freezed
sealed class Failure with _$Failure {
  /// The request never reached the server: no signal, DNS, timeout.
  const factory Failure.network({@Default('') String detail}) = NetworkFailure;

  /// The server answered with a business refusal — 4xx with an error code.
  /// [code] is the stable contract; [message] is human-facing and may change.
  const factory Failure.api({
    required int status,
    required String code,
    required String message,
    @Default(<String, dynamic>{}) Map<String, dynamic> details,
    String? requestId,
  }) = ApiFailure;

  /// 5xx. Not the user's fault and not something they can fix.
  const factory Failure.server({
    @Default(500) int status,
    String? requestId,
  }) = ServerFailure;

  /// The session is gone and could not be renewed. The UI signs out.
  const factory Failure.unauthenticated() = UnauthenticatedFailure;

  /// A local problem: cache corruption, a decode that does not match the
  /// model. Distinct from a server error because the fix is different — this
  /// one usually means clearing the cache, not retrying.
  const factory Failure.cache({@Default('') String detail}) = CacheFailure;

  /// Anything unforeseen. Carries the original for the log, never for the UI.
  const factory Failure.unexpected({Object? error, StackTrace? stackTrace}) =
      UnexpectedFailure;
}

extension FailureX on Failure {
  /// What to actually put in front of a person.
  ///
  /// Server messages are written for humans and are shown as-is; 5xx and
  /// unexpected errors are not, because their text either says nothing useful
  /// or leaks internals.
  String get message => switch (this) {
        NetworkFailure() =>
          'You appear to be offline. Check your connection and try again.',
        ApiFailure(:final message) => message,
        ServerFailure() => 'Something went wrong on our side. Please try again.',
        UnauthenticatedFailure() => 'Please sign in again to continue.',
        CacheFailure() => 'Could not read saved data. Pull to refresh.',
        UnexpectedFailure() => 'Something went wrong. Please try again.',
      };

  /// Whether a retry button makes sense. A 409 "those dates are gone" is not
  /// retryable — the state genuinely differs and retrying shows the same thing.
  bool get isRetryable => switch (this) {
        NetworkFailure() => true,
        ServerFailure() => true,
        ApiFailure(:final status) => status == 429,
        CacheFailure() => true,
        UnauthenticatedFailure() => false,
        UnexpectedFailure() => true,
      };

  bool get isOffline => this is NetworkFailure;

  /// Support quotes this; it turns "it broke" into one log lookup.
  String? get requestId => switch (this) {
        ApiFailure(:final requestId) => requestId,
        ServerFailure(:final requestId) => requestId,
        _ => null,
      };

  bool hasCode(String code) =>
      this is ApiFailure && (this as ApiFailure).code == code;
}

/// Error codes the app reacts to specifically, each because it has a distinct
/// recovery the user can actually perform. Anything else is shown as its
/// message.
abstract final class ApiErrorCode {
  static const validation = 'VALIDATION_ERROR';
  static const unauthenticated = 'UNAUTHENTICATED';
  static const tokenExpired = 'TOKEN_EXPIRED';
  static const forbidden = 'FORBIDDEN';
  static const notFound = 'NOT_FOUND';
  static const conflict = 'CONFLICT';
  static const rateLimited = 'RATE_LIMITED';
  static const datesUnavailable = 'BOOKING_DATES_UNAVAILABLE';
  static const priceChanged = 'PRICE_CHANGED';
  static const holdExpired = 'HOLD_EXPIRED';
  static const paymentsDisabled = 'PAYMENTS_DISABLED';
  static const gatewayError = 'PAYMENT_GATEWAY_ERROR';
  static const accountLocked = 'ACCOUNT_LOCKED';
}
