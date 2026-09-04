# Shop

The shop is a static, general-purpose catalogue at `/{language}/shop`. Its first
17 products were migrated from the TAZ blog article; the two camshaft cards now
form one configurable Škoda OHV product, leaving 16 catalogue cards. No application framework,
accounts, payment provider, server basket or new dependencies were introduced.

## Editing the offer

Edit `shop/catalog.json`:

- `products`: stable ID, retail price in whole CZK, dealer price/minimum, variants,
  photo path, and names/descriptions for the ten existing languages.
- `priceType`: `fixed`, `from`, or `quote` for standard products. Use `null` for a
  quote-only price. Wizard products use `configured` with a null base price; each
  profile supplies its own price.
- `image`: a real `/assets/...` path or `null`. Existing workshop images are
  displayed without a caption. Products with `null` use the shared `placeholderImage`
  automatically; add their photo path when available to replace the placeholder.
- `images`: optional ordered gallery entries with `src`, actual `width`/`height`,
  and `alt` text for each language. Keep `image` equal to the first gallery entry's
  `src`. All gallery photos stack vertically in the existing image column, keep
  their natural proportions and faded edges, and open individually in the lightbox.
  Additional gallery images load lazily; visible captions are not added.
- `placeholderImage`: the shared generated image at
  `/assets/desktop/shop-placeholder.webp`. Its alt text identifies a missing product
  photo in each language, never actual product or workshop photography, and it is
  excluded from the image sitemap. The generation prompt is in
  `shop/placeholder-prompt.txt`.
- `copy`: original article wording and price-list notes. The source price list is
  dated 5 November 2025. The camshaft configurator has separate prices from the
  supplied CSV; other products and the displayed price-list date are unchanged.

IDs and variant IDs must remain stable across edits because saved baskets use
them. Removed products/variants are dropped on the next page load. Prices always
come from the current page, never from browser storage. Dealer discounts are not
applied automatically. Starting-price and quote-only products are excluded from
the fixed-price subtotal; delivery is explicitly unpriced.

The template and UI text live in `shop/page.html` and `shop/translations.json`.
Generated `cs/shop.html`, `en/shop.html`, etc. are committed-style static source
pages, like the rest of this repository. Do not edit them directly.

The generator reuses each language's blog navigation and footer, marking the shop
as active and keeping language switches on the shop route. The shop loads the
existing `main.css` and `blog.css` for its background image, typography, panels,
image frames and mobile header. The basket reuses the blog's `.toc-wrapper`
appearance in the same 280px desktop sidebar, but uses `position: sticky` within
the content grid. The sidebar spans the catalogue and order section, so the basket
follows page scrolling and stops above the footer. The blog's table of contents
is unchanged. Only the basket's item list scrolls; the heading,
indicative price, delivery notices and order button stay visible. Quantity edits
preserve the list's scroll position. Below the blog's 1400px breakpoint it stays
inline between the catalogue and order form, with normal page scrolling.

The catalogue always has one product per row. Each card has an image-only left
column and a right column containing a centered heading, justified description,
prices and quantity controls. CSS Grid places the heading in its own right-column
row, with the photo and description starting together in the row beneath it.
Headings match the main team names' uppercase type
and thin red underline. Prices and quantity use spacing only, without separator lines.
At 680px and below the card stacks as heading, photo, then description/prices/quantity.
Specifications, when offered, appear directly above the quantity controls.
Specification dropdowns reuse the main form's pinned Choices.js component and
shared styling, retaining native selection if the CDN script is unavailable.
Text fields, textareas and quantity inputs also inherit the main page's field
families, control sizing and red focus border/glow from `main.css`. Product cards
use a scoped 14px (`.875rem`) Fira Code base: descriptions, field labels, inputs,
quantity buttons and native/enhanced dropdowns all follow that size. Prices and
supporting links use 13px, while small option labels and warnings stay at 12px.
The Chakra Petch product headings, form-section headings and submit text retain
their relative hierarchy at 1.8, 1.1 and 1.2 times the smaller base respectively.
Control heights and spacing are unchanged. The basket, final order form, blog
and main page retain their original typography. Keep font-family resets and
white focus outlines off these fields and the Choices controls;
other keyboard-operated controls still have a visible focus outline.
The order section uses the main page's `.section`, `.contact-intro` and
`.contact-sub-1` styling: a separate centered heading and explanation above one
`.terminal-form` panel, without an enclosing blog card. Its required-field note
matches the corresponding main-page language; optional fields remain optional
without an extra label suffix.
The entire order form reuses `main.css` directly, including its actual
`h4.form-section-title` headings, label weights, paragraph spacing, disclaimer
color/size and submit button. Do not add shop-specific typography or padding
overrides to these components. The contact heading and validation messages are
read from each language's main form when generating the shop.

