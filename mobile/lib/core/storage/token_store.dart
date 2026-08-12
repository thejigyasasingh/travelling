import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Where tokens live.
///
/// The refresh token is long-lived and, on mobile, there is no HttpOnly cookie
/// to hide it in — so it goes in the **Keychain / EncryptedSharedPreferences**,
/// not in `SharedPreferences`. On a rooted or jailbroken device that is not
/// absolute protection, but on an ordinary one it means another app, a backup,
/// and a filesystem dump all come up empty.
///
/// The access token is cached in memory as well as on disk: it is read on
/// every single request, and a Keychain round trip per request is both slow and
/// pointless when the process already holds it.
/// What the request pipeline needs from token storage.
///
/// An interface rather than the concrete class, for one practical reason: the
/// real store talks to the Keychain through a platform channel, which does not
/// exist in a unit test. Without this seam the refresh logic — the most
/// delicate code in the app — could only be tested on a device.
abstract interface class TokenStorage {
  String? get accessToken;
  bool get isAccessTokenExpiring;
  Future<void> load();
  Future<String?> readRefreshToken();
  Future<void> save({
    required String accessToken,
    required String refreshToken,
    required int expiresInSeconds,
  });
  Future<void> clear();
}

class TokenStore implements TokenStorage {
  TokenStore({FlutterSecureStorage? storage})
      : _storage = storage ??
            const FlutterSecureStorage(
              // v11 encrypts on Android by default (AES-GCM behind a Keystore
              // key); `resetOnError` drops the store rather than throwing when
              // a key becomes unreadable, which happens after some OS upgrades
              // and would otherwise brick sign-in with no way back.
              aOptions: AndroidOptions(resetOnError: true),
              iOptions: IOSOptions(
                // Not `first_unlock`: `_this_device` keeps the tokens off
                // iCloud backups, so restoring a backup onto a new phone does
                // not carry a live session with it. And not `unlocked`, which
                // would break a background refresh on a locked device.
                accessibility: KeychainAccessibility.first_unlock_this_device,
              ),
            );

  final FlutterSecureStorage _storage;

  static const _accessKey = 'rw.access_token';
  static const _refreshKey = 'rw.refresh_token';
  static const _expiryKey = 'rw.access_expires_at';

  String? _accessToken;
  DateTime? _expiresAt;

  @override
  String? get accessToken => _accessToken;

  /// True shortly *before* real expiry, so a refresh starts before a 401 rather
  /// than after one. Thirty seconds covers a slow request in flight.
  @override
  bool get isAccessTokenExpiring {
    final expiry = _expiresAt;
    if (_accessToken == null || expiry == null) return _accessToken != null;
    return DateTime.now().add(const Duration(seconds: 30)).isAfter(expiry);
  }

  @override
  Future<void> load() async {
    _accessToken = await _storage.read(key: _accessKey);
    final raw = await _storage.read(key: _expiryKey);
    _expiresAt = raw == null ? null : DateTime.tryParse(raw);
  }

  @override
  Future<String?> readRefreshToken() => _storage.read(key: _refreshKey);

  @override
  Future<void> save({
    required String accessToken,
    required String refreshToken,
    required int expiresInSeconds,
  }) async {
    _accessToken = accessToken;
    _expiresAt = DateTime.now().add(Duration(seconds: expiresInSeconds));
    await Future.wait([
      _storage.write(key: _accessKey, value: accessToken),
      _storage.write(key: _refreshKey, value: refreshToken),
      _storage.write(key: _expiryKey, value: _expiresAt!.toIso8601String()),
    ]);
  }

  @override
  Future<void> clear() async {
    _accessToken = null;
    _expiresAt = null;
    await Future.wait([
      _storage.delete(key: _accessKey),
      _storage.delete(key: _refreshKey),
      _storage.delete(key: _expiryKey),
    ]);
  }
}
