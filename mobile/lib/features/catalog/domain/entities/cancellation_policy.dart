/// Policy vocabulary, shared by cards, the property screen and checkout.
///
/// These strings are the terms a guest is agreeing to, so they live in one
/// place. The same policy described differently on the card and at checkout is
/// how a chargeback starts: "the listing said free cancellation".
library;

enum PolicyTone { positive, neutral, caution }

class PolicySummary {
  const PolicySummary({
    required this.label,
    required this.short,
    required this.detail,
    required this.tone,
  });

  final String label;
  final String short;
  final String detail;
  final PolicyTone tone;
}

const _policies = <String, PolicySummary>{
  'flexible': PolicySummary(
    label: 'Flexible',
    short: 'Free cancellation up to 24 h before check-in',
    detail:
        'Cancel up to 24 hours before check-in for a full refund. After that, the first night is charged.',
    tone: PolicyTone.positive,
  ),
  'moderate': PolicySummary(
    label: 'Moderate',
    short: 'Free cancellation up to 5 days before check-in',
    detail:
        'Cancel 5 days or more before check-in for a full refund. Between 5 days and 24 hours, 50% is refunded. Inside 24 hours, the stay is not refundable.',
    tone: PolicyTone.neutral,
  ),
  'strict': PolicySummary(
    label: 'Strict',
    short: 'Free cancellation up to 14 days before check-in',
    detail:
        'Cancel 14 days or more before check-in for a full refund. Between 14 and 7 days, 50% is refunded. Inside 7 days, the stay is not refundable.',
    tone: PolicyTone.caution,
  ),
  'non_refundable': PolicySummary(
    label: 'Non-refundable',
    short: 'This rate cannot be refunded',
    detail:
        'This rate is not refundable at any point. Taxes and any cleaning fee are still returned if you cancel, because neither was earned.',
    tone: PolicyTone.caution,
  ),
};

const _unknown = PolicySummary(
  label: 'Cancellation policy',
  short: 'See the property page for details',
  detail: 'The cancellation terms for this stay are shown before you pay.',
  tone: PolicyTone.neutral,
);

PolicySummary cancellationPolicy(String code) => _policies[code] ?? _unknown;

/// Stated because guests reliably ask, and because it is true regardless of
/// which policy applies to the room rate.
const refundFootnote =
    'Cleaning fees are always refunded in full, and tax is refunded in '
    'proportion to the amount returned.';