Both forms use `form.js` for inline validation on input/change and submission:
required fields, email and phone formats, warning borders/messages, and focus on
the first invalid field. Browser validation popups are disabled with `novalidate`.
Company, phone and notes remain optional in the shop; a supplied phone number is
checked with the same rule as the main form. The main form's year validation and
PHP submission remain intact. Error messages use the page's localized markup.
The release build minifies `form.js` alongside the page scripts and includes it
in the release root. It is served from the website, just like `index.js` and
`shop.js`; only catalogue imagery uses the jsDelivr asset reference.

Photos align with the top of the product description. Their thumbnails reuse
the main equipment section's `.tech-frame` soft-edge shading, which clears on
hover or keyboard focus. Images keep their natural proportions, scale down to fit
the image column and are horizontally centered; the frame follows the image instead
of forcing a 4:3 box with black bands. Placeholder images use the same sizing,
without cropping. Product photos have no visible captions; placeholders retain
their descriptive alt text for accessibility.
The zoom cursor and lightbox remain unchanged, and enlarged images are unshaded.
Click or press Enter on a photo to enlarge it; click the overlay, use its close
button or press Escape to close it. Focus returns to the photo, and image links
work without JavaScript.
Mouse/touch photo interactions suppress focus outlines, including when Escape
closes the viewer. Escape preserves the current input mode; Tab navigation and
keyboard activation retain visible focus. Restored pointer focus also preserves
the faded edges instead of leaving the thumbnail's shading cleared. Actual hover
and keyboard focus still reveal the photo normally.

Regenerate after any catalogue, template, JavaScript or CSS edit:

```sh
.venv/bin/python build_shop.py
```

`release.py` runs this automatically. The existing two release arguments retain
their meanings. The release includes the shop stylesheet, script, HTML pages,
sitemap entries and Apache extensionless route. Release navigation links to the
main, blog and shop pages all receive the site-version query parameter, including
extensionless, trailing-slash and `.html` URLs. Existing query parameters and
section anchors are preserved. Canonical/hreflang links and sitemap URLs stay
unversioned; JS/CSS continue to use their separate source-content hashes.

When releasing with a jsDelivr asset ref such as `main`, publish changed image
assets to that ref as well. Uploading the release does not update repository images
served by jsDelivr. The shop's CSS and JavaScript are served from the release folder
on the site's own origin, using content hashes in their URLs.

## Basket and checkout

For standard products, `shop.js` stores `{version: 1, items: [{id, variant, quantity}]}` in localStorage
under `muckova-shop-basket`, shared across languages on the same origin. Storage
failure falls back to memory, tabs listen for storage changes, and quantities are
bounded to 0–9999 (zero removes the line). The same limit applies to product-card
controls, basket controls, saved selections and order totals. Clicking anywhere
inside a basket quantity input selects the entire number; keyboard focus does
the same. These delegated handlers also cover rows rebuilt after quantity edits.
Configured products also store a unique `lineId` and the validated `configuration`
described below, with an implicit quantity of one and no quantity controls.
No contact details, address or draft email are stored by the site.
Company and phone are optional fields included in the prepared email only when
filled in. Street and house number remain required; the former address-extra
field is no longer collected. Delivery and notes headings share the main form's
section-title styling while preserving the delivery fieldset and legend.

