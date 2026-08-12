import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:roaming_wandering/core/error/failure.dart';
import 'package:roaming_wandering/core/network/api_client.dart';

/// Mapping transport errors onto something a screen can render.
void main() {
  RequestOptions options() => RequestOptions(path: '/bookings');

  group('mapping', () {
    test('a timeout is a network failure, not a server one', () {
      // The distinction drives what the user is told: "you are offline" invites
      // a retry, "something went wrong on our side" says retrying is pointless.
      final failure = mapDioError(
        DioException(
          requestOptions: options(),
          type: DioExceptionType.connectionTimeout,
        ),
      );
      expect(failure, isA<NetworkFailure>());
      expect(failure.isOffline, isTrue);
      expect(failure.isRetryable, isTrue);
    });

    test('a 401 is unauthenticated, whatever the body says', () {
      final failure = mapDioError(
        DioException(
          requestOptions: options(),
          response: Response<dynamic>(
            requestOptions: options(),
            statusCode: 401,
          ),
        ),
      );
      expect(failure, isA<UnauthenticatedFailure>());
      // No retry button: signing in again is the only route forward.
      expect(failure.isRetryable, isFalse);
    });

    test('a 5xx never shows the server’s own words', () {
      final failure = mapDioError(
        DioException(
          requestOptions: options(),
          response: Response<dynamic>(
            requestOptions: options(),
            statusCode: 500,
            data: {
              'error': {'code': 'INTERNAL_ERROR', 'message': 'psycopg2 boom'},
            },
          ),
        ),
      );
      expect(failure, isA<ServerFailure>());
      expect(failure.message, isNot(contains('psycopg2')));
      expect(failure.isRetryable, isTrue);
    });

    test('a business refusal keeps its code and its message', () {
      final failure = mapDioError(
        DioException(
          requestOptions: options(),
          response: Response<dynamic>(
            requestOptions: options(),
            statusCode: 409,
            data: {
              'error': {
                'code': 'BOOKING_DATES_UNAVAILABLE',
                'message': 'Those dates are no longer available.',
                'request_id': 'abc123',
              },
            },
          ),
        ),
      );

      expect(failure.hasCode(ApiErrorCode.datesUnavailable), isTrue);
      // The message is written for a human and is shown as-is.
      expect(failure.message, 'Those dates are no longer available.');
      expect(failure.requestId, 'abc123');
      // A 409 is a real conflict; retrying shows the same thing.
      expect(failure.isRetryable, isFalse);
    });

    test('a rate limit is retryable even though it is a 4xx', () {
      final failure = mapDioError(
        DioException(
          requestOptions: options(),
          response: Response<dynamic>(
            requestOptions: options(),
            statusCode: 429,
            data: {
              'error': {'code': 'RATE_LIMITED', 'message': 'Slow down.'},
            },
          ),
        ),
      );
      expect(failure.isRetryable, isTrue);
    });

    test('a non-JSON error body still produces a usable failure', () {
      // A proxy 502 returns HTML. The status is the signal.
      final failure = mapDioError(
        DioException(
          requestOptions: options(),
          response: Response<dynamic>(
            requestOptions: options(),
            statusCode: 502,
            data: '<html>Bad Gateway</html>',
          ),
        ),
      );
      expect(failure, isA<ServerFailure>());
    });

    test('anything that is not a DioException is unexpected, not swallowed', () {
      final failure = mapDioError(StateError('bad state'));
      expect(failure, isA<UnexpectedFailure>());
    });
  });

  group('presentation', () {
    test('every case has a message a person can read', () {
      const failures = [
        Failure.network(),
        Failure.api(status: 409, code: 'X', message: 'Those dates are gone.'),
        Failure.server(),
        Failure.unauthenticated(),
        Failure.cache(),
        Failure.unexpected(),
      ];
      for (final failure in failures) {
        expect(failure.message, isNotEmpty);
        // No stack traces, no exception class names in front of a user.
        expect(failure.message, isNot(contains('Exception')));
      }
    });
  });
}
