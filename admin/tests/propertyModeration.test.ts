/**
 * Which moderation actions a listing in each status will actually accept.
 *
 * This mirrors the domain's transition table on the server, and the mirror is
 * the risk: a button the server refuses is worse than a missing one. The admin
 * presses it, reads a transition error, and stops trusting the other buttons —
 * at which point they go and ask engineering to change the row directly.
 *
 * So every status the backend defines is pinned here, including the ones where
 * the answer is "nothing".
 */

import { describe, expect, it } from 'vitest'
import { moderationActions, toListQuery } from '@/pages/PropertiesPage'

/** `PropertyStatus` on the server, in full. */
const ALL_STATUSES = [
  'draft',
  'pending_review',
  'published',
  'unpublished',
  'rejected',
  'suspended',
] as const

describe('moderationActions', () => {
  it('offers approve and reject only from the review queue', () => {
    /**
     * `pending_review → published | rejected` is the only transition the
     * review endpoint can make. Approving anything else is a 409.
     */
    expect(moderationActions('pending_review')).toEqual({
      approve: true,
      reject: true,
      suspend: false,
    })

    for (const status of ALL_STATUSES.filter((s) => s !== 'pending_review')) {
      expect(moderationActions(status).approve).toBe(false)
      expect(moderationActions(status).reject).toBe(false)
    }
  })

  it('offers suspend from both states a listing can be suspended from', () => {
    /**
     * `published` is the obvious one. `unpublished` is the one that gets
     * missed: a vendor who unpublishes a listing under investigation has not
     * put it beyond reach, and if the panel hid suspend here the only way to
     * stop them republishing would be a database edit.
     */
    expect(moderationActions('published').suspend).toBe(true)
    expect(moderationActions('unpublished').suspend).toBe(true)
  })

  it('does not offer suspend where the transition table refuses it', () => {
    expect(moderationActions('draft').suspend).toBe(false)
    expect(moderationActions('rejected').suspend).toBe(false)
    // Already suspended: `suspended → unpublished` is the only way out, and no
    // admin route exposes it, so there is nothing to offer.
    expect(moderationActions('suspended').suspend).toBe(false)
  })

  it('offers nothing on a draft', () => {
    /** Not submitted. Acting on it would review work the vendor has not
     *  finished — and `draft → published` is not a transition at all. */
    expect(moderationActions('draft')).toEqual({
      approve: false,
      reject: false,
      suspend: false,
    })
  })

  it('offers nothing on a status it does not recognise', () => {
    /**
     * A status this build has never heard of means the server is ahead of the
     * panel. Guessing an action from an unknown state is how an admin
     * unpublishes something the new state was meant to protect.
     */
    expect(moderationActions('awaiting_kyc')).toEqual({
      approve: false,
      reject: false,
      suspend: false,
    })
    expect(moderationActions('')).toEqual({
      approve: false,
      reject: false,
      suspend: false,
    })
  })

  it('never offers approve and suspend on the same listing', () => {
    /** They are opposite decisions. A screen showing both is one where the
     *  reviewer has to work out which state they are even looking at. */
    for (const status of ALL_STATUSES) {
      const actions = moderationActions(status)
      expect(actions.approve && actions.suspend).toBe(false)
    }
  })
})

describe('toListQuery', () => {
  /**
   * The page defaults to the review queue, so an absent `status` means
   * "pending_review", not "everything". That makes "All" a value the URL has
   * to carry — and one the API must never see, because the server would match
   * it against nothing and hand back an empty queue that looks like good news.
   */

  it('drops the all-statuses sentinel before it reaches the API', () => {
    expect(toListQuery({ status: 'any', page: 1 })).toEqual({ page: 1 })
    expect('status' in toListQuery({ status: 'any' })).toBe(false)
  })

  it('passes a real status through untouched', () => {
    const filters = { status: 'pending_review', page: 2, size: 20 }
    expect(toListQuery(filters)).toEqual(filters)
  })

  it('leaves filters with no status alone', () => {
    expect(toListQuery({ q: 'goa', page: 1 })).toEqual({ q: 'goa', page: 1 })
  })

  it('keeps every other filter when it drops the sentinel', () => {
    /** Clearing the status filter must not also clear the search someone
     *  typed, or the page they are on. */
    expect(toListQuery({ status: 'any', q: 'goa', page: 3, size: 50 })).toEqual({
      q: 'goa',
      page: 3,
      size: 50,
    })
  })

  it('does not mutate the filters it is given', () => {
    /** They come from the URL and are shared with the `Select` that renders
     *  the current choice; mutating them would blank the dropdown. */
    const filters = { status: 'any', page: 1 }
    toListQuery(filters)
    expect(filters.status).toBe('any')
  })
})
