const { test } = require('node:test');
const assert = require('node:assert/strict');
const shop = require('../shop.js');
const { products, languages, currency } = require('../shop/catalog.json');
const texts = require('../shop/translations.json');
const product = products.find(product => product.id === 'distributor-rotor');
const range = (min = '4800', max = '5100') => ({ 'min-rpm': min, 'max-rpm': max });
const add = (items, values = range(), quantity = 1) => shop.addOrderItem(items, product.id, 'custom', quantity, products, values);
const restore = items => shop.normaliseBasket({ version: 1, items }, products);

test('rotor custom options require positive safe whole RPM values in ascending order', () => {
    assert.deepEqual(shop.normaliseOrderParameters(range('004800', 5100), product, 'custom'), range());
    assert.deepEqual(shop.normaliseOrderParameters(range('5000', '5000'), product, 'custom'), range('5000', '5000'));
    for (const value of [undefined, null, '', ' ', 0, -1, 1.5, '4.5', '1e3', '0x100', Infinity, NaN, true, [], {}, 9007199254740992]) {
        for (const fields of [{ 'min-rpm': value, 'max-rpm': '5100' }, { 'min-rpm': '4800', 'max-rpm': value }]) {
            assert.equal(shop.normaliseOrderParameters(fields, product, 'custom'), null, JSON.stringify(fields));
            const items = [];
            assert.equal(add(items, fields), items);
        }
    }
    assert.equal(shop.normaliseOrderParameters(range('5100', '4800'), product, 'custom'), null);
    assert.equal(shop.normaliseOrderParameters(undefined, product, 'custom'), null);
});

test('custom RPM settings survive storage while unrelated or forged fields are stripped', () => {
    const items = add([], { ...range(), email: 'private@example.test', price: 1 });
    assert.deepEqual(items[0], { id: product.id, variant: 'custom', parameters: range(), quantity: 1 });
    assert.deepEqual(restore(items), items);
    assert.deepEqual(restore([{ ...items[0], parameters: range('5100', '4800') }]), []);
    const original = shop.addOrderItem([], product.id, 'original', 1, products, range());
    assert.deepEqual(original[0], { id: product.id, variant: 'original', quantity: 1 });
});

test('equal RPM settings merge, but different ranges stay independently editable and removable', () => {
    let items = add([], range(), 2);
    items = add(items, range('004800', '5100'), 3);
    items = add(items, range('6000', '6500'), 4);
    assert.equal(items.length, 2);
    assert.deepEqual(items.map(item => item.quantity), [5, 4]);
    assert.notEqual(shop.basketLineKey(items[0]), shop.basketLineKey(items[1]));
    assert.equal(shop.basketLineKey(items[0]), shop.basketLineKey({ ...items[0], parameters: { 'max-rpm': '5100', 'min-rpm': '4800' } }));
    items = shop.setQuantity(items, product.id, 'custom', 8, products, range());
    assert.deepEqual(items.map(item => item.quantity), [8, 4]);
    assert.deepEqual(restore(items), items);
    assert.deepEqual(shop.removeBasketItem(items, shop.basketLineKey(items[0])), [items[1]]);
    assert.deepEqual(shop.setQuantity(items, product.id, 'custom', 0, products, range()), [items[1]]);
    const full = add([], range(), 9999);
    assert.equal(add(full, range(), 1), full);
    assert.equal(add(full, range('6000', '6500'), 1).length, 2);
});

test('all three rotor options stay quote-only and retain RPM details in every localized draft', () => {
    let items = add([]);
    items = shop.addOrderItem(items, product.id, '4800-5100', 2, products);
    items = shop.addOrderItem(items, product.id, 'original', 3, products);
    assert.deepEqual(shop.basketSummary(items, products), { count: 6, subtotalCents: 0, quotedCount: 6 });
    for (const locale of languages) {
        const localized = products.map(product => ({ ...product, name: product.translations[locale].name,
            variants: product.variants.map(variant => ({ ...variant, label: variant.translations?.[locale] || variant.label })) }));
        const config = { locale, currency, products: localized, text: texts[locale] };
        const details = shop.configurationDetails(items[0], product, config);
        assert.deepEqual(details, [[texts[locale].minRpm, '4800'], [texts[locale].maxRpm, '5100']]);
        const draft = shop.orderText(items, shop.orderDetails({ deliveryMethod: 'postal' }), config);
        for (const [label, value] of details) assert.ok(draft.includes(label + ': ' + value), locale);
        for (const variant of localized.find(p => p.id === product.id).variants) assert.ok(draft.includes(variant.label), locale);
        assert.ok(draft.includes(texts[locale].quote), locale);
    }
});

test('an old unconfigured rotor requests reselection instead of guessing the new option', () => {
    const old = { id: product.id, variant: '', quantity: 2 };
    const other = { id: 'resonance-exhaust', variant: '', quantity: 1 };
    assert.equal(shop.hasLegacyRotors({ version: 1, items: [old, other] }), true);
    assert.deepEqual(restore([old, other]), [other]);
    assert.equal(shop.hasLegacyRotors({ version: 1, items: add([]) }), false);
    assert.equal(Boolean(shop.hasLegacyRotors(null)), false);
});

test('conditional RPM field controllers retain values but disable hidden fields and clear validity', () => {
    const inputs = ['min-rpm', 'max-rpm'].map(id => Object.assign(new EventTarget(), {
        value: '', disabled: true, dataset: { orderField: id, ...(id === 'max-rpm' ? { minimumField: 'min-rpm' } : {}) },
        setCustomValidity(value) { this.error = value; },
    }));
    const rows = inputs.map(input => ({ hidden: true, dataset: { orderFieldRow: 'custom' }, querySelector: () => input }));
    const controller = shop.initOrderParameterFields({ querySelectorAll: () => rows }, 'Invalid RPM');
    controller.select('original');
    assert.ok(inputs.every(input => input.disabled && !input.error));
    controller.select('custom');
    assert.ok(inputs.every(input => !input.disabled));
    inputs[0].value = '5000'; inputs[1].value = '4800';
    inputs[0].dispatchEvent(new Event('input'));
    assert.equal(inputs[1].error, 'Invalid RPM');
    inputs[0].value = '4700';
    inputs[0].dispatchEvent(new Event('input'));
    assert.equal(inputs[1].error, '');
    assert.deepEqual(controller.read(), range('4700', '4800'));
    controller.select('');
    assert.deepEqual(controller.read(), {});
    assert.ok(inputs.every(input => input.disabled && !input.error));
    controller.select('custom');
    assert.deepEqual(controller.read(), range('4700', '4800'));
});
