import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';

/// Whether the device thinks it has a network.
///
/// Deliberately advisory. The platform reporting "connected" means an
/// interface is up, not that anything is reachable — captive portals, aeroplane
/// wifi and dead backhaul all report connected. So this is used to *explain* a
/// failure and to trigger a refetch when signal returns, never to decide
/// whether to attempt a request. The request itself is the only honest test.
class ConnectivityService {
  ConnectivityService({Connectivity? connectivity})
      : _connectivity = connectivity ?? Connectivity();

  final Connectivity _connectivity;

  Future<bool> get isOnline async =>
      _isOnline(await _connectivity.checkConnectivity());

  /// Emits `true` when connectivity returns, so a screen showing an offline
  /// state can retry itself instead of waiting for a pull-to-refresh.
  Stream<bool> get onStatusChange =>
      _connectivity.onConnectivityChanged.map(_isOnline).distinct();

  static bool _isOnline(List<ConnectivityResult> results) =>
      results.any((r) => r != ConnectivityResult.none);
}
