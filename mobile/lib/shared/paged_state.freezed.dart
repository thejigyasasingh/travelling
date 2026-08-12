// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'paged_state.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;
/// @nodoc
mixin _$PagedState<T> {

 List<T> get items; String? get nextCursor; int? get totalEstimate;/// The first load, with nothing to show yet.
 bool get isInitialLoading;/// Fetching the next page, with items already on screen.
 bool get isLoadingMore;/// A pull-to-refresh over existing items.
 bool get isRefreshing;/// Failed the *first* load: there is nothing to show but this.
 Failure? get initialError;/// Failed a *subsequent* page: the list stands, with a retry at the end.
 Failure? get pageError;/// Served from cache because the network was unreachable.
 bool get isStale; DateTime? get cachedAt;
/// Create a copy of PagedState
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$PagedStateCopyWith<T, PagedState<T>> get copyWith => _$PagedStateCopyWithImpl<T, PagedState<T>>(this as PagedState<T>, _$identity);



@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is PagedState<T>&&const DeepCollectionEquality().equals(other.items, items)&&(identical(other.nextCursor, nextCursor) || other.nextCursor == nextCursor)&&(identical(other.totalEstimate, totalEstimate) || other.totalEstimate == totalEstimate)&&(identical(other.isInitialLoading, isInitialLoading) || other.isInitialLoading == isInitialLoading)&&(identical(other.isLoadingMore, isLoadingMore) || other.isLoadingMore == isLoadingMore)&&(identical(other.isRefreshing, isRefreshing) || other.isRefreshing == isRefreshing)&&(identical(other.initialError, initialError) || other.initialError == initialError)&&(identical(other.pageError, pageError) || other.pageError == pageError)&&(identical(other.isStale, isStale) || other.isStale == isStale)&&(identical(other.cachedAt, cachedAt) || other.cachedAt == cachedAt));
}


@override
int get hashCode => Object.hash(runtimeType,const DeepCollectionEquality().hash(items),nextCursor,totalEstimate,isInitialLoading,isLoadingMore,isRefreshing,initialError,pageError,isStale,cachedAt);

@override
String toString() {
  return 'PagedState<$T>(items: $items, nextCursor: $nextCursor, totalEstimate: $totalEstimate, isInitialLoading: $isInitialLoading, isLoadingMore: $isLoadingMore, isRefreshing: $isRefreshing, initialError: $initialError, pageError: $pageError, isStale: $isStale, cachedAt: $cachedAt)';
}


}

/// @nodoc
abstract mixin class $PagedStateCopyWith<T,$Res>  {
  factory $PagedStateCopyWith(PagedState<T> value, $Res Function(PagedState<T>) _then) = _$PagedStateCopyWithImpl;
@useResult
$Res call({
 List<T> items, String? nextCursor, int? totalEstimate, bool isInitialLoading, bool isLoadingMore, bool isRefreshing, Failure? initialError, Failure? pageError, bool isStale, DateTime? cachedAt
});


$FailureCopyWith<$Res>? get initialError;$FailureCopyWith<$Res>? get pageError;

}
/// @nodoc
class _$PagedStateCopyWithImpl<T,$Res>
    implements $PagedStateCopyWith<T, $Res> {
  _$PagedStateCopyWithImpl(this._self, this._then);

  final PagedState<T> _self;
  final $Res Function(PagedState<T>) _then;

/// Create a copy of PagedState
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? items = null,Object? nextCursor = freezed,Object? totalEstimate = freezed,Object? isInitialLoading = null,Object? isLoadingMore = null,Object? isRefreshing = null,Object? initialError = freezed,Object? pageError = freezed,Object? isStale = null,Object? cachedAt = freezed,}) {
  return _then(_self.copyWith(
items: null == items ? _self.items : items // ignore: cast_nullable_to_non_nullable
as List<T>,nextCursor: freezed == nextCursor ? _self.nextCursor : nextCursor // ignore: cast_nullable_to_non_nullable
as String?,totalEstimate: freezed == totalEstimate ? _self.totalEstimate : totalEstimate // ignore: cast_nullable_to_non_nullable
as int?,isInitialLoading: null == isInitialLoading ? _self.isInitialLoading : isInitialLoading // ignore: cast_nullable_to_non_nullable
as bool,isLoadingMore: null == isLoadingMore ? _self.isLoadingMore : isLoadingMore // ignore: cast_nullable_to_non_nullable
as bool,isRefreshing: null == isRefreshing ? _self.isRefreshing : isRefreshing // ignore: cast_nullable_to_non_nullable
as bool,initialError: freezed == initialError ? _self.initialError : initialError // ignore: cast_nullable_to_non_nullable
as Failure?,pageError: freezed == pageError ? _self.pageError : pageError // ignore: cast_nullable_to_non_nullable
as Failure?,isStale: null == isStale ? _self.isStale : isStale // ignore: cast_nullable_to_non_nullable
as bool,cachedAt: freezed == cachedAt ? _self.cachedAt : cachedAt // ignore: cast_nullable_to_non_nullable
as DateTime?,
  ));
}
/// Create a copy of PagedState
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$FailureCopyWith<$Res>? get initialError {
    if (_self.initialError == null) {
    return null;
  }

  return $FailureCopyWith<$Res>(_self.initialError!, (value) {
    return _then(_self.copyWith(initialError: value));
  });
}/// Create a copy of PagedState
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$FailureCopyWith<$Res>? get pageError {
    if (_self.pageError == null) {
    return null;
  }

  return $FailureCopyWith<$Res>(_self.pageError!, (value) {
    return _then(_self.copyWith(pageError: value));
  });
}
}


