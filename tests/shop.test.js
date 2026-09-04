const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const shop = require('../shop.js');
const catalog = JSON.parse(fs.readFileSync(path.join(__dirname, '../shop/catalog.json'), 'utf8'));
const texts = JSON.parse(fs.readFileSync(path.join(__dirname, '../shop/translations.json'), 'utf8'));
const products = catalog.products;
const row = (id = 'resonance-exhaust', quantity = 1, variant = '') => ({ id, quantity, variant });
const normalise = items => shop.normaliseBasket({ version: 1, items }, products);

test('unknown storage versions and malformed data are discarded', () => {
    for (const value of [null, false, [], 'bad', {}, { version: 2, items: [row()] }, { version: 1, items: {} }]) {
        assert.deepEqual(shop.normaliseBasket(value, products), []);
    }
});
test('only IDs, variants and quantities survive storage loading', () => {
    assert.deepEqual(normalise([{ ...row(), email: 'private@example.test', company: 'Private company', phone: '+420 123 456 789', address: 'Private', price: 1, admin: true }]), [row()]);
});
test('removed products and invalid variants are discarded', () => {
    assert.deepEqual(normalise([row('gone'), row('exhaust-headers'), row('head-gasket', 1, 'unknown'), row('connecting-rod-160', 1, 'invalid')]), []);
});
test('quantities must be positive integers', () => {
    for (const quantity of [-1, 0, 1.5, '2', null, NaN, Infinity]) assert.deepEqual(normalise([row('connecting-rod-160', quantity)]), []);
});
test('duplicate rows merge and are bounded', () => {
    assert.deepEqual(normalise([row('connecting-rod-160', 6000), row('connecting-rod-160', 6000)]), [row('connecting-rod-160', 9999)]);
});
test('quantities above 99 and up to 9999 survive edits, storage and totals', () => {
    assert.equal(shop.MAX_QUANTITY, 9999);
    for (const quantity of [100, 1000, 9999]) {
        const items = shop.setQuantity([], 'connecting-rod-160', '', quantity, products);
        assert.deepEqual(items, [row('connecting-rod-160', quantity)]);
        assert.deepEqual(normalise(items), items);
        const summary = shop.basketSummary(items, products);
        assert.equal(summary.count, quantity);
        assert.equal(summary.subtotalCents, products.find(product => product.id === 'connecting-rod-160').price * 100 * quantity);
    }
});
test('variant quantities stay separate', () => {
    const basket = normalise([row('exhaust-headers', 2, 'small'), row('exhaust-headers', 3, 'large')]);
    assert.equal(basket.length, 2);
    assert.equal(shop.basketSummary(basket, products).subtotalCents, 3300000);
});
test('plus, minus and direct edits update the same line', () => {
    let items = shop.setQuantity([], 'connecting-rod-160', '', 1, products);
    items = shop.setQuantity(items, 'connecting-rod-160', '', 5, products);
    assert.deepEqual(items, [row('connecting-rod-160', 5)]);
    items = shop.setQuantity(items, 'connecting-rod-160', '', 0, products);
    assert.deepEqual(items, []);
});
test('quantity changes preserve basket order', () => {
    const items = normalise([row(), row('connecting-rod-160')]);
    assert.deepEqual(shop.setQuantity(items, 'resonance-exhaust', '', 2, products), [row('resonance-exhaust', 2), row('connecting-rod-160')]);
});
test('removing a basket line keeps other products and variants unchanged', () => {
    const items = normalise([row('exhaust-headers', 2, 'small'), row('exhaust-headers', 3, 'large'), row('connecting-rod-160')]);
    const remaining = shop.setQuantity(items, 'exhaust-headers', 'small', 0, products);
    assert.deepEqual(remaining, [row('exhaust-headers', 3, 'large'), row('connecting-rod-160')]);
});
test('basket removal uses a labelled cross button with the existing removal and focus hooks', () => {
    const doc = { createElement(tagName) {
        return { tagName, dataset: {}, attributes: {}, children: [],
            setAttribute(key, value) { this.attributes[key] = value; },
            append(child) { this.children.push(child); },
        };
    } };
    for (const lang of catalog.languages) {
        const name = products[0].translations[lang].name;
        const button = shop.basketRemoveButton(doc, row(), name, texts[lang].remove);
        assert.equal(button.tagName, 'button');
        assert.equal(button.type, 'button');
        assert.equal(button.className, 'shop-basket-remove');
        assert.equal(button.dataset.remove, '');
        assert.equal(button.dataset.focusKey, 'resonance-exhaust::remove');
        assert.equal(button.attributes['aria-label'], texts[lang].remove + ': ' + name);
        assert.equal(button.title, button.attributes['aria-label']);
        assert.equal(button.children.length, 1);
        assert.equal(button.children[0].className, 'mdi mdi-close');
        assert.equal(button.children[0].attributes['aria-hidden'], 'true');
    }
});
test('large or fractional direct updates are clamped and invalid values ignored', () => {
    assert.deepEqual(shop.setQuantity([], 'connecting-rod-160', '', 10000, products), [row('connecting-rod-160', 9999)]);
    assert.deepEqual(shop.setQuantity([], 'connecting-rod-160', '', 2.9, products), [row('connecting-rod-160', 2)]);
    assert.deepEqual(shop.setQuantity([], 'connecting-rod-160', '', NaN, products), []);
});

