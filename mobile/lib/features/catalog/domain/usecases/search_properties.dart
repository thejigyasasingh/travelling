import 'package:dio/dio.dart';

import '../../../../core/network/result.dart';
import '../../data/repositories/catalog_repository.dart';
import '../entities/search_criteria.dart';

/// Search, one page at a time.
///
/// Thin on purpose. The pagination *state* belongs to the provider that owns
/// the list; this exists so the rule "a filter change invalidates the cursor"
/// has somewhere to live that a screen cannot bypass — page three of the old
/// result set is meaningless in the new one.
class SearchProperties {
  const SearchProperties(this._repository);

  final CatalogRepository _repository;

  Future<Result<SearchPage>> call(
    SearchCriteria criteria, {
    String? cursor,
    int limit = 20,
    CancelToken? cancelToken,
  }) =>
      _repository.search(
        criteria,
        cursor: cursor,
        limit: limit,
        cancelToken: cancelToken,
      );
}
