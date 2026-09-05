const { test } = require('node:test');
const assert = require('node:assert/strict');
const shop = require('../shop.js');
const { products, languages, currency } = require('../shop/catalog.json');
const texts = require('../shop/translations.json');
const product = products.find(product => product.id === 'head-gasket');
const specification = (spacing = '88-88-88', thickness = '1.5') => ({ spacing, thickness });
const add = (items, values = specification(), quantity = 1) => shop.addOrderItem(items, product.id, 'custom', quantity, products, values);
const restore = items => shop.normaliseBasket({ version: 1, items }, products);

test('custom gasket accepts free-text spacing and canonical positive decimal thickness', () => {
    assert.deepEqual(shop.normaliseOrderParameters(specification(' 88 / 88 / 88\n ', '01,500'), product, 'custom'),
        specification('88 / 88 / 88', '1.5'));
    for (const value of ['0.5', '.5', '0,5', 0.5, '5e-1']) {
        assert.deepEqual(shop.normaliseOrderParameters(specification('88–88–88', value), product, 'custom'), specification('88–88–88', '0.5'));
    }
    assert.deepEqual(restore(add([], specification('88-88-88', '0.0000001'))), add([], specification('88-88-88', '1e-7')));
    assert.deepEqual(shop.normaliseOrderParameters(specification('0', '2'), product, 'custom'), specification('0', '2'));
    assert.deepEqual(shop.normaliseOrderParameters(specification('x'.repeat(200), '2'), product, 'custom'), specification('x'.repeat(200), '2'));
});

test('both gasket fields are required and thickness must be a finite positive decimal', () => {
    for (const spacing of [undefined, null, '', ' ', '\n\t\0', 88, true, [], {}, 'x'.repeat(201)]) {
        assert.equal(shop.normaliseOrderParameters({ spacing, thickness: '1.5' }, product, 'custom'), null, String(spacing));
    }
    for (const thickness of [null, '', ' ', 0, -1, '-1.5', '1.2.3', '1,2,3', '0x10', Infinity, NaN, true, [], {}, '1e309', '1e-999', '1'.repeat(33)]) {
        assert.equal(shop.normaliseOrderParameters(specification('88-88-88', thickness), product, 'custom'), null, String(thickness));
        const items = [];
        assert.equal(add(items, specification('88-88-88', thickness)), items);
    }
    assert.equal(shop.normaliseOrderParameters(undefined, product, 'custom'), null);
    assert.equal(shop.normaliseOrderParameters({ spacing: '88-88-88' }, product, 'custom'), null);
});

test('custom gasket specifications survive storage and remain independently editable', () => {
    let items = add([], { ...specification(), email: 'private@example.test', price: 1 }, 2);
    assert.deepEqual(items[0], { id: product.id, variant: 'custom', parameters: specification(), quantity: 2 });
    items = add(items, specification(' 88-88-88 ', '1,50'), 3);
    items = add(items, specification('90-88-90', '1.5'), 4);
    items = add(items, specification('88-88-88', '2'), 6);
    assert.deepEqual(items.map(item => item.quantity), [5, 4, 6]);
    assert.deepEqual(restore(items), items);
    items = shop.setQuantity(items, product.id, 'custom', 8, products, specification());
    assert.deepEqual(items.map(item => item.quantity), [8, 4, 6]);
    assert.deepEqual(shop.removeBasketItem(items, shop.basketLineKey(items[1])), [items[0], items[2]]);
    assert.deepEqual(restore([{ ...items[0], parameters: specification('88-88-88', '-1') }]), []);
    const fixed = shop.addOrderItem([], product.id, '80-5', 2, products, specification());
    assert.deepEqual(fixed[0], { id: product.id, variant: '80-5', quantity: 2 });
});