Checkout currently prepares an **email enquiry**, not a submitted/confirmed order.
The customer reviews the draft and sends it from their email application to
`info@petramuckova.cz`, or copies the text into webmail. It does not reuse the
existing PHP contact handler: that handler's implementation is absent from this
repository. No network submission, payment, availability guarantee, shipping tariff
or binding checkout terms are invented. Changing the basket or form invalidates
the prepared draft. Preparing an email never clears the basket.

Postal delivery is represented as:

```js
{ email, phone, delivery: { method: 'postal', address: { fullName, company, street, city, postcode, country } }, notes }
```

Future delivery methods should define their own method identifier and required
fields. If a server order endpoint is added, it must independently validate IDs,
variants, quantities, prices, delivery costs and customer data; client totals are
not an authority for charging or fulfillment. Confirm actual delivery, payment and
customer-facing terms before enabling direct orders.

## Configured camshaft items

`skoda-ohv-camshaft` uses `kind: "wizard"` and the four supplied photographs,
copied unchanged to `assets/desktop/skoda-ohv-1.jpeg` through `skoda-ohv-4.jpeg`.
They appear in that order, one below the other, in the photo column.
Its six paragraph descriptions and six profiles are translated for all ten languages.
The profile duration, lift, description and prices were imported from the supplied
`aaa.csv`. `shop/camshaft-options.csv` is a normalized import snapshot used by the
regression tests; the editable runtime catalogue remains `shop/catalog.json`.
Update that snapshot with the catalogue when intentionally revising these specifications.

The form spans the card below the photo and description. It reuses the main form's
labels, text/number fields, section headings, submit button and `form.js` inline
validation. The six options form one required native radio group in a compact table
with four shared column headings. Each option has two rows in its first column:
radio button plus operation above, description below. Duration, lift and price each
span both rows and are vertically centered. All content is left-aligned except the
right-aligned price and its heading. Column widths are 44% / 20% / 20% / 16%, changing
to 40% / 20% / 20% / 20% on narrow screens to give prices more room. Every value
and description is a native label for its radio, preserving
click-to-select and keyboard behavior without extra JavaScript. Cells wrap on small
screens rather than changing the two-row layout or shrinking the 14px body text.
The table is introduced by a localized “Poptávka” heading using the same
`form-section-title` treatment as the engine-details heading. The heading also
labels the radio fieldset for assistive technology; no mandatory-fields note is
shown here. Choosing a new shaft reveals a required bearing selector
using the existing Choices component (with a native fallback). Switching to a
regrind hides, disables and clears that selector, without clearing engine details.
All six engine fields are required; numeric dimensions and rocker ratio accept
positive decimals, with millimetres displayed for dimensions only.
The rows pair engine type with bore, stroke with rocker ratio, and exhaust-valve
head diameter with intake-valve head diameter. Diameter labels use words rather
than the Ø symbol; stored field IDs and units stay unchanged.

Each submission adds a separate configured unit, including identical submissions.
Its basket entry has the usual remove cross, full configuration and profile price,
but no quantity field or plus/minus controls. The same details are included in the
order email. Form submission only adds to the local basket; it does not send an order.
The form stays filled to allow another configuration without re-entering engine data.

Stored configured rows have this shape (no labels or prices are persisted):

```js
{ id: 'skoda-ohv-camshaft', variant: '', quantity: 1, lineId: 'unique-instance-id',
  configuration: { profile: 'new-294-294', bearing: 'small', values: {
    engineType: 'Škoda 136', bore: '75.5', stroke: '72',
    intakeValve: '34', exhaustValve: '30', rockerRatio: '1.45'
  } } }
```

Reloading validates the profile, conditional bearing, all required engine fields
and instance ID against the current catalogue. Totals use the current profile
price, never a stored price. Standard version-1 baskets remain compatible. Legacy
`camshaft-regrind` / `camshaft-new` selections cannot be mapped to a profile safely:
they are removed with a notice asking for reconfiguration; other selections remain.
The basket supports up to 500 distinct lines. Adding beyond that shows a message
and leaves the existing basket intact. Stored configuration is a product selection;
customer contact and delivery fields remain excluded from browser storage.

## Checks

Use Node through NVM if it is not on PATH, and the project's Python environment:

```sh
node --test tests/*.test.js
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python tests/smoke_release.py
```
