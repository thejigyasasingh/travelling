import 'package:freezed_annotation/freezed_annotation.dart';

part 'auth_models.freezed.dart';
part 'auth_models.g.dart';

@freezed
abstract class UserDto with _$UserDto {
  const factory UserDto({
    required String id,
    required String email,
    @JsonKey(name: 'full_name') String? fullName,
    String? phone,
    @JsonKey(name: 'avatar_url') String? avatarUrl,
    @Default('active') String status,
    @Default(<String>[]) List<String> roles,
    @Default(<String>[]) List<String> permissions,
    @JsonKey(name: 'email_verified') @Default(false) bool emailVerified,
    @JsonKey(name: 'phone_verified') @Default(false) bool phoneVerified,
    /// False for a Google-only account: there is no password to change.
    @JsonKey(name: 'has_password') @Default(true) bool hasPassword,
    @Default('en-IN') String locale,
    @Default('Asia/Kolkata') String timezone,
    @JsonKey(name: 'vendor_id') String? vendorId,
    @JsonKey(name: 'last_login_at') String? lastLoginAt,
  }) = _UserDto;

  factory UserDto.fromJson(Map<String, dynamic> json) => _$UserDtoFromJson(json);
}

@freezed
abstract class TokenDto with _$TokenDto {
  const factory TokenDto({
    @JsonKey(name: 'access_token') required String accessToken,
    @JsonKey(name: 'refresh_token') required String refreshToken,
    @JsonKey(name: 'expires_in') @Default(900) int expiresIn,
    @JsonKey(name: 'refresh_expires_in') @Default(2592000) int refreshExpiresIn,
  }) = _TokenDto;

  factory TokenDto.fromJson(Map<String, dynamic> json) =>
      _$TokenDtoFromJson(json);
}

/// What `/auth/login`, `/auth/otp/verify` and — importantly — `/auth/refresh`
/// all return: tokens **and** the user. Verified against a running server; an
/// earlier assumption that refresh returned a bare token silently broke every
/// session restore.
@freezed
abstract class AuthResponseDto with _$AuthResponseDto {
  const factory AuthResponseDto({
    required TokenDto tokens,
    required UserDto user,
    @JsonKey(name: 'is_new_user') @Default(false) bool isNewUser,
  }) = _AuthResponseDto;

  factory AuthResponseDto.fromJson(Map<String, dynamic> json) =>
      _$AuthResponseDtoFromJson(json);
}

@freezed
abstract class SessionDto with _$SessionDto {
  const factory SessionDto({
    required String id,
    @JsonKey(name: 'device_label') String? deviceLabel,
    @JsonKey(name: 'user_agent') String? userAgent,
    @JsonKey(name: 'created_at') @Default('') String createdAt,
    @JsonKey(name: 'last_used_at') String? lastUsedAt,
    @JsonKey(name: 'expires_at') @Default('') String expiresAt,
    @JsonKey(name: 'is_current') @Default(false) bool isCurrent,
  }) = _SessionDto;

  factory SessionDto.fromJson(Map<String, dynamic> json) =>
      _$SessionDtoFromJson(json);
}

@freezed
abstract class OtpChallengeDto with _$OtpChallengeDto {
  const factory OtpChallengeDto({
    @JsonKey(name: 'challenge_id') required String challengeId,
    @JsonKey(name: 'expires_in') @Default(300) int expiresIn,
    @JsonKey(name: 'resend_after') @Default(30) int resendAfter,
  }) = _OtpChallengeDto;

  factory OtpChallengeDto.fromJson(Map<String, dynamic> json) =>
      _$OtpChallengeDtoFromJson(json);
}

/// Registration answers 202 with a message and **no tokens**, deliberately: the
/// response says nothing about whether the address was already registered,
/// because that would make the endpoint a membership oracle for a leaked email
/// list. The user signs in after verifying.
@freezed
abstract class MessageDto with _$MessageDto {
  const factory MessageDto({
    @Default('') String message,
    String? detail,
  }) = _MessageDto;

  factory MessageDto.fromJson(Map<String, dynamic> json) =>
      _$MessageDtoFromJson(json);
}
