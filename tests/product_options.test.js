const { test } = require('node:test');
const assert = require('node:assert/strict');
const shop = require('../shop.js');
const { products } = require('../shop/catalog.json');
const row = (id, variant = '', quantity = 1) => ({ id, variant, quantity });
const load = items => shop.normaliseBasket({ version: 1, items }, products);

test('explicit add accumulates the draft quantity only when called', () => {
    const items = [];
    const next = shop.addOrderItem(items, 'resonance-exhaust', '', 3, products);
    assert.deepEqual(items, []);
    assert.deepEqual(next, [row('resonance-exhaust', '', 3)]);
    assert.deepEqual(shop.addOrderItem(next, 'resonance-exhaust', '', 2, products), [row('resonance-exhaust', '', 5)]);
});

test('separate option rows keep separate quantities and their own prices', () => {
    let items = shop.addOrderItem([], 'connecting-rod', '160', 2, products);
    items = shop.addOrderItem(items, 'connecting-rod', '156', 3, products);
    assert.deepEqual(items, [row('connecting-rod', '160', 2), row('connecting-rod', '156', 3)]);
    assert.equal(shop.basketSummary(items, products).subtotalCents, (12500 * 2 + 11500 * 3) * 100);
    const gaskets = [row('head-gasket', '80-5', 2), row('head-gasket', '82-0'), row('head-gasket', 'stock', 4)];
    assert.equal(shop.basketSummary(gaskets, products).subtotalCents, (620 * 3 + 160 * 4) * 100);
});

test('old connecting-rod and stock-gasket selections migrate without loss', () => {
    const old = [row('connecting-rod-160', '', 2), row('connecting-rod-156', '', 3), row('head-gasket-stock', '', 4), row('head-gasket', '82-0', 5)];
    const migrated = [row('connecting-rod', '160', 2), row('connecting-rod', '156', 3), row('head-gasket', 'stock', 4), row('head-gasket', '82-0', 5)];
    assert.deepEqual(load(old), migrated);
    assert.deepEqual(load(migrated), migrated);
    assert.deepEqual(old[0], row('connecting-rod-160', '', 2));
    assert.equal(shop.basketSummary(migrated, products).subtotalCents, (12500 * 2 + 11500 * 3 + 160 * 4 + 620 * 5) * 100);
});

test('mixed legacy and new rows merge by the new option identity', () => {
    assert.deepEqual(load([row('connecting-rod-156', '', 2), row('connecting-rod', '156', 3)]), [row('connecting-rod', '156', 5)]);
    assert.deepEqual(load([row('connecting-rod-160', 'invalid'), row('head-gasket-stock', '82-0')]), []);
});

test('old coils and distributor spare parts migrate to the corresponding new options', () => {
    const mappings = [
        ['ignition-coil-contact', 'ignition-coil', 'contact', 780],
        ['ignition-coil-contactless', 'ignition-coil', 'contactless', 1100],
        ['distributor-cap', 'distributor-parts', 'cap', 260],
        ['ignition-wiring', 'distributor-parts', 'wiring', 280],
        ['distributor-contacts', 'distributor-parts', 'contacts', 150],
        ['distributor-capacitor', 'distributor-parts', 'capacitor', 180],
    ];
    const old = mappings.map(([id], index) => row(id, '', index + 1));
    const migrated = mappings.map(([, id, variant], index) => row(id, variant, index + 1));
    assert.deepEqual(load(old), migrated);
    assert.deepEqual(load(migrated), migrated);
    assert.equal(shop.basketSummary(migrated, products).subtotalCents,
        mappings.reduce((sum, mapping, index) => sum + mapping[3] * (index + 1) * 100, 0));
    for (const [oldId, id, variant] of mappings) {
        assert.deepEqual(load([row(oldId, '', 2), row(id, variant, 3)]), [row(id, variant, 5)]);
        assert.deepEqual(load([row(oldId, 'invalid')]), []);
    }
});

test('new rod, kit and carburetor options use their current per-unit or per-set prices', () => {
    const cases = [
        ['connecting-rod', '156-engitec', 12500],
        ['cylinder-piston-kit', 'complete', 18000],
        ['cylinder-piston-kit', 'pistons-rings', 10400],
        ['cylinder-piston-kit', 'rings', 1600],
        ['carburetor-38-38', '', 7900],
    ];
    for (const [id, variant, price] of cases) {
        const items = shop.addOrderItem([], id, variant, 2, products);
        assert.deepEqual(items, [row(id, variant, 2)]);
        assert.equal(shop.basketSummary(items, products).subtotalCents, price * 2 * 100);
        assert.deepEqual(load(items), items);
    }
});

test('invalid draft quantities and variants never alter the order', () => {
    const items = [row('resonance-exhaust')];
    for (const count of [0, -1, 1.5, '2', NaN, Infinity, 10000]) {
        assert.equal(shop.addOrderItem(items, 'resonance-exhaust', '', count, products), items);
    }
    for (const [id, variant] of [['missing', ''], ['connecting-rod', ''], ['connecting-rod', '999'], ['head-gasket', ''], ['skoda-ohv-camshaft', '']]) {
        assert.equal(shop.addOrderItem(items, id, variant, 1, products), items);
    }
});

test('adding past the per-option limit fails atomically, without a partial add', () => {
    const items = [row('resonance-exhaust', '', 9998)];
    assert.equal(shop.addOrderItem(items, 'resonance-exhaust', '', 2, products), items);
    assert.deepEqual(shop.addOrderItem(items, 'resonance-exhaust', '', 1, products), [row('resonance-exhaust', '', 9999)]);
});

test('a full basket blocks new options but allows increasing an existing option', () => {
    const catalog = Array.from({ length: shop.MAX_ITEMS + 1 }, (_, index) => ({
        id: 'product-' + index, variants: [], price: 100, priceType: 'fixed',
    }));
    const items = catalog.slice(0, shop.MAX_ITEMS).map(product => row(product.id));
    assert.equal(shop.addOrderItem(items, catalog.at(-1).id, '', 1, catalog), items);
    const next = shop.addOrderItem(items, items[0].id, '', 2, catalog);
    assert.equal(next.length, shop.MAX_ITEMS);
    assert.equal(next[0].quantity, 3);
    assert.deepEqual(next.slice(1), items.slice(1));
});

test('quote, starting and approximate prices remain excluded from the fixed-price subtotal', () => {
    let items = shop.addOrderItem([], 'copper-rings', '', 3, products);
    items = shop.addOrderItem(items, 'distributor-rotor', 'original', 2, products);
    items = shop.addOrderItem(items, 'distributor-overhaul', '', 2, products);
    assert.deepEqual(shop.basketSummary(items, products), { count: 7, subtotalCents: 0, quotedCount: 7 });
});

test('approximate overhaul prices remain explicitly approximate in every localized order draft', () => {
    const texts = require('../shop/translations.json');
    const { languages, currency } = require('../shop/catalog.json');
    const details = shop.orderDetails({ deliveryMethod: 'postal', fullName: 'Test', email: 'test@example.test' });
    for (const locale of languages) {
        const config = { locale, currency, text: texts[locale],
            products: products.map(product => ({ ...product, name: product.translations[locale].name })) };
        const draft = shop.orderText([row('distributor-overhaul', '', 2)], details, config);
        const formatted = new Intl.NumberFormat(locale, { style: 'currency', currency, maximumFractionDigits: 0 }).format(3200);
        assert.ok(draft.includes(texts[locale].approx + ' ' + formatted), locale);
        assert.ok(draft.includes(texts[locale].quoteNotice), locale);
    }
});
