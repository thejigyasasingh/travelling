import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'core/providers/app_providers.dart';
import 'core/storage/cache_store.dart';
import 'core/storage/token_store.dart';

/// Boot.
///
/// The two async stores are opened **here**, before `runApp`, and injected as
/// provider overrides. The alternative — a `FutureProvider` the widget tree
/// waits on — means every screen has to handle a "storage not ready" state that
/// exists for 40 ms at launch and never again. Opening them first costs a few
/// milliseconds of splash and removes that state entirely.
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final cache = await CacheStore.open();
  final tokens = TokenStore();
  // Reads the access token off the Keychain into memory once, so the request
  // interceptor never has to await platform storage per request.
  await tokens.load();

  runApp(
    ProviderScope(
      overrides: [
        cacheStoreProvider.overrideWithValue(cache),
        tokenStoreProvider.overrideWithValue(tokens),
      ],
      child: const RoamingWanderingApp(),
    ),
  );
}