function basketSelectionFixture() {
    const handlers = {};
    const container = { addEventListener(type, handler) { handlers[type] = handler; } };
    shop.initBasketQuantitySelection(container);
    const input = (value = '9999', overrides = {}) => ({
        value, disabled: false, readOnly: false, selections: [],
        matches(selector) { assert.equal(selector, 'input[data-quantity]'); return true; },
        select() { this.selections.push(this.value); },
        ...overrides,
    });
    return { input, fire(type, target, properties = {}) { handlers[type]({ target, ...properties }); } };
}

test('clicking anywhere in a basket quantity input selects its complete value', () => {
    const { input, fire } = basketSelectionFixture();
    const field = input();
    for (const offsetX of [1, 60, 119]) fire('click', field, { offsetX });
    assert.deepEqual(field.selections, ['9999', '9999', '9999']);
    field.value = '1200';
    fire('click', field);
    assert.equal(field.selections.at(-1), '1200');
});

test('keyboard focus also selects the basket quantity for easy replacement', () => {
    const { input, fire } = basketSelectionFixture();
    const field = input('10');
    fire('focusin', field);
    assert.deepEqual(field.selections, ['10']);
});

test('basket quantity selection keeps working after rows are recreated', () => {
    const { input, fire } = basketSelectionFixture();
    const original = input('5');
    fire('click', original);
    const replacement = input('6');
    fire('focusin', replacement);
    fire('click', replacement);
    assert.deepEqual(original.selections, ['5']);
    assert.deepEqual(replacement.selections, ['6', '6']);
});

