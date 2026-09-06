# Shop

The shop is a static, general-purpose catalogue at `/{language}/shop`. It contains
13 catalogue cards, including configurable Škoda OHV and TAZ camshaft products.
No application framework, accounts, payment provider or server basket is used.
The final order form submits to PHP using the contact form's existing server-side
PHPMailer installation and SMTP account.

## Editing the offer

Edit `shop/catalog.json`:

- `products`: stable ID, customer price in whole CZK, variants, photo path, and
  names/descriptions for the ten existing languages. Legacy dealer reference values
  in the source catalogue are not rendered or used in basket totals.
- `category`: `camshafts`, `exhaust`, `engineParts`, `ignition`, or `fuel`.
  Its localized label is the first blog-style tag. `tags` supplies additional
  language-neutral model, brand or specification tags. These presentation fields
  do not enter the order data or change the backend catalogue version.
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
  displayed without a caption. Products with `null` or no image path render no
  image markup or reserved photo space; add their photo path when available.
  Product assets use the supplied optimized `eshop-*` filenames in `assets/desktop`;
  preserve their supplied bytes and record their actual dimensions below.
  The distributor spare-parts collage uses `eshop-rozdelovac-nd-01.jpg`, the
  cylinder/piston kit uses `eshop-valce-sada-01.jpg` first (the complete kit), then
  `eshop-valce-sada-02.jpg`, and the carburetor uses `eshop-karburator-01.webp`.
  The resonance exhaust uses `eshop-rezonancni-vyfuk-01.jpg`.
  The copper rings currently have no photo. The supplied `eshop-placeholder.webp`
  is retained as an unused asset; it is not a fallback and is not indexed in the sitemap.
- `images`: optional ordered gallery entries with `src`, actual `width`/`height`,
  and `alt` text for each language. Keep `image` equal to the first gallery entry's
  `src`. Gallery photos share a fixed 16:9 viewport inside the blog's red-corner frame; thumbnails switch
  the selected photo. They open individually, uncropped, in the lightbox.
  Use a one-entry array for a single photo with explicit dimensions as well;
  only arrays with multiple images create the thumbnail gallery.
  Additional gallery images load lazily; visible captions are not added.
- `photoMaxHeight`: optional positive pixel height for a single-photo product with
  explicit image dimensions. The rotor, distributor-parts collage and
  distributor overhaul use 360px previews. The whole frame scales proportionally
  and remains centered, without cropping, stretching or empty bars. Full-size
  lightbox images are unchanged; other products retain their existing sizing.
- `photoMaxWidth`: optional positive pixel width for a single-photo product with
  explicit image dimensions. The resonance exhaust and coil use 435px previews,
  matching the tuned manifold photo. Height scales automatically with the original
  aspect ratio. The supplied replacement coil photo is `eshop-zapalovaci-civka-01.jpg`.
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
image frames and mobile header. A product table of contents sits above the basket
in the same 280px desktop sidebar. Its title uses the shop's localized
`contentsTitle` ("NABÍDKA" in Czech), and its numbered links are generated from
the product names and IDs. It reuses
the blog's `.toc-wrapper`, `.toc-title`, `.toc-nav` and `.toc-link` styles, including
the active product indicator while scrolling. The contents list scrolls separately.
Both panels stick together within the content grid when the viewport has enough
room for readable lists and the fixed order summary. On shorter screens the contents
scroll away before the basket sticks; if the basket summary itself cannot fit,
it stays in normal page flow. The sidebar spans the catalogue and order section,
so neither panel overlaps the footer. The blog's table of contents is unchanged.
Only the basket's item list scrolls inside its panel; the heading,
indicative price and order button stay visible. The information icon to the right
of the indicative-price label reveals the delivery notice and, when applicable,
the quote/starting/approximate-price notice. It opens on hover, keyboard focus or
click/tap; a click pins it open. Escape, clicking outside, or clicking the icon
again closes it. The popover lives outside the clipped basket and stays within
the viewport without changing the sidebar layout. Quantity edits
preserve the list's scroll position. Below the blog's 1400px breakpoint it stays
inline between the catalogue and order form, with normal page scrolling.

