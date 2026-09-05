# Shop

The shop is a static, general-purpose catalogue at `/{language}/shop`. It contains
13 catalogue cards, including configurable Škoda OHV and TAZ camshaft products.
No application framework, accounts, payment provider, server basket or new
dependencies were introduced.

## Editing the offer

Edit `shop/catalog.json`:

- `products`: stable ID, customer price in whole CZK, variants, photo path, and
  names/descriptions for the ten existing languages. Legacy dealer reference values
  in the source catalogue are not rendered or used in basket totals.
- `variants`: stable IDs and labels, with optional `price` / `priceType` overrides and localized
  labels in `translations`. By default, each variant becomes a radio-table option;
  a product with no variants still has one selectable option. `descriptions` adds
  a localized description row under a variant. For single-option items, the
  localized product `optionName` can differ from the card heading, and
  `optionDescription` adds a description below it.
  Variants may define `fields` with an ID and localized `labelKey`: these are
  required fields shown only for the selected variant. Types are `integer`
  (default, positive whole number), `decimal` (positive number), and `text`
  (with `maxLength` between 1 and 200). `minimumField` names another numeric
  field that supplies an inclusive lower bound.
  The rotor's custom variant uses `min-rpm` / `max-rpm`; its other variants have
  no extra fields. All three rotor options remain priced on request.
- `options`: optional groups containing a stable ID, translated name/description
  and `variantIds`. All variants must appear exactly once and variants in a group
  must share a price and price type. A group with multiple variants shows a required specification
  dropdown inside its selected subform. The current head gasket instead has four
  direct radio options: 80.5 mm (620 CZK), 82 mm (620 CZK), and stock TAZ 1.43
  with silicone treatment (160 CZK), and a quote-only custom option. The custom
  option requires cylinder spacing as text (for example `88-88-88`) and thickness
  as a positive decimal in millimetres. Its explicit `price: null` and
  `priceType: "quote"` override the product's fixed base price.
- `legacyItems`: explicit old-ID/variant mappings for merged products. The old
  160/156 mm connecting-rod cards map to `connecting-rod` variants at 12,500/11,500
  CZK; the old stock gasket maps to `head-gasket:stock`. The two coils map to
  `ignition-coil:contact` and `ignition-coil:contactless`; the four distributor
  components map to `distributor-parts` variants. These mappings preserve
  existing saved selections without trusting stored names or prices.
- `priceType`: `fixed`, `from`, `approx`, or `quote` for standard products. Use `null`
  for a quote-only price. The distributor overhaul is `approx` (around 1,600 CZK,
  depending on the work), not a fixed price or a minimum. Wizard products use
  `configured` with a null base price; each profile supplies its own price.
- `image`: a real `/assets/...` path or `null`. Existing workshop images are
  displayed without a caption. Products with `null` use the shared `placeholderImage`
  automatically; add their photo path when available to replace the placeholder.
  The distributor spare-parts collage uses `rozdelovace-01.jpeg`, the
  cylinder/piston kit uses `sada-valce-02.jpeg` first, then `sada-valce-01.jpeg`, and the
  carburetor uses `karburator.jpeg`. Only the copper rings still use a placeholder.
  The resonance exhaust uses `rezonancni-vyfuk-01.jpg` (renamed from
  `blog-article1-1.jpg` in the desktop, 1200 and 800 asset directories).
- `images`: optional ordered gallery entries with `src`, actual `width`/`height`,
  and `alt` text for each language. Keep `image` equal to the first gallery entry's
  `src`. Gallery photos share a fixed 16:9 frame with faded edges; thumbnails switch
  the selected photo. They open individually, uncropped, in the lightbox.
  Use a one-entry array for a single photo with explicit dimensions as well;
  only arrays with multiple images create the thumbnail gallery.
  Additional gallery images load lazily; visible captions are not added.
- `photoMaxHeight`: optional positive pixel height for a single-photo product with
  explicit image dimensions. The coil, rotor, distributor-parts collage and
  distributor overhaul use 360px previews. The whole frame scales proportionally
  and remains centered, without cropping, stretching or empty bars. Full-size
  lightbox images are unchanged; other products retain their existing sizing.
- `placeholderImage`: the shared generated image at
  `/assets/desktop/shop-placeholder.webp`. Its alt text identifies a missing product
  photo in each language, never actual product or workshop photography, and it is
  excluded from the image sitemap. The generation prompt is in
  `shop/placeholder-prompt.txt`.
