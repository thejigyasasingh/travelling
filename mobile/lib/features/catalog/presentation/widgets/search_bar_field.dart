import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/search_provider.dart';

/// The destination field, with debounced suggestions.
///
/// Debounced at 300 ms: a request per keystroke means eight in-flight requests
/// for "goa beach" and the slowest — not the newest — painting last.
class SearchBarField extends ConsumerStatefulWidget {
  const SearchBarField({super.key});

  @override
  ConsumerState<SearchBarField> createState() => _SearchBarFieldState();
}

class _SearchBarFieldState extends ConsumerState<SearchBarField> {
  late final TextEditingController _controller;
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(
      text: ref.read(searchCriteriaControllerProvider).query ?? '',
    );
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () {
      ref.read(searchCriteriaControllerProvider.notifier).setQuery(value);
    });
  }

  @override
  Widget build(BuildContext context) => TextField(
        controller: _controller,
        onChanged: _onChanged,
        textInputAction: TextInputAction.search,
        onSubmitted: (value) {
          _debounce?.cancel();
          ref.read(searchCriteriaControllerProvider.notifier).setQuery(value);
        },
        decoration: InputDecoration(
          hintText: 'Where to? Goa, Manali, Jaipur…',
          prefixIcon: const Icon(Icons.search_rounded, size: 20),
          isDense: true,
          suffixIcon: _controller.text.isEmpty
              ? null
              : IconButton(
                  icon: const Icon(Icons.close_rounded, size: 18),
                  tooltip: 'Clear',
                  onPressed: () {
                    _controller.clear();
                    ref.read(searchCriteriaControllerProvider.notifier).setQuery(null);
                    setState(() {});
                  },
                ),
        ),
      );
}