The catalogue always has one product per row. Every card reuses the blog's
`.blog-card`, `.article-header`, `.meta-tags`, `.article-title`, `.lead` and
`.tech-divider` components. Existing introductory copy becomes the lead; products
with no description omit it rather than inventing a subheading. The photo/gallery
and remaining description use `.article-body`, followed by the unchanged option
form as a sibling, outside the article body. This prevents blog table styles from
affecting the ordering controls. Card padding and heading/lead typography follow
the blog's desktop and mobile rules. Standard tables have an option column (44%) and a
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
families, control sizing and red focus border/glow from `main.css`. Product ordering
tables retain a scoped 14px (`.875rem`) Fira Code base, including their inputs,
quantity buttons and native/enhanced dropdowns. Secondary field labels use 13px,
and small option labels and warnings stay at 12px. Submit text uses 1.2 times the
base (the base size on small screens). Product headings, leads and descriptive
body text instead inherit the blog's responsive typography directly.
The basket, final order form, blog
and main page retain their original typography. Keep font-family resets and
white focus outlines off these fields and the Choices controls;
other keyboard-operated controls still have a visible focus outline.
The order section uses the main page's `.section` and `.contact-intro` styling:
a separate centered heading above one `.terminal-form` panel, without a subheading
or an enclosing blog card. Its required-field note
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

Product photos follow the header lead and precede the detailed description. Photos
reuse the blog's `.blog-figure`, `.blog-img-frame` red corners and `.blog-img`
border, without the former equipment-section fade overlay. Single-photo products keep their natural proportions,
scale down to fit the card's inner width and are horizontally centered. The frame
reserves the declared photo width before lazy loading, capped to the available
width, so it cannot collapse or introduce empty strips beside smaller images.
Camshaft, head-gasket and cylinder-kit galleries use fixed landscape frames as
described below. Product photos have no visible captions. Products without photos
omit the photo row entirely, leaving the heading, available description and order form.
The zoom cursor and lightbox remain unchanged, and enlarged images are unshaded.
Click or press Enter on a photo to enlarge it; click the overlay, use its close
button or press Escape to close it. Focus returns to the photo, and image links
work without JavaScript.
Mouse/touch photo interactions suppress focus outlines, including when Escape
closes the viewer. Escape preserves the current input mode; Tab navigation and
keyboard activation retain visible focus. The decorative blog frame remains
visible after the viewer closes; hovering animates its red corners as on the blog.

Regenerate after any catalogue, template, JavaScript or CSS edit:

```sh
.venv/bin/python build_shop.py
```

`release.py` runs the frontend-only build automatically, without generating or
changing `backend/order_catalog.php`. For the same page-only build, use
`.venv/bin/python build_shop.py --frontend-only`.
The existing two release arguments retain
their meanings. The release includes the shop stylesheet, script, HTML pages,
sitemap entries and assets, but no backend or server configuration. Apache
extensionless routes, root redirects and the `X-Site-Release` header are managed
separately on the server, not rendered by the release pipeline. Release navigation links to the
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
All specifications appear in the order panel and submitted email. Quote-only gasket
options never inherit the standard gasket price or contribute to the indicative total.
Legacy rotor rows without a variant cannot be mapped unambiguously; the page
asks the customer to select a new option and preserves their other order items.
Configured products also store a unique `lineId` and the validated `configuration`
described below, with an implicit quantity of one and no quantity controls.
No contact details, address, attachment or email body are saved in browser storage.
Company and phone are optional fields included in the order email only when
filled in. Street and house number remain required; the former address-extra
field is no longer collected. Delivery and notes headings share the main form's
section-title styling while preserving the delivery fieldset and legend.

Checkout sends an order directly to `/backend/order_form_handler.php` using
`multipart/form-data`, without opening an email application. Both this form and the
main contact form use `SiteForm.initValidation`, `initAttachments` and
`initSubmission` for inline validation, upload controls, the disabled sending state,
and success/error feedback. The main form keeps its existing contact endpoint.
Three optional attachment controls reuse the main form's localized labels and
styling, with an **8 MiB combined limit** (displayed as 8 MB). Photos, PDFs, plain
text/CSV/Markdown, Office documents, RTF and ZIP/7z/RAR archives are supported.
The server checks upload errors, actual sizes, extensions and detected MIME types;
it never executes, extracts or permanently stores uploaded files. MIME checks are
not antivirus scanning; attachments still need normal mailbox security controls.

