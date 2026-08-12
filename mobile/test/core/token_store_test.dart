/// Where tokens live, and when the app decides one is stale.
///
/// Two things are being pinned, and they fail in opposite directions:
///
/// * **What is written, and under which keys.** A rename here signs every
///   existing installation out on upgrade — silently, because the read simply
///   returns null and the app looks like a fresh install.
/// * **When [TokenStore.isAccessTokenExpiring] is true.** Too eager and the app
///   refreshes constantly, rotating tokens for no reason. Too lazy and every
///   session begins with a 401 the user waits through.
///
/// Runs against `flutter_secure_storage`'s own in-memory test platform rather
/// than a hand-rolled fake, so the real `TokenStore` — real keys, real
/// Keychain options — is what executes.
library;

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:roaming_wandering/core/storage/token_store.dart';

/// The keys as they exist on real devices. Spelled out literally, not imported
/// from the class under test: importing them would make a rename pass this
/// test while breaking every installed app.
const _accessKey = 'rw.access_token';
const _refreshKey = 'rw.refresh_token';
const _expiryKey = 'rw.access_expires_at';

void main() {
  late Map<String, String> disk;
  late TokenStore store;

  setUp(() {
    disk = {};
    FlutterSecureStorage.setMockInitialValues(disk);
    store = TokenStore();
  });

  test('starts with nothing', () async {
    await store.load();

    expect(store.accessToken, isNull);
    expect(await store.readRefreshToken(), isNull);
  });

  test('a store with no token is not "expiring"', () {
    // Signed out is not the same as stale. If this returned true the
    // interceptor would try to refresh on the very first anonymous request —
    // a search — and a guest who never signed in would get a spurious sign-out
    // prompt.
    expect(store.isAccessTokenExpiring, isFalse);
  });

  test('saves all three fields under their published keys', () async {
    await store.save(
      accessToken: 'acc',
      refreshToken: 'ref',
      expiresInSeconds: 900,
    );

    expect(disk[_accessKey], 'acc');
    expect(disk[_refreshKey], 'ref');
    expect(DateTime.parse(disk[_expiryKey]!).isAfter(DateTime.now()), isTrue);
  });

  test('keeps the access token in memory so a read is not a Keychain trip', () async {
    // Read on every single request. A platform-channel round trip per request
    // is measurable on a mid-range Android phone, and pointless when the
    // process already holds the value.
    await store.save(accessToken: 'acc', refreshToken: 'ref', expiresInSeconds: 900);

    expect(store.accessToken, 'acc');
  });

  test('the refresh token is never held in memory', () async {
    // Deliberate asymmetry. The refresh token is the long-lived credential; it
    // is read at most once per refresh, so there is no reason for it to sit in
    // a heap dump between them.
    await store.save(accessToken: 'acc', refreshToken: 'ref', expiresInSeconds: 900);

    expect(await store.readRefreshToken(), 'ref');
    // Nothing on the public surface exposes it synchronously.
    expect(store.accessToken, isNot('ref'));
  });

  test('load restores a session across a restart', () async {
    await store.save(accessToken: 'acc', refreshToken: 'ref', expiresInSeconds: 900);

    final afterRestart = TokenStore();
    await afterRestart.load();

    expect(afterRestart.accessToken, 'acc');
    expect(afterRestart.isAccessTokenExpiring, isFalse);
    expect(await afterRestart.readRefreshToken(), 'ref');
  });

  test('a freshly saved token is not expiring', () async {
    await store.save(accessToken: 'acc', refreshToken: 'ref', expiresInSeconds: 900);

    expect(store.isAccessTokenExpiring, isFalse);
  });

  test('a token expiring inside the skew window counts as expiring', () async {
    // **The** timing rule. The refresh starts *before* the 401, not after it,
    // so a request in flight when the token turns over still succeeds. Twenty
    // seconds is inside the thirty-second window.
    await store.save(accessToken: 'acc', refreshToken: 'ref', expiresInSeconds: 20);

    expect(store.isAccessTokenExpiring, isTrue);
  });

  test('a token just outside the skew window does not', () async {
    // The other side of the same boundary — without this, a change to the
    // window that made it enormous would still pass the test above.
    await store.save(accessToken: 'acc', refreshToken: 'ref', expiresInSeconds: 120);

    expect(store.isAccessTokenExpiring, isFalse);
  });

  test('an already-expired token is expiring', () async {
    await store.save(accessToken: 'acc', refreshToken: 'ref', expiresInSeconds: -60);

    expect(store.isAccessTokenExpiring, isTrue);
  });

  test('a token with an unreadable expiry is treated as expiring', () async {
    // Written by an older build, or corrupted. Assuming it is *valid* would
    // mean never refreshing it and every request 401ing; assuming it is stale
    // costs one extra refresh and recovers.
    disk[_accessKey] = 'acc';
    disk[_expiryKey] = 'not-a-date';

    final loaded = TokenStore();
    await loaded.load();

    expect(loaded.accessToken, 'acc');
    expect(loaded.isAccessTokenExpiring, isTrue);
  });

  test('clear removes every key, not just the access token', () async {
    // Sign-out. Leaving the refresh token behind would let the next person
    // holding the phone silently resume the previous account's session.
    await store.save(accessToken: 'acc', refreshToken: 'ref', expiresInSeconds: 900);

    await store.clear();

    expect(disk, isEmpty);
    expect(store.accessToken, isNull);
    expect(await store.readRefreshToken(), isNull);
    expect(store.isAccessTokenExpiring, isFalse);
  });

  test('clear survives a restart', () async {
    await store.save(accessToken: 'acc', refreshToken: 'ref', expiresInSeconds: 900);
    await store.clear();

    final afterRestart = TokenStore();
    await afterRestart.load();

    expect(afterRestart.accessToken, isNull);
  });

  test('saving again replaces rather than accumulates', () async {
    await store.save(accessToken: 'a1', refreshToken: 'r1', expiresInSeconds: 900);
    await store.save(accessToken: 'a2', refreshToken: 'r2', expiresInSeconds: 900);

    expect(store.accessToken, 'a2');
    expect(await store.readRefreshToken(), 'r2');
    expect(disk.length, 3);
  });
}
