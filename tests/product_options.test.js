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

test('quote and starting prices remain excluded from the fixed-price subtotal', () => {
    let items = shop.addOrderItem([], 'copper-rings', '', 3, products);
    items = shop.addOrderItem(items, 'distributor-rotor', '', 2, products);
    assert.deepEqual(shop.basketSummary(items, products), { count: 5, subtotalCents: 0, quotedCount: 5 });
});
