@Tags(['live'])
library;

import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:roaming_wandering/features/auth/data/models/auth_models.dart';
import 'package:roaming_wandering/features/booking/data/models/booking_models.dart';
import 'package:roaming_wandering/features/catalog/data/models/property_models.dart';

/// Parses **live** API responses through the app's real DTOs.
///
/// A schema says what a server *should* send; this reads what it actually
/// sends. The difference is where the expensive bugs live — a sibling client
/// was written from a schema listing and silently mis-parsed `/auth/refresh`,
/// breaking every session restore in a way no unit test could see.
///
/// Skipped automatically when nothing is listening, so the ordinary suite stays
/// green without a backend:
///
///     flutter test --tags live
void main() {
  const baseUrl = 'http://localhost:8000/api/v1';
  const email = 'journey@example.com';
  const password = 'a-very-long-passphrase-2026';

  late Dio dio;
  var serverUp = false;

  setUpAll(() async {
    dio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        validateStatus: (status) => status != null && status < 500,
        connectTimeout: const Duration(seconds: 3),
      ),
    );
    try {
      final response = await dio.get<Map<String, dynamic>>('/ping');
      serverUp = response.statusCode == 200;
    } on DioException {
      serverUp = false;
    } on SocketException {
      serverUp = false;
    }
  });

  Future<String?> signIn() async {
    final response = await dio.post<Map<String, dynamic>>(
      '/auth/login',
      data: {'email': email, 'password': password},
    );
    if (response.statusCode != 200) return null;
    return AuthResponseDto.fromJson(response.data!).tokens.accessToken;
  }

  test('search results parse into SearchPageDto', () async {
    if (!serverUp) return;
    final response = await dio
        .get<Map<String, dynamic>>('/search', queryParameters: {'limit': 2});

    expect(response.statusCode, 200);
    final page = SearchPageDto.fromJson(response.data!);
    for (final item in page.items) {
      expect(item.id, isNotEmpty);
      expect(item.slug, isNotEmpty);
      expect(item.currency, isNotEmpty);
      // A nightly "from" and a stay total are different numbers with different
      // labels; neither may be silently substituted for the other.
      expect(item.totalPriceMinor, anyOf(isNull, isA<int>()));
    }
  });

  test('a property parses, nested rooms and images included', () async {
    if (!serverUp) return;
    final search = await dio
        .get<Map<String, dynamic>>('/search', queryParameters: {'limit': 1});
    final items = SearchPageDto.fromJson(search.data!).items;
    if (items.isEmpty) return;

    final response =
        await dio.get<Map<String, dynamic>>('/properties/${items.first.slug}');
    expect(response.statusCode, 200);

    final property = PropertyDto.fromJson(response.data!);
    expect(property.id, isNotEmpty);
    expect(property.name, isNotEmpty);
    for (final room in property.roomTypes) {
      expect(room.id, isNotEmpty);
      expect(room.baseRateMinor, greaterThanOrEqualTo(0));
    }
  });

  test('amenities parse', () async {
    if (!serverUp) return;
    final response = await dio.get<List<dynamic>>('/amenities');
    for (final raw in response.data ?? []) {
      final amenity = AmenityDto.fromJson(raw as Map<String, dynamic>);
      expect(amenity.code, isNotEmpty);
      expect(amenity.label, isNotEmpty);
    }
  });

  test('login returns tokens AND a user, and both parse', () async {
    if (!serverUp) return;
    final response = await dio.post<Map<String, dynamic>>(
      '/auth/login',
      data: {'email': email, 'password': password},
    );
    if (response.statusCode != 200) return; // seeded account absent

    final auth = AuthResponseDto.fromJson(response.data!);
    expect(auth.tokens.accessToken, isNotEmpty);
    expect(auth.tokens.refreshToken, isNotEmpty);
    expect(auth.user.email, contains('@'));
  });

  test('refresh returns the SAME envelope as login, not a bare token', () async {
    if (!serverUp) return;
    final login = await dio.post<Map<String, dynamic>>(
      '/auth/login',
      data: {'email': email, 'password': password},
    );
    if (login.statusCode != 200) return;

    final refreshToken =
        AuthResponseDto.fromJson(login.data!).tokens.refreshToken;
    final response = await dio.post<Map<String, dynamic>>(
      '/auth/refresh',
      data: {'refresh_token': refreshToken},
    );

    expect(response.statusCode, 200);
    // The bug this pins down: the interceptor reads
    // `data['tokens']['access_token']`. If the server returned a flat token —
    // or if someone "simplified" the interceptor to read the top level — every
    // session restore would fail silently and every request would then carry
    // `Bearer null`.
    expect(
      response.data!.containsKey('tokens'),
      isTrue,
      reason: '/auth/refresh must nest tokens under "tokens"',
    );
    final refreshed = AuthResponseDto.fromJson(response.data!);
    expect(refreshed.tokens.accessToken, isNotEmpty);
    // Rotated: presenting the old one again reads as theft and revokes the
    // whole family.
    expect(refreshed.tokens.refreshToken, isNot(refreshToken));
  });

  test('registration answers a message, never tokens', () async {
    if (!serverUp) return;
    final response = await dio.post<Map<String, dynamic>>(
      '/auth/register',
      data: {
        'email': 'contract-check@example.com',
        'password': password,
        'full_name': 'Contract Check',
      },
    );
    if (response.statusCode != 202) return;

    // Deliberate: the response says nothing about whether the address was
    // already registered, so the endpoint is not a membership oracle.
    expect(response.data!.containsKey('tokens'), isFalse);
    expect(MessageDto.fromJson(response.data!).message, isNotEmpty);
  });

  test('the bookings list parses', () async {
    if (!serverUp) return;
    final token = await signIn();
    if (token == null) return;

    final response = await dio.get<Map<String, dynamic>>(
      '/bookings',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    expect(response.statusCode, 200);

    final page = BookingListDto.fromJson(response.data!);
    for (final booking in page.items) {
      expect(booking.reference, isNotEmpty);
      expect(booking.checkIn, matches(RegExp(r'^\d{4}-\d{2}-\d{2}$')));
      expect(booking.totalMinor, greaterThan(0));
    }
  });

  test('an error body parses into the envelope the app expects', () async {
    if (!serverUp) return;
    final response = await dio.get<Map<String, dynamic>>('/bookings');

    expect(response.statusCode, 401);
    // `{error: {code, message, request_id}}` — what `mapDioError` unpacks.
    final error = response.data!['error'] as Map<String, dynamic>;
    expect(error['code'], isNotNull);
    expect(error['message'], isNotNull);
  });
}