test('quantity selection ignores other controls and disabled or read-only fields', () => {
    const { input, fire } = basketSelectionFixture();
    for (const override of [{ matches: () => false }, { disabled: true }, { readOnly: true }]) {
        const field = input('12', override);
        fire('focusin', field);
        fire('click', field);
        assert.deepEqual(field.selections, []);
    }
});
test('quote and starting-price products are not misrepresented as fixed totals', () => {
    const summary = shop.basketSummary(normalise([row('resonance-exhaust', 2), row('distributor-rotor', 1), row('copper-rings', 4)]), products);
    assert.deepEqual(summary, { count: 7, subtotalCents: 540000, quotedCount: 5 });
});
test('dealer prices do not apply automatically at the dealer minimum', () => {
    const product = products.find(p => p.id === 'resonance-exhaust');
    assert.equal(shop.basketSummary([row(product.id, product.dealerMinimum)], products).subtotalCents, product.price * product.dealerMinimum * 100);
});
test('storage works across locales because it has no translated names or prices', () => {
    const items = normalise([row(), row('head-gasket', 2, '82-0')]);
    const stored = JSON.stringify({ version: 1, items });
    assert.deepEqual(shop.normaliseBasket(JSON.parse(stored), products), items);
    assert.equal(shop.STORAGE_KEY, 'muckova-shop-basket');
});
const values = {
    fullName: ' Test Customer ', email: 'customer@example.test', deliveryMethod: 'postal',
    company: ' Test Company s.r.o. ', phone: ' +420 123 456 789 ',
    street: 'Street 12', city: 'Praha', postcode: '110 00', country: 'Česko', notes: 'A & B + 80.5 mm',
};
test('delivery has a method and a separate postal-address structure', () => {
    const details = shop.orderDetails(values);
    assert.equal(details.delivery.method, 'postal');
    assert.equal(details.delivery.address.fullName, 'Test Customer');
    assert.equal(details.delivery.address.company, values.company.trim());
    assert.equal(details.delivery.address.postcode, '110 00');
    assert.equal(details.email, values.email);
    assert.equal(details.phone, values.phone.trim());
    assert.throws(() => shop.orderDetails({ ...values, deliveryMethod: 'pickup' }));
});
test('every locale generates an order draft with products, contact details, address and caveats', () => {
    for (const locale of catalog.languages) {
        const config = { locale, currency: catalog.currency, text: texts[locale], products: products.map(p => ({ ...p, name: p.translations[locale].name })) };
        const items = normalise([row('exhaust-headers', 2, 'small'), row('distributor-rotor'), row('copper-rings')]);
        const draft = shop.orderText(items, shop.orderDetails(values), config);
        for (const value of ['TAZ 1.43 l', '[exhaust-headers:small]', values.email, values.street, values.country, values.notes, texts[locale].deliveryNotice, texts[locale].quoteNotice, texts[locale].confirmation]) {
            assert.ok(draft.includes(value), locale + ': ' + value);
        }
        assert.ok(draft.split('\n').includes(texts[locale].company + ': ' + values.company.trim()), locale);
        assert.ok(draft.split('\n').includes(texts[locale].phone + ': ' + values.phone.trim()), locale);
    }
});
test('empty optional company and phone fields are omitted from every localized draft', () => {
    for (const locale of catalog.languages) {
        const config = { locale, currency: catalog.currency, text: texts[locale], products: products.map(p => ({ ...p, name: p.translations[locale].name })) };
        for (const empty of ['', '  \t ', undefined, null]) {
            const details = shop.orderDetails({ ...values, company: empty, phone: empty });
            assert.equal(details.delivery.address.company, '');
            assert.equal(details.phone, '');
            const draft = shop.orderText([row()], details, config);
            assert.ok(!draft.includes(texts[locale].company + ':'), locale);
            assert.ok(!draft.includes(texts[locale].phone + ':'), locale);
            assert.doesNotMatch(draft, /\b(?:undefined|null)\b/);
            assert.ok(draft.includes(values.street));
        }
    }
});
test('the removed address-extra field is ignored in order details and drafts', () => {
    const details = shop.orderDetails({ ...values, addressExtra: 'Legacy address supplement' });
    assert.ok(!Object.hasOwn(details.delivery.address, 'addressExtra'));
    const config = { locale: 'cs', currency: catalog.currency, text: texts.cs, products: products.map(p => ({ ...p, name: p.translations.cs.name })) };
    assert.ok(!shop.orderText([row()], details, config).includes('Legacy address supplement'));
});
test('mailto encodes user text and never changes recipient or injects extra headers', () => {
    const body = 'Žluťoučký &bcc=bad@example.test\r\nA + B # ?';
    const url = new URL(shop.mailtoUrl('info@petramuckova.cz', 'Order & delivery', body));
    assert.equal(url.pathname, 'info@petramuckova.cz');
    assert.equal(url.searchParams.get('body'), body);
    assert.equal(url.searchParams.get('subject'), 'Order & delivery');
    assert.equal(url.searchParams.has('bcc'), false);
});

