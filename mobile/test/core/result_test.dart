/// `Result`, `guard`, and the Dio error mapper.
///
/// This is the seam every repository call passes through, and the one place
/// that decides what a failure *is*. Getting it wrong is not a crash — it is
/// worse: an offline phone told "something went wrong on our side", so the
/// guest stops trying instead of walking to where there is signal.
///
/// The distinctions asserted here each drive a different screen:
///
/// * **network vs server** — one invites a retry, the other says retrying now
///   is pointless;
/// * **401 vs other 4xx** — one signs the user out, the other shows a message;
/// * **cancel** — a screen that went away, never an error in front of anyone.
library;

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:roaming_wandering/core/error/failure.dart';
import 'package:roaming_wandering/core/network/api_client.dart';
import 'package:roaming_wandering/core/network/result.dart';

RequestOptions get _options => RequestOptions(path: '/bookings');

DioException _badResponse(int status, {Object? body, Map<String, List<String>>? headers}) =>
    DioException.badResponse(
      statusCode: status,
      requestOptions: _options,
      response: Response<Object?>(
        requestOptions: _options,
        statusCode: status,
        data: body,
        headers: Headers.fromMap(headers ?? {}),
      ),
    );

void main() {
  group('Result', () {
    test('ok carries its value and no failure', () {
      const result = Result<int>.ok(7);

      expect(result.isOk, isTrue);
      expect(result.valueOrNull, 7);
      expect(result.failureOrNull, isNull);
    });

    test('err carries its failure and no value', () {
      const result = Result<int>.err(Failure.network());

      expect(result.isOk, isFalse);
      expect(result.valueOrNull, isNull);
      expect(result.failureOrNull, isA<NetworkFailure>());
    });

    test('mapOk transforms a value', () {
      expect(const Result<int>.ok(21).mapOk((v) => v * 2).valueOrNull, 42);
    });

    test('mapOk carries a failure through untouched', () {
      // The whole point of the type: a transform in the middle of a chain
      // cannot accidentally turn a failure into a success, or lose which
      // failure it was.
      const failure = Failure.api(status: 409, code: 'PRICE_CHANGED', message: 'up');
      final mapped = const Result<int>.err(failure).mapOk((v) => v * 2);

      expect(mapped.failureOrNull, failure);
    });

    test('mapOk is reachable at all', () {
      // Not a tautology. It was previously named `map`, which collides with
      // the `map` freezed generates on the same type — two extension members
      // with one name make both unreachable, so every call site was a compile
      // error and there simply were none. A rename fixed it; this pins it.
      expect(const Result<int>.ok(1).mapOk((v) => '$v'), const Result<String>.ok('1'));
    });

    test('fold runs exactly one branch', () {
      expect(const Result<int>.ok(1).fold((v) => 'ok', (f) => 'err'), 'ok');
      expect(
        const Result<int>.err(Failure.network()).fold((v) => 'ok', (f) => 'err'),
        'err',
      );
    });

    test('valueOrNull cannot distinguish a null value from a failure', () {
      // Documented rather than fixed. `Result<T?>` is not used anywhere, and
      // `fold` is the answer where it would matter. Written down so nobody
      // reaches for `valueOrNull` on a nullable T and trusts the result.
      expect(const Result<int?>.ok(null).valueOrNull, isNull);
      expect(const Result<int?>.ok(null).isOk, isTrue);
    });
  });

  group('guard', () {
    setUp(() => mapDioErrorRef = mapDioError);

    test('returns ok for a call that succeeds', () async {
      expect(expectValue(await guard(() async => 'fine')), 'fine');
    });

    test('converts a thrown DioException into a Failure', () async {
      final result = await guard<String>(
        () async => throw DioException.connectionError(
          requestOptions: _options,
          reason: 'down',
        ),
      );

      expect(result.failureOrNull, isA<NetworkFailure>());
    });

    test('passes a Failure through rather than wrapping it', () async {
      // Use cases throw their own domain failures — a below-minimum stay, for
      // instance. Wrapping those in `unexpected` would replace a sentence the
      // guest can act on with "something went wrong".
      const domain = Failure.api(status: 400, code: 'BELOW_MIN', message: 'Two nights minimum');
      final result = await guard<String>(() async => throw domain);

      expect(result.failureOrNull, domain);
    });

    test('does not let a non-Dio throw escape', () async {
      // A decode bug in a model is a `TypeError`, not a `DioException`. It must
      // still come back as a Result, or it surfaces as a red screen.
      final result = await guard<String>(() async => throw StateError('bad shape'));

      expect(result.failureOrNull, isA<UnexpectedFailure>());
    });
  });

  group('mapDioError', () {
    test('every flavour of not-reaching-the-server is a network failure', () {
      for (final type in [
        DioExceptionType.connectionTimeout,
        DioExceptionType.sendTimeout,
        DioExceptionType.receiveTimeout,
        DioExceptionType.connectionError,
      ]) {
        expect(
          mapDioError(DioException(requestOptions: _options, type: type)),
          isA<NetworkFailure>(),
          reason: '$type should read as offline',
        );
      }
    });

    test('a cancelled request is not an error anyone sees', () {
      // The screen was disposed. Rendering "you appear to be offline" over a
      // page the user already left is noise at best.
      final failure = mapDioError(DioException.requestCancelled(
        requestOptions: _options,
        reason: 'disposed',
      ));

      expect(failure, const Failure.network(detail: 'cancelled'));
    });

    test('401 is unauthenticated, not a generic 4xx', () {
      // The interceptor has already tried to refresh by the time this runs, so
      // a 401 reaching here means the session is genuinely gone: sign out.
      expect(mapDioError(_badResponse(401)), isA<UnauthenticatedFailure>());
    });

    test('5xx is a server failure and is not retryable-by-the-user', () {
      final failure = mapDioError(_badResponse(503));

      expect(failure, isA<ServerFailure>());
      expect(failure.message, contains('our side'));
    });

    test('a 4xx envelope keeps its code and message', () {
      final failure = mapDioError(_badResponse(409, body: {
        'error': {
          'code': 'BOOKING_DATES_UNAVAILABLE',
          'message': 'Those dates have just gone.',
          'request_id': 'req-99',
        },
      }));

      expect(failure.hasCode(ApiErrorCode.datesUnavailable), isTrue);
      expect(failure.message, 'Those dates have just gone.');
      expect(failure.requestId, 'req-99');
    });

    test('a 4xx with no envelope still produces something showable', () {
      // A proxy or a gateway can return a 4xx that never touched the app. The
      // guest still needs a sentence.
      final failure = mapDioError(_badResponse(413, body: '<html>Too large</html>'));

      expect(failure, isA<ApiFailure>());
      expect(failure.message, isNotEmpty);
      expect(failure.hasCode('UNKNOWN'), isTrue);
    });

    test('the request id falls back to the response header', () {
      // Support quotes this. When the body has no envelope the header is the
      // only way back to the log line.
      final failure = mapDioError(_badResponse(
        429,
        body: {'error': <String, dynamic>{'code': 'RATE_LIMITED', 'message': 'Slow down'}},
        headers: {'x-request-id': ['hdr-7']},
      ));

      expect(failure.requestId, 'hdr-7');
    });

    test('a rate limit is retryable but a sold-out stay is not', () {
      // **The** retry rule. Retrying a 429 eventually works; retrying "those
      // dates are gone" shows the same answer and wastes the guest's time.
      expect(
        mapDioError(_badResponse(429, body: {
          'error': {'code': 'RATE_LIMITED', 'message': 'Slow down'},
        })).isRetryable,
        isTrue,
      );
      expect(
        mapDioError(_badResponse(409, body: {
          'error': {'code': 'BOOKING_DATES_UNAVAILABLE', 'message': 'Gone'},
        })).isRetryable,
        isFalse,
      );
    });

    test('something that is not a DioException is unexpected, not a crash', () {
      expect(mapDioError(FormatException('nope')), isA<UnexpectedFailure>());
    });
  });
}

/// Local unwrap, so this file does not depend on the shared support library it
/// is partly testing.
T expectValue<T>(Result<T> result) {
  expect(result.isOk, isTrue, reason: 'expected Ok, got ${result.failureOrNull}');
  return result.valueOrNull as T;
}