/// Adds pattern-matching-related methods to [PagedState].
extension PagedStatePatterns<T> on PagedState<T> {
/// A variant of `map` that fallback to returning `orElse`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _PagedState<T> value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _PagedState() when $default != null:
return $default(_that);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// Callbacks receives the raw object, upcasted.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case final Subclass2 value:
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _PagedState<T> value)  $default,){
final _that = this;
switch (_that) {
case _PagedState():
return $default(_that);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `map` that fallback to returning `null`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _PagedState<T> value)?  $default,){
final _that = this;
switch (_that) {
case _PagedState() when $default != null:
return $default(_that);case _:
  return null;

}
}
/// A variant of `when` that fallback to an `orElse` callback.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( List<T> items,  String? nextCursor,  int? totalEstimate,  bool isInitialLoading,  bool isLoadingMore,  bool isRefreshing,  Failure? initialError,  Failure? pageError,  bool isStale,  DateTime? cachedAt)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _PagedState() when $default != null:
return $default(_that.items,_that.nextCursor,_that.totalEstimate,_that.isInitialLoading,_that.isLoadingMore,_that.isRefreshing,_that.initialError,_that.pageError,_that.isStale,_that.cachedAt);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// As opposed to `map`, this offers destructuring.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case Subclass2(:final field2):
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( List<T> items,  String? nextCursor,  int? totalEstimate,  bool isInitialLoading,  bool isLoadingMore,  bool isRefreshing,  Failure? initialError,  Failure? pageError,  bool isStale,  DateTime? cachedAt)  $default,) {final _that = this;
switch (_that) {
case _PagedState():
return $default(_that.items,_that.nextCursor,_that.totalEstimate,_that.isInitialLoading,_that.isLoadingMore,_that.isRefreshing,_that.initialError,_that.pageError,_that.isStale,_that.cachedAt);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `when` that fallback to returning `null`
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( List<T> items,  String? nextCursor,  int? totalEstimate,  bool isInitialLoading,  bool isLoadingMore,  bool isRefreshing,  Failure? initialError,  Failure? pageError,  bool isStale,  DateTime? cachedAt)?  $default,) {final _that = this;
switch (_that) {
case _PagedState() when $default != null:
return $default(_that.items,_that.nextCursor,_that.totalEstimate,_that.isInitialLoading,_that.isLoadingMore,_that.isRefreshing,_that.initialError,_that.pageError,_that.isStale,_that.cachedAt);case _:
  return null;

}
}

}

/// @nodoc


class _PagedState<T> extends PagedState<T> {
  const _PagedState({final  List<T> items = const <Never>[], this.nextCursor, this.totalEstimate, this.isInitialLoading = true, this.isLoadingMore = false, this.isRefreshing = false, this.initialError, this.pageError, this.isStale = false, this.cachedAt}): _items = items,super._();
  

 final  List<T> _items;
@override@JsonKey() List<T> get items {
  if (_items is EqualUnmodifiableListView) return _items;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_items);
}

@override final  String? nextCursor;
@override final  int? totalEstimate;
/// The first load, with nothing to show yet.
@override@JsonKey() final  bool isInitialLoading;
/// Fetching the next page, with items already on screen.
@override@JsonKey() final  bool isLoadingMore;
/// A pull-to-refresh over existing items.
@override@JsonKey() final  bool isRefreshing;
/// Failed the *first* load: there is nothing to show but this.
@override final  Failure? initialError;
/// Failed a *subsequent* page: the list stands, with a retry at the end.
@override final  Failure? pageError;
/// Served from cache because the network was unreachable.
@override@JsonKey() final  bool isStale;
@override final  DateTime? cachedAt;

/// Create a copy of PagedState
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$PagedStateCopyWith<T, _PagedState<T>> get copyWith => __$PagedStateCopyWithImpl<T, _PagedState<T>>(this, _$identity);