test('variant dropdowns reuse main-page Choices settings with accessible labels', () => {
    const selects = products.filter(product => product.variants.length).map(product => ({
        id: 'variant-' + product.id, value: '', labels: [{ id: 'label-variant-' + product.id }],
    }));
    const calls = [];
    const doc = { querySelectorAll(selector) {
        assert.equal(selector, '.shop-variant .custom-select');
        return selects;
    } };
    function ChoicesFixture(select, options) { calls.push({ select, options }); }
    shop.initVariantSelects(doc, ChoicesFixture);
    assert.equal(calls.length, selects.length);
    calls.forEach(({ select, options }, index) => {
        assert.equal(select, selects[index]);
        assert.equal(select.value, '');
        assert.deepEqual(options, {
            searchEnabled: false, itemSelectText: '', shouldSort: false,
            allowHTML: false, labelId: select.labels[0].id,
        });
    });
});
test('native variant controls remain usable when Choices is unavailable', () => {
    shop.initVariantSelects({ querySelectorAll() { assert.fail('Native controls must be left untouched'); } }, undefined);
});

function photoViewerFixture({ nativeDialog = true, photos = [
    { src: '/assets/desktop/engine.webp', alt: 'Camshaft' },
    { src: 'https://cdn.jsdelivr.net/gh/pmuckova/site-petramuckova.cz@main/assets/desktop/shop-placeholder.webp', alt: 'Photo not yet available' },
] } = {}) {
    const doc = { activeElement: null };
    function node() {
        const classList = new Set();
        classList.remove = name => classList.delete(name);
        classList.toggle = (name, enabled) => enabled ? classList.add(name) : classList.delete(name);
        return {
            listeners: {}, attributes: {}, classList,
            addEventListener(type, handler) { this.listeners[type] = handler; },
            setAttribute(key, value) { this.attributes[key] = value; },
            focus() { doc.activeElement = this; },
            fire(type, props = {}) {
                const event = { button: 0, detail: 1, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, ...props };
                this.listeners[type]?.(event);
                return event;
            },
        };
    }
    Object.assign(doc, node());
    const viewer = node(), image = node(), closeButton = node();
    viewer.open = false;
    if (nativeDialog) viewer.showModal = () => { viewer.open = true; };
    viewer.close = () => { viewer.open = false; viewer.fire('close'); };
    viewer.querySelector = selector => selector === '.lightbox-img' ? image : closeButton;
    const links = photos.map(photo => {
        const link = node();
        link.href = photo.src;
        link.querySelector = () => ({ alt: photo.alt });
        return link;
    });
    doc.getElementById = id => id === 'shop-lightbox' ? viewer : null;
    doc.querySelectorAll = selector => selector === '.shop-photo-link' ? links : [];
    shop.initPhotoViewer(doc);
    return { doc, viewer, image, closeButton, links };
}

test('product photos open the blog-style viewer with the full image, alt text and keyboard focus', () => {
    const { doc, viewer, image, closeButton, links } = photoViewerFixture();
    for (const link of links) {
        const event = link.fire('click');
        assert.equal(event.defaultPrevented, true);
        assert.equal(viewer.open, true);
        assert.equal(viewer.classList.has('active'), true);
        assert.equal(image.src, link.href);
        assert.equal(image.alt, link.querySelector('img').alt);
        assert.equal(viewer.attributes['aria-label'], image.alt);
        assert.equal(doc.activeElement, closeButton);
        viewer.fire('click');
        assert.equal(viewer.open, false);
        assert.equal(viewer.classList.has('active'), false);
        assert.equal(doc.activeElement, link);
    }
});
test('both photos in every camshaft gallery enlarge independently and restore the correct link', () => {
    for (const productId of ['skoda-ohv-camshaft', 'taz-camshaft']) {
        const photos = products.find(product => product.id === productId).images
            .map(image => ({ src: image.src, alt: image.alt.cs }));
        const { doc, viewer, image, links } = photoViewerFixture({ photos });
        assert.equal(links.length, 2);
        links.forEach((link, index) => {
            link.fire('click');
            assert.equal(viewer.open, true);
            assert.equal(image.src, photos[index].src);
            assert.equal(image.alt, photos[index].alt);
            assert.equal(viewer.fire('cancel').defaultPrevented, true);
            assert.equal(viewer.open, false);
            assert.equal(doc.activeElement, link);
            assert.equal(link.classList.has('shop-photo-pointer-focus'), true);
        });
    }
});

