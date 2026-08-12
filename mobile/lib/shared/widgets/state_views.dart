import 'package:flutter/material.dart';

import '../../core/error/failure.dart';
import '../../core/theme/app_theme.dart';

/// Loading, empty, error and offline states.
///
/// They exist as widgets because every list needs all four, and hand-rolling
/// them per screen is how an app ends up with a blank page for "no results" on
/// one screen and a spinner that never resolves on another.
class LoadingView extends StatelessWidget {
  const LoadingView({super.key, this.label});

  final String? label;

  @override
  Widget build(BuildContext context) => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            if (label != null) ...[
              Gap.md,
              Text(label!, style: Theme.of(context).textTheme.bodyMedium),
            ],
          ],
        ),
      );
}

class EmptyView extends StatelessWidget {
  const EmptyView({
    required this.title,
    super.key,
    this.description,
    this.icon,
    this.action,
  });

  final String title;
  final String? description;
  final IconData? icon;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null)
              Icon(icon, size: 48, color: theme.colorScheme.outline),
            Gap.md,
            Text(
              title,
              style: theme.textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.w600),
              textAlign: TextAlign.center,
            ),
            if (description != null) ...[
              Gap.sm,
              Text(
                description!,
                style: theme.textTheme.bodyMedium
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                textAlign: TextAlign.center,
              ),
            ],
            if (action != null) ...[Gap.lg, action!],
          ],
        ),
      ),
    );
  }
}

/// An error, with a retry only when retrying could plausibly help.
///
/// A 409 "those dates are gone" gets no retry button: the state genuinely
/// differs, and offering a retry teaches people that the button does nothing.
class ErrorView extends StatelessWidget {
  const ErrorView({
    required this.failure,
    super.key,
    this.onRetry,
    this.title,
  });

  final Failure failure;
  final VoidCallback? onRetry;
  final String? title;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final offline = failure.isOffline;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              offline ? Icons.wifi_off_rounded : Icons.error_outline_rounded,
              size: 48,
              color: offline
                  ? theme.colorScheme.onSurfaceVariant
                  : theme.colorScheme.error,
            ),
            Gap.md,
            Text(
              title ?? (offline ? 'You are offline' : 'Something went wrong'),
              style: theme.textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.w600),
              textAlign: TextAlign.center,
            ),
            Gap.sm,
            Text(
              failure.message,
              style: theme.textTheme.bodyMedium
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              textAlign: TextAlign.center,
            ),
            // Quoting the request id turns "it broke" into one log lookup.
            if (failure.requestId != null) ...[
              Gap.sm,
              SelectableText(
                'Reference: ${failure.requestId}',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.outline,
                  fontFamily: 'monospace',
                ),
              ),
            ],
            if (onRetry != null && failure.isRetryable) ...[
              Gap.lg,
              OutlinedButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh_rounded, size: 18),
                label: const Text('Try again'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// A banner saying the content on screen was saved earlier.
///
/// Shown *with* the content, never instead of it. Stale data plus an honest
/// label beats a spinner on a train — and beats stale data pretending to be
/// live, which is how a guest arrives at checkout to a different price.
class StaleDataBanner extends StatelessWidget {
  const StaleDataBanner({required this.cachedAt, super.key, this.onRefresh});

  final DateTime? cachedAt;
  final VoidCallback? onRefresh;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      color: theme.colorScheme.warningContainer,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        child: Row(
          children: [
            Icon(Icons.cloud_off_rounded,
                size: 18, color: theme.colorScheme.warning),
            Gap.sm,
            Expanded(
              child: Text(
                'Showing saved results — prices and availability may have changed.',
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.warning),
              ),
            ),
            if (onRefresh != null)
              TextButton(onPressed: onRefresh, child: const Text('Refresh')),
          ],
        ),
      ),
    );
  }
}

/// A shimmering placeholder. Sized like the content it stands in for, so the
/// layout does not jump when the real thing arrives.
class ShimmerBox extends StatefulWidget {
  const ShimmerBox({
    super.key,
    this.width,
    this.height = 16,
    this.radius = 8,
  });

  final double? width;
  final double height;
  final double radius;

  @override
  State<ShimmerBox> createState() => _ShimmerBoxState();
}

class _ShimmerBoxState extends State<ShimmerBox>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  )..repeat();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final base = Theme.of(context).colorScheme.surfaceContainerHighest;
    // Respect the OS setting. A shimmer is exactly the kind of continuous
    // motion that triggers vestibular discomfort.
    if (MediaQuery.disableAnimationsOf(context)) {
      return _box(base);
    }
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) => ShaderMask(
        blendMode: BlendMode.srcATop,
        shaderCallback: (bounds) => LinearGradient(
          begin: Alignment(-1 - 2 * _controller.value, 0),
          end: Alignment(1 - 2 * _controller.value, 0),
          colors: [base, base.withValues(alpha: 0.4), base],
          stops: const [0.35, 0.5, 0.65],
        ).createShader(bounds),
        child: _box(base),
      ),
    );
  }

  Widget _box(Color color) => Container(
        width: widget.width,
        height: widget.height,
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(widget.radius),
        ),
      );
}
