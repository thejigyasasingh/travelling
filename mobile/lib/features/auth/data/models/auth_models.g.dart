// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'auth_models.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_UserDto _$UserDtoFromJson(Map<String, dynamic> json) => _UserDto(
  id: json['id'] as String,
  email: json['email'] as String,
  fullName: json['full_name'] as String?,
  phone: json['phone'] as String?,
  avatarUrl: json['avatar_url'] as String?,
  status: json['status'] as String? ?? 'active',
  roles:
      (json['roles'] as List<dynamic>?)?.map((e) => e as String).toList() ??
      const <String>[],
  permissions:
      (json['permissions'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList() ??
      const <String>[],
  emailVerified: json['email_verified'] as bool? ?? false,
  phoneVerified: json['phone_verified'] as bool? ?? false,
  hasPassword: json['has_password'] as bool? ?? true,
  locale: json['locale'] as String? ?? 'en-IN',
  timezone: json['timezone'] as String? ?? 'Asia/Kolkata',
  vendorId: json['vendor_id'] as String?,
  lastLoginAt: json['last_login_at'] as String?,
);

Map<String, dynamic> _$UserDtoToJson(_UserDto instance) => <String, dynamic>{
  'id': instance.id,
  'email': instance.email,
  'full_name': instance.fullName,
  'phone': instance.phone,
  'avatar_url': instance.avatarUrl,
  'status': instance.status,
  'roles': instance.roles,
  'permissions': instance.permissions,
  'email_verified': instance.emailVerified,
  'phone_verified': instance.phoneVerified,
  'has_password': instance.hasPassword,
  'locale': instance.locale,
  'timezone': instance.timezone,
  'vendor_id': instance.vendorId,
  'last_login_at': instance.lastLoginAt,
};

_TokenDto _$TokenDtoFromJson(Map<String, dynamic> json) => _TokenDto(
  accessToken: json['access_token'] as String,
  refreshToken: json['refresh_token'] as String,
  expiresIn: (json['expires_in'] as num?)?.toInt() ?? 900,
  refreshExpiresIn: (json['refresh_expires_in'] as num?)?.toInt() ?? 2592000,
);

Map<String, dynamic> _$TokenDtoToJson(_TokenDto instance) => <String, dynamic>{
  'access_token': instance.accessToken,
  'refresh_token': instance.refreshToken,
  'expires_in': instance.expiresIn,
  'refresh_expires_in': instance.refreshExpiresIn,
};

_AuthResponseDto _$AuthResponseDtoFromJson(Map<String, dynamic> json) =>
    _AuthResponseDto(
      tokens: TokenDto.fromJson(json['tokens'] as Map<String, dynamic>),
      user: UserDto.fromJson(json['user'] as Map<String, dynamic>),
      isNewUser: json['is_new_user'] as bool? ?? false,
    );

Map<String, dynamic> _$AuthResponseDtoToJson(_AuthResponseDto instance) =>
    <String, dynamic>{
      'tokens': instance.tokens,
      'user': instance.user,
      'is_new_user': instance.isNewUser,
    };

_SessionDto _$SessionDtoFromJson(Map<String, dynamic> json) => _SessionDto(
  id: json['id'] as String,
  deviceLabel: json['device_label'] as String?,
  userAgent: json['user_agent'] as String?,
  createdAt: json['created_at'] as String? ?? '',
  lastUsedAt: json['last_used_at'] as String?,
  expiresAt: json['expires_at'] as String? ?? '',
  isCurrent: json['is_current'] as bool? ?? false,
);

Map<String, dynamic> _$SessionDtoToJson(_SessionDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'device_label': instance.deviceLabel,
      'user_agent': instance.userAgent,
      'created_at': instance.createdAt,
      'last_used_at': instance.lastUsedAt,
      'expires_at': instance.expiresAt,
      'is_current': instance.isCurrent,
    };

_OtpChallengeDto _$OtpChallengeDtoFromJson(Map<String, dynamic> json) =>
    _OtpChallengeDto(
      challengeId: json['challenge_id'] as String,
      expiresIn: (json['expires_in'] as num?)?.toInt() ?? 300,
      resendAfter: (json['resend_after'] as num?)?.toInt() ?? 30,
    );

Map<String, dynamic> _$OtpChallengeDtoToJson(_OtpChallengeDto instance) =>
    <String, dynamic>{
      'challenge_id': instance.challengeId,
      'expires_in': instance.expiresIn,
      'resend_after': instance.resendAfter,
    };

_MessageDto _$MessageDtoFromJson(Map<String, dynamic> json) => _MessageDto(
  message: json['message'] as String? ?? '',
  detail: json['detail'] as String?,
);

Map<String, dynamic> _$MessageDtoToJson(_MessageDto instance) =>
    <String, dynamic>{'message': instance.message, 'detail': instance.detail};
