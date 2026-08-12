import '../../../../core/error/failure.dart';

/// A quote request that is wrong before it is sent.
///
/// Expressed as [Failure] values rather than a separate error type, so a screen
/// has one error path instead of two: it renders `failure.message` whether the
/// problem came from the server or from here. These never reach the network —
/// asking the server a question we already know is malformed wastes a round
/// trip and answers with a validation error nobody wrote for a human.
abstract final class QuoteProblem {
  static const invalidDates = Failure.api(
    status: 422,
    code: 'INVALID_DATES',
    message: 'Choose a check-out date after your check-in date.',
  );

  static const belowMinimumStay = Failure.api(
    status: 422,
    code: 'BELOW_MINIMUM_STAY',
    message: 'This room has a minimum stay. Try a longer trip or another room.',
  );
}
