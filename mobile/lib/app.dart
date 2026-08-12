import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';

class RoamingWanderingApp extends ConsumerWidget {
  const RoamingWanderingApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);

    return MaterialApp.router(
      title: 'Roaming & Wandering',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      // Follows the OS. Forcing light mode on someone who has chosen dark is a
      // small disrespect that a travel app — used on planes and at night — can
      // least afford.
      themeMode: ThemeMode.system,
      routerConfig: router,
      builder: (context, child) {
        // Clamp text scaling. Honouring the user's setting is right; letting it
        // reach 3× turns a price row into an unreadable overlap, so it is
        // bounded rather than ignored.
        final scale = MediaQuery.textScalerOf(context).clamp(
          minScaleFactor: 0.8,
          maxScaleFactor: 1.6,
        );
        return MediaQuery(
          data: MediaQuery.of(context).copyWith(textScaler: scale),
          child: child ?? const SizedBox.shrink(),
        );
      },
    );
  }
}
