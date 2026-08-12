# Roaming & Wandering — Flutter app

Flutter 3.41 · Riverpod · Dio · GoRouter · Freezed · JsonSerializable

The guest-facing mobile app: search, property details, booking, checkout,
trips, wishlist and account. It talks to the API in `../backend` and holds no
business rules of its own beyond presentation.

```bash
flutter pub get
dart run build_runner build          # Freezed, JsonSerializable, Riverpod
flutter analyze && flutter test      # the gate

# Against a local backend. `adb reverse` is more reliable than the emulator's
# 10.0.2.2 NAT, which silently swallowed requests on this machine.
adb reverse tcp:8000 tcp:8000
flutter run --dart-define=API_BASE_URL=http://localhost:8000/api/v1
```

---

## Layout

The dependency rule points inward. `presentation` may import `domain` and
`data`; `domain` imports neither Flutter nor Dio; `core` is shared by all.

```
lib/
├── core/
│   ├── config/      Build-time configuration, from --dart-define
│   ├── error/       The Failure union — every way a request can fail
│   ├── network/     Dio client, auth interceptor, Result, connectivity
│   ├── storage/     Keychain-backed tokens, Hive-backed response cache
│   ├── providers/   The composition root
│   ├── router/      GoRouter, with the auth redirect
│   ├── theme/       Material 3 from one seed colour
│   └── utils/       Money (minor units), dates (half-open stays)
├── features/<feature>/
│   ├── data/        DTOs (freezed + json), data sources, repositories
│   ├── domain/      Entities, value objects, use cases
│   └── presentation/ Providers, screens, widgets
└── shared/          PagedState and the widgets every screen needs
```

**DTOs stop at `data/`.** They are `snake_case` mirrors of the wire format,
verified against a running server rather than read off a schema — see the live
contract tests below for why that distinction earns its keep.

---

## The decisions that matter

**One refresh, however many 401s.** A screen fires several requests at once; if
the token has expired they all get 401 together. The backend *rotates* refresh
tokens and treats reuse as theft — it revokes the whole family and signs the
user out of every device. So `AuthInterceptor` shares a single in-flight
`Completer` and everyone retries once behind it. Concurrent refreshes would not
merely waste requests; they would log the user out. Pinned by
`test/core/auth_interceptor_test.dart`.

**Tokens live in the Keychain / EncryptedSharedPreferences, not
`SharedPreferences`.** The access token is additionally held in memory so the
interceptor never awaits platform storage per request.

**Money is integer minor units end to end.** Paise, never rupees, until the
moment a string is rendered. A `double` for money is a total that disagrees
with the invoice.

**Stay dates are half-open.** `[checkIn, checkOut)` — 12th→14th is two nights
and the 14th is free for the next guest. Dates travel as `yyyy-MM-dd` strings,
never `DateTime`s silently shifted by a timezone, and are advanced by
constructing a date rather than adding 24 hours, so a DST transition cannot
drop a night.

**Prices come from the server, always.** The booking panel asks for a quote and
waits. Nightly rates vary by date, weekends have multipliers, tax is slabbed —
computing it here would produce a number the server rejects with a 409 at
checkout.

**The idempotency key is minted when the booking form opens, not per tap.** A
double-tapped "Reserve" is a second room held on real inventory.

**The client never decides that a payment succeeded.** Only the server, which
holds the gateway secret, can verify a signature. And if verification fails
*after* the money moved, the webhook still confirms the booking — so the guest
is sent to their trip, which polls, rather than being invited to pay twice.

**`PagedState` is not `AsyncValue<List<T>>`.** A paged list has states that type
cannot express and a user can plainly see: items *and* a spinner, items *and* a
page error, items that are stale from cache. Collapsing them is what produces a
list that blanks itself when page four fails.

**Infinite scroll fires from a scroll extent, not a sentinel widget.** A
"load more" marker only fires once it is built, which on a fast fling is already
too late. The guard lives in the notifier, so the widget can call `loadMore` on
every frame.

---

## Offline

Caching policy is chosen per resource, because the cost of staleness differs:

| Resource | Policy | Why |
| --- | --- | --- |
| Amenities | Cache-first, 1 day | A reference list. The filter sheet must open instantly. |
| Search (first page only) | Network-first, cache as fallback | Prices go stale in minutes. Later pages are never cached — a cursor is meaningless without its query. |
| Property detail | Network-first, 1 h fallback | Keeps the address and check-in time when the lift has no signal. |
| Bookings | Network-first, cached generously | A guest at a reception desk with no signal still needs their reference. |
| Quotes, refund previews | Never cached | Both are time-sensitive by construction. |

Stale content is shown **with a banner saying so**, never silently. Showing
saved prices as though they were live is how a guest reaches checkout to a
different number.

---

## Not included

**Razorpay's SDK is not bundled.** It needs a native dependency and a merchant
account. `CheckoutScreen` is real up to the point the sheet would open —
order creation, the hold countdown, verification and every error path talk to
the API; the gateway call itself is a clearly-marked placeholder.

**The wishlist is device-local.** The backend has no wishlist endpoint yet, so
saved stays live in the same Hive box as the cache. It does not follow the guest
to another device, and the screen says so.

---

## Testing

```bash
flutter test                    # unit + widget
flutter test --tags live        # also parses live API responses (needs the backend)
```

The `live` suite parses **real** responses through the app's real DTOs and skips
itself when nothing is listening. It exists because a sibling client was written
from a schema listing and silently mis-parsed `/auth/refresh` — a bug no unit
test could see, because the fixtures were wrong in the same way the code was.

---

## Android notes

Two things in `android/app/src/main/AndroidManifest.xml` are load-bearing and
were both found by running a release build rather than a debug one:

* **`INTERNET` is declared in the main manifest.** Flutter only puts it in the
  *debug* manifest, so an app that works throughout development ships with no
  network at all, failing as though the device were offline.
* **Cleartext HTTP is permitted for loopback only**, via
  `network_security_config.xml`. `usesCleartextTraffic="true"` would allow
  plaintext to every host including production; the config allows it for
  `10.0.2.2`, `localhost` and `127.0.0.1`, none of which are reachable from a
  real network.

`compileSdk`/`targetSdk` are pinned to 36 rather than tracking Flutter's
default, which resolves to a platform this SDK installs as `android-37.0` and
Gradle then fails to find as `android-37`.