- `copy`: original article wording and price-list notes. The source price list is
  dated 5 November 2025. The camshaft configurator has separate prices from the
  supplied CSV. The remaining product descriptions, options and prices were revised
  from the supplied Czech product list; the displayed price-list date is unchanged.
  The Ø82 mm kit's three prices are for a complete four-cylinder engine, not one cylinder.

IDs and variant IDs must remain stable across edits because saved baskets use
them. Removed products/variants without a `legacyItems` mapping are dropped on the
next page load. Prices always
come from the current page, never from browser storage. Dealer prices and minimums
are not displayed. Starting-price, approximate-price and quote-only products are excluded from
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

The catalogue always has one product per row. Every card uses the same photo-led
layout: left-aligned heading with the main team names' uppercase type and thin red
underline, photo/gallery, description, then an option table. Photo, text and table
share the same inner edges. Standard tables have an option column (44%) and a
right-aligned price column; like the camshaft tables, they have internal dividers
but no outer border. Every standard table retains both the option and price
headings, including single-option products. Selecting a radio moves one shared subform directly beneath
that option. Selecting it again hides the subform and clears validation warnings.
The radios are optional display controls, not required order fields.
The subform places labels in the first column and controls in the second: any
applicable specification dropdown, quantity, then the Add to order button. Quantity
uses the shared minus/input/plus spinner, compacted to the product form's 42px
control height. It is a draft value (1–9999), not a live basket control. Minus is
disabled at 1 and plus at 9999. Only pressing Add to order
adds that many units, accumulating units of the same variant in the order. A
submission that would exceed 9999 units of an option is rejected without a partial
add. Changing the selection moves the same fields and retains the quantity.
The Add to order button is also 42px high, matching the product form fields;
it has no glow or upward movement on hover. Its hover background lightens to the
same red as the basket's Order button, using a shared rule. The final checkout
button keeps its original main-page styling.
Specification dropdowns reuse the main form's pinned Choices.js component and
shared styling, retaining native selection if the CDN script is unavailable.
Text fields, textareas and quantity inputs also inherit the main page's field
families, control sizing and red focus border/glow from `main.css`. Product cards
use a scoped 14px (`.875rem`) Fira Code base: descriptions, field labels, inputs,
quantity buttons and native/enhanced dropdowns all follow that size. Prices and
supporting links use 13px, while small option labels and warnings stay at 12px.
The Chakra Petch product headings, form-section headings and submit text retain
their relative hierarchy at 1.8, 1.1 and 1.2 times the smaller base respectively.
The basket, final order form, blog
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

Product subforms and the final order form use `form.js` for inline validation on input/change and submission:
required fields, email and phone formats, warning borders/messages, and focus on
the first invalid field. Browser validation popups are disabled with `novalidate`.
Company, phone and notes remain optional in the shop; a supplied phone number is
checked with the same rule as the main form. The main form's year validation and
PHP submission remain intact. Error messages use the page's localized markup.
The release build minifies `form.js` alongside the page scripts and includes it
in the release root. It is served from the website, just like `index.js` and
`shop.js`; only catalogue imagery uses the jsDelivr asset reference.

Product photos precede the description. Photos reuse
the main equipment section's `.tech-frame` soft-edge shading, which clears on
hover or keyboard focus. Single-photo products keep their natural proportions,
scale down to fit the card's inner width and are horizontally centered. The frame
reserves the declared photo width before lazy loading, capped to the available
width, so it cannot collapse or introduce empty strips beside smaller images. Placeholder
images use the same sizing, without cropping. Camshaft, head-gasket and cylinder-kit galleries use fixed
landscape frames as described below. Product photos have no visible captions;
placeholders retain their descriptive alt text for accessibility.
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
bounded to 0–9999 (zero removes the line). Product subforms accept 1–9999 units per
add, subject to the same per-option limit in the order. Basket controls edit the
existing line directly; product form edits do not affect it. Clicking anywhere
inside a basket or product quantity input selects the entire number; keyboard focus does
the same. These delegated handlers also cover rows rebuilt after quantity edits.
Custom rotor and gasket rows additionally store sanitized `parameters`: respectively
`min-rpm` / `max-rpm` and `spacing` / `thickness`. Text is whitespace-normalized;
positive numbers are canonicalized (including decimal-comma values in restored data).
Each product/variant/specification combination is one order line: identical
specifications accumulate quantity; different specifications remain independently
editable/removable. Structured line keys preserve punctuation in free-text spacing.
All specifications appear in the order panel and email draft. Quote-only gasket
options never inherit the standard gasket price or contribute to the indicative total.
Legacy rotor rows without a variant cannot be mapped unambiguously; the page
asks the customer to select a new option and preserves their other order items.
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