test('Escape after mouse, touch or pen opening restores photo focus without a ring', () => {
    for (const activation of [{ detail: 1 }, { detail: 0, pointerType: 'touch' }, { detail: 0, pointerType: 'pen' }]) {
        const { doc, viewer, links } = photoViewerFixture();
        links[0].fire('click', activation);
        doc.fire('keydown', { key: 'Escape' });
        // Native dialogs emit cancel for Escape and keep Tab focus inside the modal.
        assert.equal(viewer.fire('cancel').defaultPrevented, true);
        assert.equal(viewer.open, false);
        assert.equal(viewer.classList.has('active'), false);
        assert.equal(doc.activeElement, links[0]);
        assert.equal(viewer.classList.has('shop-photo-pointer-focus'), true);
        assert.equal(links[0].classList.has('shop-photo-pointer-focus'), true);
        // Actual keyboard navigation must still bring back the visible focus indicator.
        doc.fire('keydown', { key: 'Tab' });
        assert.equal(links[0].classList.has('shop-photo-pointer-focus'), false);
    }
});
test('Escape after keyboard opening preserves visible photo focus', () => {
    const { doc, viewer, links } = photoViewerFixture();
    links[0].fire('click', { detail: 0 });
    doc.fire('keydown', { key: 'Escape' });
    assert.equal(viewer.fire('cancel').defaultPrevented, true);
    assert.equal(viewer.open, false);
    assert.equal(doc.activeElement, links[0]);
    assert.equal(viewer.classList.has('shop-photo-pointer-focus'), false);
    assert.equal(links[0].classList.has('shop-photo-pointer-focus'), false);
});
test('Tab inside a mouse-opened viewer preserves keyboard focus after Escape', () => {
    const { doc, viewer, links } = photoViewerFixture();
    links[0].fire('click');
    doc.fire('keydown', { key: 'Tab' });
    doc.fire('keydown', { key: 'Escape' });
    viewer.fire('cancel');
    assert.equal(viewer.open, false);
    assert.equal(doc.activeElement, links[0]);
    assert.equal(links[0].classList.has('shop-photo-pointer-focus'), false);
});
test('pointer photo interactions suppress outlines before modal focus and after closing', () => {
    const { doc, viewer, links } = photoViewerFixture();
    links[0].fire('pointerdown');
    assert.equal(links[0].classList.has('shop-photo-pointer-focus'), true);
    links[0].fire('click');
    assert.equal(viewer.classList.has('shop-photo-pointer-focus'), true);
    viewer.fire('pointerdown');
    viewer.fire('click');
    assert.equal(doc.activeElement, links[0]);
    assert.equal(links[0].classList.has('shop-photo-pointer-focus'), true);
});
test('Tab restores visible photo focus even for previously clicked links', () => {
    const { doc, viewer, links } = photoViewerFixture();
    links[0].fire('click');
    viewer.fire('click');
    links[1].fire('click');
    doc.fire('keydown', { key: 'Tab' });
    assert.equal(viewer.classList.has('shop-photo-pointer-focus'), false);
    assert.ok(links.every(link => !link.classList.has('shop-photo-pointer-focus')));
});
test('touch photo clicks suppress outlines even when their click count is zero', () => {
    const { doc, viewer, links } = photoViewerFixture();
    links[0].fire('click', { detail: 0, pointerType: 'touch' });
    assert.equal(viewer.classList.has('shop-photo-pointer-focus'), true);
    viewer.fire('click', { detail: 0, pointerType: 'touch' });
    assert.equal(doc.activeElement, links[0]);
    assert.equal(links[0].classList.has('shop-photo-pointer-focus'), true);
});
test('keyboard photo activation and keyboard close preserve visible focus', () => {
    const { doc, viewer, links } = photoViewerFixture();
    links[0].fire('click', { detail: 0 });
    assert.equal(viewer.classList.has('shop-photo-pointer-focus'), false);
    assert.equal(links[0].classList.has('shop-photo-pointer-focus'), false);
    viewer.fire('click', { detail: 0 });
    assert.equal(doc.activeElement, links[0]);
    assert.equal(links[0].classList.has('shop-photo-pointer-focus'), false);
});
test('switching from keyboard zoom to a pointer close suppresses the restored outline', () => {
    const { doc, viewer, links } = photoViewerFixture();
    links[0].fire('click', { detail: 0 });
    viewer.fire('pointerdown');
    assert.equal(viewer.classList.has('shop-photo-pointer-focus'), true);
    assert.equal(links[0].classList.has('shop-photo-pointer-focus'), true);
    viewer.fire('click');
    assert.equal(doc.activeElement, links[0]);
    assert.equal(links[0].classList.has('shop-photo-pointer-focus'), true);
});
test('photo links retain normal modified-click and unsupported-dialog behaviour', () => {
    const { viewer, links } = photoViewerFixture();
    for (const props of [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }]) {
        assert.equal(links[0].fire('click', props).defaultPrevented, false);
        assert.equal(viewer.open, false);
    }
    const fallback = photoViewerFixture({ nativeDialog: false });
    assert.equal(fallback.links[0].fire('click').defaultPrevented, false);
    assert.equal(fallback.viewer.open, false);
});

