import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/error/failure.dart';
import '../../../../core/network/result.dart';
import '../../../../core/providers/repository_providers.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_theme.dart';
import '../../data/models/auth_models.dart';

/// Create an account.
///
/// Registration does **not** sign you in: the API answers 202 with the same
/// message whether or not the address was already registered, because saying
/// otherwise would make it a membership oracle for a leaked email list. So this
/// screen ends on "check your inbox" rather than in the app.
class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  static const _minPassword = 12;

  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();

  bool _accepted = false;
  bool _busy = false;
  bool _sent = false;
  Failure? _error;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false) || !_accepted) return;

    setState(() {
      _busy = true;
      _error = null;
    });

    final result = await ref.read(authRepositoryProvider).register(
          email: _email.text.trim(),
          password: _password.text,
          fullName: _name.text.trim().isEmpty ? null : _name.text.trim(),
        );

    if (!mounted) return;
    setState(() {
      _busy = false;
      switch (result) {
        case Ok<MessageDto>():
          _sent = true;
        case Err<MessageDto>(:final failure):
          _error = failure;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    if (_sent) {
      return Scaffold(
        appBar: AppBar(),
        body: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.mark_email_read_outlined,
                  size: 56, color: theme.colorScheme.primary),
              Gap.md,
              Text('Check your inbox',
                  style: theme.textTheme.headlineSmall
                      ?.copyWith(fontWeight: FontWeight.w700)),
              Gap.sm,
              Text(
                'We have sent a link to ${_email.text.trim()}. Open it to '
                'finish setting up your account, then sign in.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium,
              ),
              Gap.sm,
              Text(
                'If that address already has an account, the email will say so '
                'instead — we do not reveal which addresses are registered.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
              Gap.lg,
              FilledButton(
                onPressed: () => context.go(Routes.login),
                child: const Text('Go to sign in'),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 32),
          children: [
            Text('Create your account',
                style: theme.textTheme.headlineMedium
                    ?.copyWith(fontWeight: FontWeight.w700)),
            Gap.xs,
            Text('One account for booking, trips and invoices.',
                style: theme.textTheme.bodyMedium
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            Gap.lg,

            if (_error != null) ...[
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: theme.colorScheme.errorContainer,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(_error!.message,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onErrorContainer,
                    )),
              ),
              Gap.md,
            ],

            TextFormField(
              controller: _name,
              textCapitalization: TextCapitalization.words,
              autofillHints: const [AutofillHints.name],
              decoration: const InputDecoration(labelText: 'Full name'),
            ),
            Gap.md,
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
              autofillHints: const [AutofillHints.newPassword],
              decoration: const InputDecoration(
                labelText: 'Password',
                // Stated up front rather than as a rejection after submitting:
                // a rule you learn by failing is a bad rule.
                helperText: 'At least $_minPassword characters. A phrase you '
                    'can remember beats a short jumble.',
                helperMaxLines: 2,
              ),
              validator: (value) => (value?.length ?? 0) < _minPassword
                  ? 'At least $_minPassword characters'
                  : null,
            ),
            Gap.md,
            CheckboxListTile(
              value: _accepted,
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              title: const Text(
                'I agree to the terms of service and privacy policy.',
              ),
              onChanged: (value) => setState(() => _accepted = value ?? false),
            ),
            Gap.md,
            FilledButton(
              onPressed: _busy || !_accepted ? null : _submit,
              child: _busy
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Create account'),
            ),
            Gap.md,
            Center(
              child: TextButton(
                onPressed: () => context.go(Routes.login),
                child: const Text('Already have an account? Sign in'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
