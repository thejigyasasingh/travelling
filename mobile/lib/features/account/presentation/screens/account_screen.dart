import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/error/failure.dart';
import '../../../../core/network/result.dart';
import '../../../../core/providers/repository_providers.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/utils/dates.dart';
import '../../../../shared/widgets/state_views.dart';
import '../../../auth/data/models/auth_models.dart';
import '../../../auth/presentation/providers/auth_provider.dart';

/// Account: profile, sessions, sign out.
///
/// The **sessions list** is the part that matters. It is the only place a guest
/// can see that someone else is signed into their account and end it — which is
/// the whole reason sessions are tracked server-side. Each row shows a device
/// label and when it was last used, because "iPhone, 3 minutes ago" is what
/// makes an unfamiliar entry recognisable as unfamiliar.
class AccountScreen extends ConsumerWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Account')),
      body: switch (auth) {
        AuthRestoring() => const LoadingView(),
        Unauthenticated() => EmptyView(
            title: 'Sign in to see your account',
            description:
                'Your trips, invoices and saved details live behind sign-in.',
            icon: Icons.person_outline_rounded,
            action: FilledButton(
              onPressed: () => context.push(Routes.login),
              child: const Text('Sign in'),
            ),
          ),
        Authenticated(:final user) => ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
            children: [
              Row(
                children: [
                  CircleAvatar(
                    radius: 28,
                    backgroundColor: theme.colorScheme.primary,
                    child: Text(
                      _initials(user),
                      style: TextStyle(
                        color: theme.colorScheme.onPrimary,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  Gap.md,
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(user.fullName ?? user.email.split('@').first,
                            style: theme.textTheme.titleLarge
                                ?.copyWith(fontWeight: FontWeight.w700)),
                        Text(user.email,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            )),
                      ],
                    ),
                  ),
                ],
              ),
              Gap.lg,

              if (!user.emailVerified) _VerifyEmailNotice(email: user.email),

              _SectionCard(
                title: 'Contact details',
                children: [
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Email'),
                    subtitle: Text(user.email),
                    trailing: user.emailVerified
                        ? Icon(Icons.verified_rounded,
                            color: theme.colorScheme.success, size: 20)
                        : TextButton(
                            onPressed: () async {
                              await ref
                                  .read(authRepositoryProvider)
                                  .resendVerification();
                              if (context.mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('Verification email sent.'),
                                  ),
                                );
                              }
                            },
                            child: const Text('Resend'),
                          ),
                  ),
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Phone'),
                    subtitle: Text(user.phone ?? 'Not linked'),
                    trailing: user.phoneVerified
                        ? Icon(Icons.verified_rounded,
                            color: theme.colorScheme.success, size: 20)
                        : null,
                  ),
                ],
              ),

              Gap.md,
              const _SessionsCard(),

              Gap.lg,
              OutlinedButton.icon(
                icon: const Icon(Icons.logout_rounded, size: 18),
                label: const Text('Sign out'),
                onPressed: () async {
                  await ref.read(authProvider.notifier).signOut();
                  if (context.mounted) context.go(Routes.home);
                },
              ),
              Gap.sm,
              Center(
                child: TextButton(
                  onPressed: () async {
                    final confirmed = await showDialog<bool>(
                      context: context,
                      builder: (context) => AlertDialog(
                        title: const Text('Sign out everywhere?'),
                        content: const Text(
                          'Every phone, tablet and browser signed into this '
                          'account will be signed out, including this one.',
                        ),
                        actions: [
                          TextButton(
                            onPressed: () => Navigator.of(context).pop(false),
                            child: const Text('Cancel'),
                          ),
                          FilledButton(
                            onPressed: () => Navigator.of(context).pop(true),
                            child: const Text('Sign out everywhere'),
                          ),
                        ],
                      ),
                    );
                    if (confirmed ?? false) {
                      await ref
                          .read(authProvider.notifier)
                          .signOut(allDevices: true);
                      if (context.mounted) context.go(Routes.home);
                    }
                  },
                  child: const Text('Sign out of every device'),
                ),
              ),
            ],
          ),
      },
    );
  }
}

String _initials(UserDto user) {
  final source = user.fullName?.trim().isNotEmpty ?? false
      ? user.fullName!
      : user.email;
  return source
      .split(RegExp(r'[\s@.]+'))
      .where((part) => part.isNotEmpty)
      .take(2)
      .map((part) => part[0].toUpperCase())
      .join();
}

class _SessionsCard extends ConsumerWidget {
  const _SessionsCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sessions = ref.watch(sessionListProvider);
    final theme = Theme.of(context);

    return _SectionCard(
      title: 'Signed-in devices',
      subtitle:
          'Anything here you do not recognise, end it — then change your password.',
      children: [
        sessions.when(
          loading: () => const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Center(child: CircularProgressIndicator()),
          ),
          error: (error, _) => Text(
            error is Failure ? error.message : 'Could not load your sessions.',
            style: theme.textTheme.bodySmall
                ?.copyWith(color: theme.colorScheme.error),
          ),
          data: (items) => Column(
            children: [
              for (final session in items)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Row(
                    children: [
                      Flexible(
                        child: Text(session.deviceLabel ?? 'Unknown device'),
                      ),
                      if (session.isCurrent) ...[
                        Gap.sm,
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: theme.colorScheme.primaryContainer,
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text('This device',
                              style: theme.textTheme.labelSmall),
                        ),
                      ],
                    ],
                  ),
                  subtitle: Text(
                    'Last used ${formatRelative(session.lastUsedAt ?? session.createdAt)}',
                  ),
                  trailing: session.isCurrent
                      ? null
                      : TextButton(
                          onPressed: () async {
                            await ref
                                .read(authRepositoryProvider)
                                .revokeSession(session.id);
                            ref.invalidate(sessionListProvider);
                          },
                          child: const Text('Sign out'),
                        ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _VerifyEmailNotice extends StatelessWidget {
  const _VerifyEmailNotice({required this.email});

  final String email;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: theme.colorScheme.warningContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        'Your email is not verified yet. Booking confirmations and GST invoices '
        'are sent to $email, so it is worth doing before your next trip.',
        style: theme.textTheme.bodySmall
            ?.copyWith(color: theme.colorScheme.warning),
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({
    required this.title,
    required this.children,
    this.subtitle,
  });

  final String title;
  final String? subtitle;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title,
                style: theme.textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.w600)),
            if (subtitle != null) ...[
              Gap.xs,
              Text(subtitle!,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  )),
            ],
            Gap.sm,
            ...children,
          ],
        ),
      ),
    );
  }
}

/// The signed-in sessions.
final sessionListProvider = FutureProvider.autoDispose<List<SessionDto>>((ref) async {
  final result = await ref.watch(authRepositoryProvider).sessions();
  return switch (result) {
    Ok<List<SessionDto>>(:final value) => value,
    Err<List<SessionDto>>(:final failure) => throw failure,
  };
});
