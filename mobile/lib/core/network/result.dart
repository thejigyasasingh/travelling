import 'package:freezed_annotation/freezed_annotation.dart';

import '../error/failure.dart';

part 'result.freezed.dart';

/// Success or failure, without exceptions crossing layer boundaries.
///
/// Repositories return this rather than throwing. The reason is not purity: an
/// exception that escapes a repository is invisible in the signature, so the
/// caller has no way to know it must be handled, and it surfaces as a red
/// screen in front of a user. A `Result` in the return type cannot be ignored.
@freezed
sealed class Result<T> with _$Result<T> {
  const factory Result.ok(T value) = Ok<T>;
  const factory Result.err(Failure failure) = Err<T>;
}

extension ResultX<T> on Result<T> {
  bool get isOk => this is Ok<T>;

  T? get valueOrNull => switch (this) {
        Ok<T>(:final value) => value,
        Err<T>() => null,
      };

  Failure? get failureOrNull => switch (this) {
        Ok<T>() => null,
        Err<T>(:final failure) => failure,
      };

  /// Map the success value, carrying any failure through untouched.
  ///
  /// Named `mapOk` rather than `map` because freezed generates its own
  /// pattern-matching `map` on this type, and two extension members with the
  /// same name on the same type make **both** unreachable — `result.map(...)`
  /// is a compile error, not a silent pick. The name is the fix.
  Result<R> mapOk<R>(R Function(T value) transform) => switch (this) {
        Ok<T>(:final value) => Result.ok(transform(value)),
        Err<T>(:final failure) => Result.err(failure),
      };

  R fold<R>(R Function(T value) onOk, R Function(Failure failure) onErr) =>
      switch (this) {
        Ok<T>(:final value) => onOk(value),
        Err<T>(:final failure) => onErr(failure),
      };
}

/// Run a network call and convert whatever it throws into a [Failure].
///
/// Every data source body goes through this, so error mapping exists once
/// rather than in fifty `try`/`catch` blocks that each get it slightly
/// differently.
Future<Result<T>> guard<T>(Future<T> Function() call) async {
  try {
    return Result.ok(await call());
  } catch (error, stackTrace) {
    return Result.err(_toFailure(error, stackTrace));
  }
}

Failure _toFailure(Object error, StackTrace stackTrace) {
  if (error is Failure) return error;
  // Imported lazily to keep this file free of a Dio dependency at the type
  // level; the mapper lives with the client that produces the errors.
  return mapDioErrorRef(error, stackTrace);
}

/// Indirection so `result.dart` does not import Dio directly — assigned once at
/// startup. Keeps the Result type usable in tests that never touch HTTP.
Failure Function(Object error, StackTrace? stackTrace) mapDioErrorRef =
    (error, stackTrace) =>
        Failure.unexpected(error: error, stackTrace: stackTrace);