`skoda-ohv-camshaft` and `taz-camshaft` use `kind: "wizard"`. Škoda OHV uses four supplied
photographs copied unchanged to `assets/desktop/skoda-ohv-1.jpeg` through
`skoda-ohv-4.jpeg`; TAZ uses three photographs, `assets/desktop/taz-01.jpeg` through
`taz-03.jpeg`. The images
appear in a gallery under a left-aligned, red-underlined heading. The main photo
and thumbnails align with the inner text and form edges, using the same responsive
side inset (28px on desktop, 18px on small screens).
Thumbnail buttons switch the large photo; clicking the large photo retains the
existing magnifier and fullscreen viewer. Without JavaScript, all linked photos
remain visible one below the other. Main gallery photos use a fixed 16:9 frame
with a center crop, so switching between landscape and portrait photos never
changes the gallery's height. Thumbnails also use a center crop. Enlarged photos
keep their original proportions and show the complete image.
The description follows the gallery, with an introductory paragraph,
side-by-side regrinding/manufacturing sections and installation instructions below.
These sections stack on small screens. The catalogue's `descriptionGroups` maps
the existing translated paragraphs into these sections without rewriting or
dropping their contents. Standard product cards use the same photo-led layout,
with their existing description paragraphs followed by a quantity-based option table.
The Škoda product has six
description paragraphs and six profiles; the TAZ product has four paragraphs and four
profiles. All content is translated for all ten languages. Profile duration, lift,
description and prices were imported from the supplied CSV files.
`shop/camshaft-options.csv` and `shop/taz-camshaft-options.csv` are normalized import
snapshots used by the regression tests; the editable runtime catalogue remains
`shop/catalog.json`. Update the applicable snapshot with the catalogue when intentionally
revising these specifications.

The form spans the card below the photo and description. It reuses the main form's
labels, text/number fields, submit button and `form.js` inline validation. Each
product's options form one optional native radio group in a compact table
with four shared column headings, internal row dividers and no outer border.
Each option has two rows in its first column:
radio button plus operation above, description below. Duration, lift and price each
span both rows and are vertically centered. All content is left-aligned except the
right-aligned price and its heading. Column widths are 44% / 20% / 20% / 16%, changing
to 40% / 20% / 20% / 20% on narrow screens to give prices more room. Every value
and description is a native label for its radio, preserving
click-to-select and keyboard behavior. Activating the selected radio again (or
one of its labels) clears the selection and hides the subform; engine values are
retained, while the conditional bearing selector is cleared and disabled.
The radios only control which subform is open: they have no `required` attribute,
validation class or shared yellow warning. With no selection, the add button is
disabled and submission is ignored. Closing the subform clears its warnings;
the visible engine fields and applicable bearing selector still validate normally.
Arrow-key navigation remains native. Cells wrap on small
screens rather than changing the two-row layout or shrinking the 14px body text.
The radio fieldset has a screen-reader legend but no visible inquiry subheading or
mandatory-fields note. In the Škoda configurator, choosing a new shaft reveals a
required bearing selector using the existing Choices component (with a native
fallback). Switching to a regrind hides, disables and clears that selector, without
clearing engine details. The TAZ configurator has no bearing selector. A single
shared group of field rows is hidden until an operation is selected, then moves
directly below that selected option inside the same table. Each row keeps its label
in the first column and lets its control span the remaining three columns. Changing
the selected operation moves the same controls, preserving their values and avoiding
duplicate form state. The add-to-order button occupies the group's final row,
spanning the last three columns below the inputs. Every displayed engine field is
required. Clicking anywhere in an engine text/number field or focusing it from the
keyboard selects its complete content, matching basket quantity inputs.
The Škoda configurator collects engine type,
bore, stroke, rocker ratio and both valve-head diameters. The TAZ configurator does
not ask for engine type or rocker ratio, and collects only bore, stroke and both
valve-head diameters. Numeric values accept positive decimals, with millimetres
displayed for dimensions. Diameter labels use words rather than the Ø symbol;
stored field IDs and units stay unchanged.

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

Reloading validates the profile, any product-specific conditional bearing, all required engine fields
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
