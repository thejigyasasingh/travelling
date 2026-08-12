import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/error/failure.dart';
import '../../../../core/network/result.dart';
import '../../../../core/providers/repository_providers.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_theme.dart';
import '../../data/models/auth_models.dart';
import '../providers/auth_provider.dart';

/// Sign in, by password or phone OTP.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key, this.redirectTo});

  /// Where to go after signing in. Already validated as an in-app path by the
  /// router — an open redirect is a phishing primitive even on mobile.
  final String? redirectTo;

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _phone = TextEditingController();
  final _code = TextEditingController();

  bool _otpMode = false;
  String? _challengeId;
  bool _busy = false;
  Failure? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _phone.dispose();
    _code.dispose();
    super.dispose();
  }

  void _done() {
    if (!mounted) return;
    context.go(widget.redirectTo ?? Routes.home);
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    await action();
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _signIn() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    await _run(() async {
      final result = await ref.read(authProvider.notifier).signIn(
            email: _email.text.trim(),
            password: _password.text,
            deviceLabel: _deviceLabel(context),
          );
      switch (result) {
        case Ok<AuthResponseDto>():
          _done();
        case Err<AuthResponseDto>(:final failure):
          if (mounted) setState(() => _error = failure);
      }
    });
  }

  Future<void> _requestOtp() async {
    await _run(() async {
      final result =
          await ref.read(authRepositoryProvider).requestOtp(_phone.text.trim());
      switch (result) {
        case Ok<OtpChallengeDto>(:final value):
          if (mounted) setState(() => _challengeId = value.challengeId);
        case Err<OtpChallengeDto>(:final failure):
          if (mounted) setState(() => _error = failure);
      }
    });
  }

  Future<void> _verifyOtp() async {
    await _run(() async {
      final result = await ref.read(authProvider.notifier).verifyOtp(
            challengeId: _challengeId!,
            code: _code.text.trim(),
          );
      switch (result) {
        case Ok<AuthResponseDto>():
          _done();
        case Err<AuthResponseDto>(:final failure):
          if (mounted) setState(() => _error = failure);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.close_rounded),
          onPressed: () => context.go(Routes.home),
        ),
      ),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(24, 8, 24, 32),
            children: [
              Text('Welcome back',
                  style: theme.textTheme.headlineMedium
                      ?.copyWith(fontWeight: FontWeight.w700)),
              Gap.xs,
              Text('Sign in to manage your trips and bookings.',
                  style: theme.textTheme.bodyMedium
                      ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
              Gap.lg,

              SegmentedButton<bool>(
                segments: const [
                  ButtonSegment(value: false, label: Text('Email')),
                  ButtonSegment(value: true, label: Text('Phone OTP')),
                ],
                selected: {_otpMode},
                onSelectionChanged: (selection) => setState(() {
                  _otpMode = selection.first;
                  _error = null;
                  _challengeId = null;
                }),
              ),
              Gap.lg,

              if (_error != null) ...[
                _ErrorBanner(
                  failure: _error!,
                  locked: _error!.hasCode(ApiErrorCode.accountLocked),
                ),
                Gap.md,
              ],

              if (!_otpMode) ...[
                TextFormField(
                  controller: _email,
                  keyboardType: TextInputType.emailAddress,
                  autofillHints: const [AutofillHints.email],
                  decoration: const InputDecoration(labelText: 'Email'),
                  validator: (value) =>
                      (value?.contains('@') ?? false) ? null : 'Enter your email',
                ),
                Gap.md,
                TextFormField(
                  controller: _password,
                  obscureText: true,
                  autofillHints: const [AutofillHints.password],
                  decoration: const InputDecoration(labelText: 'Password'),
                  onFieldSubmitted: (_) => _signIn(),
                  validator: (value) =>
                      (value?.isEmpty ?? true) ? 'Enter your password' : null,
                ),
                Gap.lg,
                FilledButton(
                  onPressed: _busy ? null : _signIn,
                  child: _busy
                      ? const _ButtonSpinner()
                      : const Text('Sign in'),
                ),
              ] else if (_challengeId == null) ...[
                TextFormField(
                  controller: _phone,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(
                    labelText: 'Phone number',
                    hintText: '+91 98765 43210',
                    helperText: 'We will text you a six-digit code.',
                  ),
                ),
                Gap.lg,
                FilledButton(
                  onPressed: _busy ? null : _requestOtp,
                  child: _busy ? const _ButtonSpinner() : const Text('Send code'),
                ),
              ] else ...[
                TextFormField(
                  controller: _code,
                  keyboardType: TextInputType.number,
                  maxLength: 6,
                  autofillHints: const [AutofillHints.oneTimeCode],
                  decoration: InputDecoration(
                    labelText: 'Six-digit code',
                    helperText: 'Sent to ${_phone.text}',
                  ),
                ),
                Gap.md,
                FilledButton(
                  onPressed: _busy ? null : _verifyOtp,
                  child: _busy
                      ? const _ButtonSpinner()
                      : const Text('Verify and sign in'),
                ),
                TextButton(
                  onPressed: () => setState(() => _challengeId = null),
                  child: const Text('Use a different number'),
                ),
              ],

              Gap.lg,
              Center(
                child: TextButton(
                  onPressed: () => context.push(Routes.register),
                  child: const Text('New here? Create an account'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Shown in the session list so a guest can recognise "which device is this?"
/// and revoke the one they do not know.
String _deviceLabel(BuildContext context) {
  final platform = Theme.of(context).platform;
  return switch (platform) {
    TargetPlatform.iOS => 'iPhone',
    TargetPlatform.android => 'Android phone',
    TargetPlatform.macOS => 'Mac',
    TargetPlatform.windows => 'Windows PC',
    TargetPlatform.linux => 'Linux',
    TargetPlatform.fuchsia => 'Device',
  };
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.failure, this.locked = false});

  final Failure failure;
  final bool locked;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: theme.colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        locked
            ? 'Too many attempts. This account is locked for a short while — '
                'try again shortly, or reset your password.'
            : failure.message,
        style: theme.textTheme.bodySmall
            ?.copyWith(color: theme.colorScheme.onErrorContainer),
      ),
    );
  }
}

class _ButtonSpinner extends StatelessWidget {
  const _ButtonSpinner();

  @override
  Widget build(BuildContext context) => const SizedBox(
        width: 18,
        height: 18,
        child: CircularProgressIndicator(strokeWidth: 2),
      );
}
