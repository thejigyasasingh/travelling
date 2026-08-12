import 'package:dio/dio.dart';

import '../../../../core/network/result.dart';
import '../../../../core/storage/cache_store.dart';
import '../../../../core/storage/token_store.dart';
import '../models/auth_models.dart';

/// Authentication.
///
/// Every call that mints tokens hands them to [TokenStore] before returning, so
/// a caller cannot forget to persist a session it just created.
class AuthRepository {
  const AuthRepository({
    required Dio dio,
    required TokenStore tokens,
    required CacheStore cache,
  })  : _dio = dio,
        _tokens = tokens,
        _cache = cache;

  final Dio _dio;
  final TokenStore _tokens;
  final CacheStore _cache;

  Future<AuthResponseDto> _adopt(Map<String, dynamic> json) async {
    final auth = AuthResponseDto.fromJson(json);
    await _tokens.save(
      accessToken: auth.tokens.accessToken,
      refreshToken: auth.tokens.refreshToken,
      expiresInSeconds: auth.tokens.expiresIn,
    );
    await _cache.write(CacheKeys.currentUser, auth.user.toJson());
    return auth;
  }

  Future<Result<AuthResponseDto>> login({
    required String email,
    required String password,
    required String deviceLabel,
  }) =>
      guard(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          '/auth/login',
          data: {
            'email': email,
            'password': password,
            'device_label': deviceLabel,
          },
        );
        return _adopt(response.data!);
      });

  /// Registration returns 202 and a message — **no tokens**. The response says
  /// nothing about whether the address was already registered, deliberately:
  /// otherwise the endpoint is a membership oracle for a leaked email list.
  Future<Result<MessageDto>> register({
    required String email,
    required String password,
    String? fullName,
  }) =>
      guard(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          '/auth/register',
          data: {
            'email': email,
            'password': password,
            'full_name': fullName,
          },
        );
        return MessageDto.fromJson(response.data!);
      });

  Future<Result<OtpChallengeDto>> requestOtp(String phone) => guard(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          '/auth/otp/request',
          data: {'phone': phone, 'purpose': 'login'},
        );
        return OtpChallengeDto.fromJson(response.data!);
      });

  Future<Result<AuthResponseDto>> verifyOtp({
    required String challengeId,
    required String code,
  }) =>
      guard(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          '/auth/otp/verify',
          data: {'challenge_id': challengeId, 'code': code},
        );
        return _adopt(response.data!);
      });

  Future<Result<UserDto>> me() => guard(() async {
        final response = await _dio.get<Map<String, dynamic>>('/auth/me');
        final user = UserDto.fromJson(response.data!);
        await _cache.write(CacheKeys.currentUser, user.toJson());
        return user;
      });

  /// Restore a session at launch using the stored refresh token.
  ///
  /// Returns null for someone who is simply not signed in — overwhelmingly the
  /// common case on a first launch, and not an error worth surfacing.
  Future<UserDto?> restoreSession() async {
    final refreshToken = await _tokens.readRefreshToken();
    if (refreshToken == null) return null;

    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/refresh',
        data: {'refresh_token': refreshToken},
      );
      // The endpoint returns the user alongside the tokens, so restoring is one
      // round trip rather than a refresh followed by `/auth/me`.
      return (await _adopt(response.data!)).user;
    } on DioException catch (error) {
      // Offline at launch: keep the session and fall back to the cached user
      // rather than signing someone out because they opened the app on a
      // train. A genuinely revoked token produces 401 and is handled below.
      if (error.response == null) {
        final cached = _cache.read(CacheKeys.currentUser, UserDto.fromJson);
        if (cached != null) return cached.value;
      }
      await _tokens.clear();
      return null;
    }
  }

  Future<Result<void>> logout({bool allDevices = false}) => guard(() async {
        final refreshToken = await _tokens.readRefreshToken();
        try {
          await _dio.post<void>(
            '/auth/logout',
            data: {'refresh_token': refreshToken, 'all_devices': allDevices},
          );
        } finally {
          // Cleared even if the call fails. A network error must not leave
          // someone who pressed "sign out" still signed in on the screen in
          // front of them — and on a shared phone, cached trips must go too.
          await _tokens.clear();
          await _cache.clear();
        }
      });

  Future<Result<void>> forgotPassword(String email) => guard(() async {
        // Always accepted, whether or not the address exists.
        await _dio.post<void>('/auth/password/forgot', data: {'email': email});
      });

  Future<Result<void>> changePassword({
    required String currentPassword,
    required String newPassword,
  }) =>
      guard(() async {
        await _dio.post<void>(
          '/auth/password/change',
          data: {
            'current_password': currentPassword,
            'new_password': newPassword,
          },
        );
      });

  Future<Result<void>> resendVerification() =>
      guard(() async => _dio.post<void>('/auth/email/resend'));

  Future<Result<List<SessionDto>>> sessions() => guard(() async {
        final response = await _dio.get<List<dynamic>>('/auth/sessions');
        return (response.data ?? [])
            .map((item) => SessionDto.fromJson(item as Map<String, dynamic>))
            .toList(growable: false);
      });

  Future<Result<void>> revokeSession(String sessionId) =>
      guard(() async => _dio.delete<void>('/auth/sessions/$sessionId'));
}