test('free-text punctuation cannot collide in specification line keys', () => {
    const base = { id: product.id, variant: 'custom' };
    const a = { ...base, parameters: { a: '88,b=90', b: '92' } };
    const b = { ...base, parameters: { a: '88', b: '90,b=92' } };
    assert.notEqual(shop.basketLineKey(a), shop.basketLineKey(b));
    assert.equal(shop.basketLineKey(a), shop.basketLineKey({ ...a, parameters: { b: '92', a: '88,b=90' } }));
});

test('custom gasket price never falls back to 620 CZK or adds to the indicative total', () => {
    let items = add([], specification(), 3);
    assert.deepEqual(shop.itemPrice(items[0], product), { price: null, priceType: 'quote' });
    assert.deepEqual(shop.basketSummary(items, products), { count: 3, subtotalCents: 0, quotedCount: 3 });
    for (const [id, price] of [['80-5', 620], ['82-0', 620], ['stock', 160]]) {
        items = shop.addOrderItem(items, product.id, id, 2, products);
        assert.deepEqual(shop.itemPrice({ variant: id }, product), { price, priceType: 'fixed' });
    }
    assert.deepEqual(shop.basketSummary(items, products), { count: 9, subtotalCents: 280000, quotedCount: 3 });
});

test('all localized drafts include gasket specifications and price-on-request wording', () => {
    const items = add([], specification('88-90-88', '1,25'), 2);
    for (const locale of languages) {
        const localized = products.map(product => ({ ...product, name: product.translations[locale].name,
            variants: product.variants.map(variant => ({ ...variant, label: variant.translations?.[locale] || variant.label })) }));
        const config = { locale, currency, products: localized, text: texts[locale] };
        const details = shop.configurationDetails(items[0], product, config);
        assert.deepEqual(details, [[texts[locale].gasketSpacing, '88-90-88'], [texts[locale].gasketThickness, '1.25']]);
        const draft = shop.orderText(items, shop.orderDetails({ deliveryMethod: 'postal' }), config);
        for (const [label, value] of details) assert.ok(draft.includes(label + ': ' + value), locale);
        assert.ok(draft.includes(texts[locale].quote), locale);
        assert.ok(draft.includes(product.variants.find(v => v.id === 'custom').translations[locale]), locale);
        assert.ok(!draft.includes('620'), locale);
    }
});

test('conditional gasket fields validate by type and clear warnings when unselected', () => {
    const inputs = ['spacing', 'thickness'].map(id => Object.assign(new EventTarget(), {
        value: '', disabled: true, maxLength: id === 'spacing' ? 200 : -1,
        dataset: { orderField: id, orderFieldType: id === 'spacing' ? 'text' : 'decimal', orderFieldWarning: 'Invalid ' + id },
        setCustomValidity(value) { this.error = value; },
    }));
    const rows = inputs.map(input => ({ hidden: true, dataset: { orderFieldRow: 'custom' }, querySelector: () => input }));
    const controller = shop.initOrderParameterFields({ querySelectorAll: () => rows }, 'Invalid RPM');
    controller.select('custom');
    inputs[0].value = '88-90-88'; inputs[1].value = '1.25';
    inputs[1].dispatchEvent(new Event('input'));
    assert.ok(inputs.every(input => !input.disabled && !input.error));
    assert.deepEqual(controller.read(), specification('88-90-88', '1.25'));
    for (const value of ['0', '-1', '1.2.3']) {
        inputs[1].value = value;
        inputs[1].dispatchEvent(new Event('input'));
        assert.equal(inputs[1].error, 'Invalid thickness');
    }
    controller.select('80-5');
    assert.deepEqual(controller.read(), {});
    assert.ok(inputs.every(input => input.disabled && !input.error));
    controller.select('custom');
    assert.equal(inputs[0].value, '88-90-88');
    inputs[1].value = '1.5';
    inputs[1].dispatchEvent(new Event('input'));
    assert.equal(inputs[1].error, '');
    controller.select('');
    assert.deepEqual(controller.read(), {});
    assert.ok(inputs.every(input => input.disabled && !input.error));
});