function navigationFixture() {
    const doc = { activeElement: null };
    function node(attrs = {}) {
        return {
            attrs, hidden: true, style: {}, listeners: {},
            getAttribute(key) { return this.attrs[key]; },
            setAttribute(key, value) { this.attrs[key] = value; },
            addEventListener(type, handler) { this.listeners[type] = handler; },
            focus() { doc.activeElement = this; },
            closest() { return this; },
            fire(type, props = {}) {
                const event = { defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, ...props };
                this.listeners[type]?.(event);
                return event;
            },
        };
    }
    Object.assign(doc, node());
    const menus = ['mobile-menu-overlay', 'mobile-langchooser-overlay'].map(id => {
        const trigger = node({ 'aria-controls': id, 'aria-expanded': 'false' });
        const links = [node({ href: '/cs/' }), node({ href: '/cs/shop' })];
        const panel = node();
        panel.querySelector = () => links[0];
        panel.querySelectorAll = () => links;
        return { id, trigger, panel, links };
    });
    doc.querySelectorAll = () => menus.map(menu => menu.trigger);
    doc.getElementById = id => menus.find(menu => menu.id === id)?.panel;
    const media = node();
    const viewport = { matchMedia(query) { assert.equal(query, '(min-width: 1400px)'); return media; } };
    shop.initNavigation(doc, viewport);
    return { doc, menus, media };
}

test('blog-style mobile menus open, focus their first link, and close with Escape', () => {
    const { doc, menus } = navigationFixture();
    const menu = menus[0];
    menu.trigger.fire('click');
    assert.equal(menu.panel.hidden, false);
    assert.equal(menu.panel.style.display, 'block');
    assert.equal(menu.trigger.getAttribute('aria-expanded'), 'true');
    assert.equal(doc.activeElement, menu.links[0]);
    assert.equal(doc.fire('keydown', { key: 'Escape' }).defaultPrevented, true);
    assert.equal(menu.panel.hidden, true);
    assert.equal(menu.trigger.getAttribute('aria-expanded'), 'false');
    assert.equal(doc.activeElement, menu.trigger);
});

test('keyboard focus stays in the open mobile menu', () => {
    const { doc, menus } = navigationFixture();
    const menu = menus[0];
    menu.trigger.fire('click');
    assert.equal(doc.fire('keydown', { key: 'Tab', shiftKey: true }).defaultPrevented, true);
    assert.equal(doc.activeElement, menu.links[1]);
    assert.equal(doc.fire('keydown', { key: 'Tab' }).defaultPrevented, true);
    assert.equal(doc.activeElement, menu.links[0]);
});

test('mobile navigation preserves links and closes on selection or the desktop breakpoint', () => {
    const { menus, media } = navigationFixture();
    menus[0].trigger.fire('click');
    menus[1].trigger.fire('click');
    assert.equal(menus[0].panel.hidden, true);
    assert.equal(menus[1].panel.hidden, false);
    const click = menus[1].panel.fire('click', { target: menus[1].links[1] });
    assert.equal(click.defaultPrevented, false);
    assert.equal(menus[1].panel.hidden, true);
    menus[0].trigger.fire('click');
    media.fire('change', { matches: true });
    assert.ok(menus.every(menu => menu.panel.hidden));
});