@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _PagedState<T>&&const DeepCollectionEquality().equals(other._items, _items)&&(identical(other.nextCursor, nextCursor) || other.nextCursor == nextCursor)&&(identical(other.totalEstimate, totalEstimate) || other.totalEstimate == totalEstimate)&&(identical(other.isInitialLoading, isInitialLoading) || other.isInitialLoading == isInitialLoading)&&(identical(other.isLoadingMore, isLoadingMore) || other.isLoadingMore == isLoadingMore)&&(identical(other.isRefreshing, isRefreshing) || other.isRefreshing == isRefreshing)&&(identical(other.initialError, initialError) || other.initialError == initialError)&&(identical(other.pageError, pageError) || other.pageError == pageError)&&(identical(other.isStale, isStale) || other.isStale == isStale)&&(identical(other.cachedAt, cachedAt) || other.cachedAt == cachedAt));
}


@override
int get hashCode => Object.hash(runtimeType,const DeepCollectionEquality().hash(_items),nextCursor,totalEstimate,isInitialLoading,isLoadingMore,isRefreshing,initialError,pageError,isStale,cachedAt);

@override
String toString() {
  return 'PagedState<$T>(items: $items, nextCursor: $nextCursor, totalEstimate: $totalEstimate, isInitialLoading: $isInitialLoading, isLoadingMore: $isLoadingMore, isRefreshing: $isRefreshing, initialError: $initialError, pageError: $pageError, isStale: $isStale, cachedAt: $cachedAt)';
}


}

/// @nodoc
abstract mixin class _$PagedStateCopyWith<T,$Res> implements $PagedStateCopyWith<T, $Res> {
  factory _$PagedStateCopyWith(_PagedState<T> value, $Res Function(_PagedState<T>) _then) = __$PagedStateCopyWithImpl;
@override @useResult
$Res call({
 List<T> items, String? nextCursor, int? totalEstimate, bool isInitialLoading, bool isLoadingMore, bool isRefreshing, Failure? initialError, Failure? pageError, bool isStale, DateTime? cachedAt
});


@override $FailureCopyWith<$Res>? get initialError;@override $FailureCopyWith<$Res>? get pageError;

}
/// @nodoc
class __$PagedStateCopyWithImpl<T,$Res>
    implements _$PagedStateCopyWith<T, $Res> {
  __$PagedStateCopyWithImpl(this._self, this._then);

  final _PagedState<T> _self;
  final $Res Function(_PagedState<T>) _then;

/// Create a copy of PagedState
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? items = null,Object? nextCursor = freezed,Object? totalEstimate = freezed,Object? isInitialLoading = null,Object? isLoadingMore = null,Object? isRefreshing = null,Object? initialError = freezed,Object? pageError = freezed,Object? isStale = null,Object? cachedAt = freezed,}) {
  return _then(_PagedState<T>(
items: null == items ? _self._items : items // ignore: cast_nullable_to_non_nullable
as List<T>,nextCursor: freezed == nextCursor ? _self.nextCursor : nextCursor // ignore: cast_nullable_to_non_nullable
as String?,totalEstimate: freezed == totalEstimate ? _self.totalEstimate : totalEstimate // ignore: cast_nullable_to_non_nullable
as int?,isInitialLoading: null == isInitialLoading ? _self.isInitialLoading : isInitialLoading // ignore: cast_nullable_to_non_nullable
as bool,isLoadingMore: null == isLoadingMore ? _self.isLoadingMore : isLoadingMore // ignore: cast_nullable_to_non_nullable
as bool,isRefreshing: null == isRefreshing ? _self.isRefreshing : isRefreshing // ignore: cast_nullable_to_non_nullable
as bool,initialError: freezed == initialError ? _self.initialError : initialError // ignore: cast_nullable_to_non_nullable
as Failure?,pageError: freezed == pageError ? _self.pageError : pageError // ignore: cast_nullable_to_non_nullable
as Failure?,isStale: null == isStale ? _self.isStale : isStale // ignore: cast_nullable_to_non_nullable
as bool,cachedAt: freezed == cachedAt ? _self.cachedAt : cachedAt // ignore: cast_nullable_to_non_nullable
as DateTime?,
  ));
}

/// Create a copy of PagedState
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$FailureCopyWith<$Res>? get initialError {
    if (_self.initialError == null) {
    return null;
  }

  return $FailureCopyWith<$Res>(_self.initialError!, (value) {
    return _then(_self.copyWith(initialError: value));
  });
}/// Create a copy of PagedState
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$FailureCopyWith<$Res>? get pageError {
    if (_self.pageError == null) {
    return null;
  }

  return $FailureCopyWith<$Res>(_self.pageError!, (value) {
    return _then(_self.copyWith(pageError: value));
  });
}
}

// dart format on