After the business email is accepted by SMTP, the form resets and only the submitted
basket lines and quantities are removed. Other-tab additions are retained. If the
business email fails, the contact data, attachments and order stay available for
retry. The request ID is reused for an unchanged retry; the PHP session serializes
submissions and remembers receipts and the separate customer-recap delivery flag for
up to 24 hours (maximum 50 receipts). If only the recap fails, the response remains
successful with `customerEmail: "failed"`: the customer is told that the order was
received, to wait for our reply, and not to submit it again. An identical retry only
attempts the missing recap, never the already-sent business email. Both initial and
recap-only attempts are rate limited. Completed retries resend neither message.
Legacy receipts count as a business email already sent. This prevents duplicate
mail on ordinary retries in the same session, but is not a durable order database,
background retry queue or an exactly-once guarantee across SMTP failures/session loss.
SMTP acceptance does not guarantee inbox delivery; later bounces need normal mailbox
handling.

The handler obtains a same-origin CSRF token, checks a honeypot, limits order size
and quantities, and throttles valid attempts to five per IP per 15 minutes. The
browser sends product/variant IDs and configuration values, never an authoritative
price or HTML email. `build_shop.py` generates `backend/order_catalog.php` alongside
the pages. PHP independently resolves every selected product, current price and
required specification from this catalogue. A catalogue-version mismatch rejects
an outdated page rather than silently changing the order's prices.

`backend/order_mail.php` defines a simple Czech HTML email for the business and a
plain-text alternative: customer contact, postal address, product table with
quantities/configurations/unit and line prices, indicative total,
notes and an order ID. The source form language is included. The business email
omits the customer-facing delivery and non-binding-order notices. Quote-only,
starting-price and approximate items are explicitly labelled and excluded from the
fixed-price total. All customer content is escaped in HTML. Files are normal email
attachments. Mail is sent from the authenticated company address to
`info@petramuckova.cz`, with the customer in Reply-To, not the From header.

Only after the business email succeeds, a **separate recap** is sent to the validated
customer address. It uses the form language, including localized product names,
configuration labels and notices, with the company address in From and Reply-To.
`shop/order-email-translations.json` defines its subject, headings, thank-you text,
and bold next-step paragraph asking the customer to **wait for our reply** to confirm
the order, availability, selected delivery and final price. These two introductory
paragraphs appear before the recap heading in HTML and plain text. There is no
warning box or separate delivery/non-binding-order notice. A short reply invitation
is followed by a separate five-line company footer (name, IČ, address, email, phone),
defined in `ORDER_COMPANY_FOOTER` in `backend/order_mail.php`.
It includes the same reference, contact/delivery details, items, specifications,
prices, caveats and notes, in HTML and plain text. Uploads are sent only to the
business, not reattached to the customer recap. Each message has its own stable
Message-ID; the recap includes automatic-message headers to discourage auto-reply
loops. Email-only translations and the localized authoritative catalogue are bundled
into `backend/order_catalog.php` by the builder; no extra runtime JSON file is needed.
There is no online payment, stock reservation or fixed delivery tariff.

Postal delivery is represented as:

```js
{ email, phone, delivery: { method: 'postal', address: { fullName, company, street, city, postcode, country } }, notes }
```

Future delivery methods should define their own method identifier and required
fields in both the page and PHP validator. Actual availability, delivery and final
pricing remain confirmed by email.

### Hosting / release

The release pipeline is **frontend-only**. It never copies `backend/`, PHP files,
`.user.ini` or `.htaccess`, including files nested inside asset or language
directories. It does not require the private PHP source files, read server
configuration or regenerate the backend catalogue. Existing backend source files
are left unchanged. The next release build recreates `release/` without any stale
server-side files from earlier builds.

Manage the backend separately on the server. When updating order processing,
deploy these private files to its `backend/` directory:

- `order_form_handler.php` — public GET-token / POST-order endpoint.
- `order_mail.php` — validation and email template functions (no direct output).
- `order_catalog.php` — authoritative catalogue generated with
  `.venv/bin/python build_shop.py` (no direct output).

After changing products, variants or prices, generate and separately deploy the
updated `order_catalog.php` alongside the frontend update, so their catalogue
versions match. Mail-copy changes also require regenerating and separately
deploying the backend catalogue.

