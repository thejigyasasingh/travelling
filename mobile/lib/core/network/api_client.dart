import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../config/app_config.dart';
import '../error/failure.dart';
import '../storage/token_store.dart';
import 'auth_interceptor.dart';

/// The HTTP client.
///
/// One Dio for the app, plus a second bare one used only to refresh tokens and
/// to replay a retried request — see [AuthInterceptor] for why that separation
/// is not optional.
class ApiClient {
  ApiClient({
    required AppConfig config,
    required TokenStorage tokenStore,
    required Future<void> Function() onSessionLost,
    Dio? dio,
    Dio? refreshDio,
  }) : _config = config {
    final base = BaseOptions(
      baseUrl: config.apiBaseUrl,
      connectTimeout: config.connectTimeout,
      receiveTimeout: config.receiveTimeout,
      // The app decides what a status means, not Dio: every non-2xx is handed
      // to the error mapper so a 409 arrives as a typed ApiFailure rather than
      // as an exception someone forgot to catch.
      validateStatus: (status) => status != null && status < 400,
      headers: const {'Accept': 'application/json'},
      contentType: Headers.jsonContentType,
    );

    _refreshDio = refreshDio ?? Dio(base);
    dioInstance = dio ?? Dio(base);

    dioInstance.interceptors.add(
      AuthInterceptor(
        tokenStore: tokenStore,
        refreshClient: _refreshDio,
        onSessionLost: onSessionLost,
      ),
    );

    if (!config.isProduction) {
      dioInstance.interceptors.add(_LoggingInterceptor());
    }
  }

  final AppConfig _config;
  late final Dio dioInstance;
  late final Dio _refreshDio;

  Dio get dio => dioInstance;
  AppConfig get config => _config;
}

/// Logs requests in debug builds only.
///
/// Authorization headers and request bodies are **never** logged: a login body
/// holds a password and a token is a bearer credential, and both end up in
/// device logs that crash reporters upload.
class _LoggingInterceptor extends Interceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    debugPrint('→ ${options.method} ${options.uri}');
    handler.next(options);
  }

  @override
  void onResponse(Response<dynamic> response, ResponseInterceptorHandler handler) {
    debugPrint('← ${response.statusCode} ${response.requestOptions.uri}');
    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    // debugPrint rather than developer.log: log() is stripped from release and
    // profile builds, which is precisely where a network problem that never
    // appears in development has to be diagnosed.
    debugPrint(
      '✗ ${err.response?.statusCode ?? err.type.name} '
      '${err.requestOptions.uri} — ${err.message}',
    );
    handler.next(err);
  }
}

/// Turns anything Dio throws into a typed [Failure].
///
/// Callers never see a `DioException`, never re-check a status code, and cannot
/// forget to. The mapping is a pure function so it is testable without a
/// network.
Failure mapDioError(Object error, [StackTrace? stackTrace]) {
  if (error is! DioException) {
    return Failure.unexpected(error: error, stackTrace: stackTrace);
  }

  switch (error.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.receiveTimeout:
    case DioExceptionType.transformTimeout:
    case DioExceptionType.connectionError:
      return const Failure.network();
    case DioExceptionType.cancel:
      // A cancelled request is a screen that went away, not a fault.
      return const Failure.network(detail: 'cancelled');
    case DioExceptionType.badCertificate:
      return const Failure.network(detail: 'certificate');
    case DioExceptionType.badResponse:
    case DioExceptionType.unknown:
      break;
  }

  final response = error.response;
  final status = response?.statusCode ?? 0;
  if (status == 0) {
    return Failure.unexpected(error: error, stackTrace: stackTrace);
  }

  final requestId = response?.headers.value('x-request-id');

  if (status == 401) return const Failure.unauthenticated();
  if (status >= 500) return Failure.server(status: status, requestId: requestId);

  // The envelope: {"error": {code, message, details, request_id}}.
  final body = response?.data;
  final envelope = body is Map<String, dynamic>
      ? body['error'] as Map<String, dynamic>?
      : null;

  return Failure.api(
    status: status,
    code: envelope?['code'] as String? ?? 'UNKNOWN',
    message: envelope?['message'] as String? ??
        'The request could not be completed.',
    details: (envelope?['details'] as Map<String, dynamic>?) ?? const {},
    requestId: envelope?['request_id'] as String? ?? requestId,
  );
}
