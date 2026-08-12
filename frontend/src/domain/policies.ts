/**
 * Policy vocabulary shared by search cards, the property page and checkout.
 *
 * These strings are business rules the guest is agreeing to, so they live in
 * one place. The same words appearing differently on the card and at checkout
 * is how a chargeback starts: "the listing said free cancellation".
 */

export interface PolicySummary {
  readonly label: string
  readonly short: string
  readonly detail: string
  readonly tone: 'positive' | 'neutral' | 'caution'
}

const POLICIES: Record<string, PolicySummary> = {
  flexible: {
    label: 'Flexible',
    short: 'Free cancellation up to 24 h before check-in',
    detail:
      'Cancel up to 24 hours before check-in for a full refund. After that, the first night is charged.',
    tone: 'positive',
  },
  moderate: {
    label: 'Moderate',
    short: 'Free cancellation up to 5 days before check-in',
    detail:
      'Cancel 5 days or more before check-in for a full refund. Between 5 days and 24 hours, 50% is refunded. Inside 24 hours, the stay is not refundable.',
    tone: 'neutral',
  },
  strict: {
    label: 'Strict',
    short: 'Free cancellation up to 14 days before check-in',
    detail:
      'Cancel 14 days or more before check-in for a full refund. Between 14 and 7 days, 50% is refunded. Inside 7 days, the stay is not refundable.',
    tone: 'caution',
  },
  non_refundable: {
    label: 'Non-refundable',
    short: 'This rate cannot be refunded',
    detail:
      'This rate is not refundable at any point. Taxes and any cleaning fee are still returned if you cancel, because neither was earned.',
    tone: 'caution',
  },
}

const UNKNOWN: PolicySummary = {
  label: 'Cancellation policy',
  short: 'See the property page for details',
  detail: 'The cancellation terms for this stay are shown before you pay.',
  tone: 'neutral',
}

export function cancellationPolicy(code: string): PolicySummary {
  return POLICIES[code] ?? UNKNOWN
}

/**
 * The cleaning fee and tax always come back in full, whatever the policy says
 * about the room rate — nothing was cleaned, and tax on money not kept was
 * never owed. Stated here because guests reliably ask.
 */
export const REFUND_FOOTNOTE =
  'Cleaning fees are always refunded in full, and tax is refunded in proportion to the amount returned.'
