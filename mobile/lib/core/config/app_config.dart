/// Build-time configuration.
///
/// Read from `--dart-define`, not from a checked-in file: an API host baked
/// into source is the reason someone eventually ships a debug build pointed at
/// production. Nothing secret lives here — a mobile binary is a file anyone can
/// unzip, so the only credentials it may hold are public ones (the Razorpay
/// *key id*, which authorises nothing on its own).
library;

enum Flavor { dev, staging, prod }

class AppConfig {
  const AppConfig({
    required this.apiBaseUrl,
    required this.flavor,
    required this.razorpayKeyId,
    this.connectTimeout = const Duration(seconds: 8),
    this.receiveTimeout = const Duration(seconds: 20),
  });

  final String apiBaseUrl;
  final Flavor flavor;
  final String razorpayKeyId;
  final Duration connectTimeout;
  final Duration receiveTimeout;

  bool get isProduction => flavor == Flavor.prod;

  /// The default points at the host loopback as seen from an Android emulator.
  /// `localhost` inside the emulator is the emulator itself, which is the
  /// single most common "why can't the app reach my server" hour lost.
  static const _defaultBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1',
  );

  static AppConfig fromEnvironment() {
    const flavorName = String.fromEnvironment('FLAVOR', defaultValue: 'dev');
    return AppConfig(
      apiBaseUrl: _defaultBaseUrl,
      flavor: Flavor.values.firstWhere(
        (f) => f.name == flavorName,
        orElse: () => Flavor.dev,
      ),
      razorpayKeyId: const String.fromEnvironment('RAZORPAY_KEY_ID'),
    );
  }
}
