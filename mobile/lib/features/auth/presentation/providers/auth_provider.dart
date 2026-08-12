import 'dart:async';

import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../../core/network/result.dart';
import '../../../../core/providers/app_providers.dart';
import '../../../../core/providers/repository_providers.dart';
import '../../../booking/presentation/providers/booking_providers.dart';
import '../../data/models/auth_models.dart';

part 'auth_provider.g.dart';

/// Who is signed in.
sealed class AuthState {
  const AuthState();
}

/// Launch, before the stored refresh token has been exchanged. The router must
/// wait here rather than treating it as signed-out — otherwise every cold start
/// flashes the sign-in screen at a signed-in user.
class AuthRestoring extends AuthState {
  const AuthRestoring();
}

class Authenticated extends AuthState {
  const Authenticated(this.user);
  final UserDto user;
}

class Unauthenticated extends AuthState {
  const Unauthenticated();
}

@Riverpod(keepAlive: true)
class Auth extends _$Auth {
  @override
  AuthState build() {
    // The interceptor raises this when a refresh finally fails. Watching it
    // here means a token that expires while the app is backgrounded surfaces as
    // a sign-out rather than as a screen full of 401s.
    ref.listen(sessionLostProvider, (_, lost) {
      if (lost) {
        state = const Unauthenticated();
        ref.read(sessionLostProvider.notifier).clear();
      }
    });

    unawaited(_restore());
    return const AuthRestoring();
  }

  Future<void> _restore() async {
    final user = await ref.read(authRepositoryProvider).restoreSession();
    state = user == null ? const Unauthenticated() : Authenticated(user);
  }

  Future<Result<AuthResponseDto>> signIn({
    required String email,
    required String password,
    required String deviceLabel,
  }) async {
    final result = await ref.read(authRepositoryProvider).login(
          email: email,
          password: password,
          deviceLabel: deviceLabel,
        );
    if (result case Ok<AuthResponseDto>(:final value)) {
      state = Authenticated(value.user);
    }
    return result;
  }

  Future<Result<AuthResponseDto>> verifyOtp({
    required String challengeId,
    required String code,
  }) async {
    final result = await ref
        .read(authRepositoryProvider)
        .verifyOtp(challengeId: challengeId, code: code);
    if (result case Ok<AuthResponseDto>(:final value)) {
      state = Authenticated(value.user);
    }
    return result;
  }

  Future<void> signOut({bool allDevices = false}) async {
    await ref.read(authRepositoryProvider).logout(allDevices: allDevices);
    state = const Unauthenticated();
    // Everything cached for the previous person — trips, saved stays — is gone
    // with the session. On a shared phone that is not optional.
    ref.invalidate(bookingsListProvider);
  }

  Future<void> refreshUser() async {
    final result = await ref.read(authRepositoryProvider).me();
    if (result case Ok<UserDto>(:final value)) state = Authenticated(value);
  }
}

/// The signed-in user, or null. Most screens want this rather than the state.
@riverpod
UserDto? currentUser(Ref ref) => switch (ref.watch(authProvider)) {
      Authenticated(:final user) => user,
      _ => null,
    };

@riverpod
bool isSignedIn(Ref ref) => ref.watch(authProvider) is Authenticated;
