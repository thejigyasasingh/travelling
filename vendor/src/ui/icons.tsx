import type { SVGProps } from 'react'

/**
 * The icon set.
 *
 * Hand-drawn rather than a dependency. Fifteen icons do not justify 200 kB of
 * library and a build-time tree-shaking question, and drawing them on one grid
 * with one stroke weight is what makes them look like a set instead of a
 * collection — which is most of what "polished" means in a sidebar.
 *
 * Rules every icon here follows:
 *
 * * **24×24 grid, 1.75 stroke, round caps and joins.** One weight throughout.
 *   Mixing 1.5 and 2 across a nav list is visible even when nobody can say why.
 * * **`currentColor`, never a fixed fill.** An icon inherits its parent's
 *   colour, so an active nav item tints its icon for free and a disabled button
 *   dims one.
 * * **`aria-hidden`.** Every icon here sits beside a text label. Announcing it
 *   to a screen reader repeats the label; hiding it is the accessible choice,
 *   not the lazy one.
 * * **`size-*` from the caller.** The default is `size-5`; a caller overriding
 *   it gets a shape that still aligns, because the geometry is on one grid.
 */
type IconProps = SVGProps<SVGSVGElement> & { className?: string }

function Icon({ className = 'size-5', children, ...rest }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  )
}

// ── navigation ────────────────────────────────────────────────────────────

export const HomeIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 10.5 12 3l9 7.5" />
    <path d="M5 9.5V20a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9.5" />
    <path d="M9.5 21v-6h5v6" />
  </Icon>
)

export const BuildingIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 21V6a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v15" />
    <path d="M14 10h5a1 1 0 0 1 1 1v10" />
    <path d="M3 21h18" />
    <path d="M7.5 9h3M7.5 13h3M7.5 17h3M17 14v3" />
  </Icon>
)

export const CalendarIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M3 10h18M8 3v4M16 3v4" />
    <path d="M7.5 14h2M11 14h2M14.5 14h2M7.5 17.5h2M11 17.5h2" />
  </Icon>
)

export const InboxIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 13h4l1.5 3h7L17 13h4" />
    <path d="M5.5 5h13l2.5 8v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-5Z" />
  </Icon>
)

export const StarIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m12 3.5 2.6 5.4 5.9.8-4.3 4.1 1.1 5.9-5.3-2.9-5.3 2.9 1.1-5.9L3.5 9.7l5.9-.8Z" />
  </Icon>
)

export const WalletIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H18a1 1 0 0 1 1 1v2" />
    <path d="M3 7.5V18a2 2 0 0 0 2 2h14a1 1 0 0 0 1-1v-9a1 1 0 0 0-1-1H5.5A2.5 2.5 0 0 1 3 7.5Z" />
    <circle cx="16" cy="14" r="1.15" fill="currentColor" stroke="none" />
  </Icon>
)

export const ReportIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z" />
    <path d="M14 3v5h5" />
    <path d="M9 13h6M9 16.5h4" />
  </Icon>
)

// ── overview tiles ────────────────────────────────────────────────────────

export const BellIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M18 9a6 6 0 1 0-12 0c0 5-2 6.5-2 6.5h16S18 14 18 9Z" />
    <path d="M13.7 19a2 2 0 0 1-3.4 0" />
  </Icon>
)

export const PlaneIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M10.2 12.6 3 10.4l1.6-1.6 3.2.6 2.6-2.6-6.3-3 2-2 8 2.2 3.1-3.1a2 2 0 0 1 2.8 2.8l-3.1 3.1L19.1 15l-2 2-3-6.3-2.6 2.6.6 3.2-1.6 1.6Z" />
  </Icon>
)

export const KeyIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="8" cy="12" r="4" />
    <path d="M12 12h9M18 12v3M15.5 12v2.5" />
  </Icon>
)

// ── state ─────────────────────────────────────────────────────────────────

export const CheckIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m5 12.5 4.5 4.5L19 7" />
  </Icon>
)

export const AlertIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 4.5 2.8 20h18.4Z" />
    <path d="M12 10v4M12 17h.01" />
  </Icon>
)

export const TrendUpIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m3 16 5.5-5.5 3.5 3.5L21 5" />
    <path d="M15 5h6v6" />
  </Icon>
)

export const SearchEmptyIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.6-3.6" />
    <path d="M8.5 11h5" />
  </Icon>
)

export const ArrowRightIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 12h15M13 6l6 6-6 6" />
  </Icon>
)

export const SignOutIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M9 21H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3" />
    <path d="M15.5 16.5 20 12l-4.5-4.5M20 12H9" />
  </Icon>
)