When uploading a frontend release, **preserve** the existing production `backend/`,
`.htaccess` and `.user.ini`; do not use a deployment mode that deletes files absent
from the release. As with the supplied contact handler, the library must exist at
`backend/lib/PHPMailer/src/{Exception,PHPMailer,SMTP}.php` and
`PETRAMUCKOVA_CZ_SMTP_PASSWORD` must be configured on the server (environment,
Apache variable, or its `REDIRECT_` equivalent). No password is added to PHP source.
The SMTP host remains `smtp.svethostingu.cz`, SMTPS port 465. TLS verification is not
disabled. PHP needs fileinfo, mbstring, OpenSSL, sessions, writable temporary/session
directories and outbound SMTP access. The existing `.user.ini` 16 MB POST/upload
limits accommodate the 8 MB attachment total plus form fields.

The host must execute PHP; **`python3 -m http.server` cannot submit orders**. For local
UI and PHP tests use the isolated test harness below, which replaces PHPMailer with
a recorder and uses a dummy password. Do not submit a real order merely to test a
deployment. A safe initial production check is GET `/backend/order_form_handler.php`:
it must return JSON with `status: "ready"` and a token, not PHP source. This checks
PHP/session availability only; SMTP delivery still needs a separately approved test.
Session receipts store hashes, timestamps and a recap delivery flag, not contact details. Private temporary
throttle files store hashed IP keys and request timestamps; stale throttle files are
occasionally cleaned up. Contact details and attachments are delivered to the business
mailbox and should follow its normal access/retention policy. The customer's own
contact details and order recap are also emailed to the address they supplied.

## Configured camshaft items

`skoda-ohv-camshaft` and `taz-camshaft` use `kind: "wizard"`. Škoda OHV uses four supplied
photographs in `assets/desktop`: `eshop-skoda-ohv-01.jpeg`, `eshop-skoda-ohv-02.jpeg`,
`eshop-skoda-ohv-03.jpg` and `eshop-skoda-ohv-04.jpg`. TAZ uses three photographs,
`eshop-taz-01.jpeg` through `eshop-taz-03.jpeg`. The images
appear in a gallery under the blog-style tags, heading and lead. The main photo
and thumbnails align with the inner text and form edges, using the blog card's
responsive padding (50px on desktop, 20px horizontally below 1400px).
Thumbnail buttons switch the large photo; clicking the large photo retains the
existing magnifier and fullscreen viewer. Without JavaScript, all linked photos
remain visible one below the other. Main gallery photos use a fixed 16:9 frame
with a center crop, so switching between landscape and portrait photos never
changes the gallery's height. Thumbnails also use a center crop. Enlarged photos
keep their original proportions and show the complete image. In the enlarged
viewer, previous/next arrows and the Left/Right arrow keys cycle through the
current product's photos, wrapping at either end. A position counter identifies
the current photo. Navigation is hidden for single-photo products; Escape and
photo/backdrop clicks still close the viewer and restore focus to the original
zoom link without changing the underlying thumbnail selection.
The introduction appears in the header. Detailed copy follows the gallery with
side-by-side regrinding/manufacturing sections using `.tech-math-block` and
`.equation-display` from the blog's formula panels, followed by installation
instructions. Supporting requirements use the blog's `.tech-list` red-arrow bullets.
The operation panels stack on small screens. The catalogue's `descriptionGroups` maps
the existing translated paragraphs into these sections without rewriting or
dropping their contents. Standard product cards use the same blog-style layout,
with the first description paragraph as the lead and any remaining notes as a
technical list, followed by the unchanged quantity-based option table.
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

`tests/test_order_handler.py` also runs real PHP multipart HTTP tests in a temporary
directory with a fake PHPMailer. Set `PHP_BIN` if PHP is not on PATH. The tests cover
all products/profiles, authoritative pricing, HTML escaping, required custom fields,
CSRF, MIME/size limits, retry deduplication, rate limits and simulated SMTP failures.
They also check localized customer recaps in all ten languages, separate recipients
and Reply-To headers, no customer attachments, and recap-only retries after a
partial delivery failure.
`tests/submission.test.js` covers the shared browser submission lifecycle and protocol.
With Playwright and a Chromium browser installed, run
`.venv/bin/python tests/smoke_order_browser.py` for the actual browser-to-PHP flow
and a regression check against the main contact form. `PLAYWRIGHT_MODULE` and
`BROWSER_EXECUTABLE` can point to existing local installations. An optional output
directory argument retains desktop/mobile screenshots and both sample HTML emails.
`tests/smoke_release.py` runs the real release build in an isolated tree and verifies
that no backend, PHP or server configuration is included and that private backend
fixtures remain unchanged; it never changes the working `release/` directory.
