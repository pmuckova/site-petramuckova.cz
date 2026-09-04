const { test } = require('node:test');
const assert = require('node:assert/strict');
const catalog = require('../shop/catalog.json');
const texts = require('../shop/translations.json');
const shop = require('../shop.js');
const SiteForm = require('../form.js');
const product = catalog.products.find(product => product.kind === 'wizard');
const engine = { engineType: 'Škoda 136', bore: '75.5', stroke: '72', intakeValve: '34', exhaustValve: '30', rockerRatio: '1.45' };
const configuration = (profile = 'regrind-262-248', bearing = '') => ({ profile, bearing, values: { ...engine } });
const add = (items = [], value = configuration(), lineId = 'test-1') => shop.addConfiguredItem(items, product.id, value, catalog.products, lineId);
const load = items => shop.normaliseBasket({ version: 1, items }, catalog.products);

test('every CSV option adds one configured line at its current catalogue price', () => {
    assert.deepEqual(product.wizard.profiles.map(profile => profile.price), [5600, 5600, 11400, 11400, 13200, 11400]);
    for (const profile of product.wizard.profiles) {
        const items = add([], configuration(profile.id, profile.manufacture === 'new' ? 'small' : ''));
        assert.equal(items.length, 1);
        assert.equal(items[0].quantity, 1);
        assert.deepEqual(shop.basketSummary(items, catalog.products), { count: 1, subtotalCents: profile.price * 100, quotedCount: 0 });
    }
});

test('identical submissions remain separate, persistent, independently removable entries', () => {
    const ordinary = { id: 'exhaust-headers', variant: 'small', quantity: 3 };
    const items = add(add([ordinary]), configuration(), 'test-2');
    assert.equal(items.length, 3);
    assert.deepEqual(load(JSON.parse(JSON.stringify(items))), items);
    const key = shop.basketLineKey(items[1]);
    assert.notEqual(key, shop.basketLineKey(items[2]));
    assert.deepEqual(shop.removeBasketItem(items, key), [ordinary, items[2]]);
    assert.deepEqual(shop.basketSummary(items, catalog.products), { count: 5, subtotalCents: 3100000, quotedCount: 0 });
    assert.equal(shop.setQuantity(items, product.id, '', 99, catalog.products), items);
    const changed = shop.setQuantity(items, ordinary.id, ordinary.variant, 4, catalog.products);
    assert.deepEqual(changed.slice(1), items.slice(1));
});

test('bearing selection is mandatory only for new shafts, and stale regrind bearings are removed', () => {
    assert.equal(shop.normaliseConfiguration(configuration('new-294-294'), product), null);
    assert.equal(shop.normaliseConfiguration(configuration('new-294-294', 'invented'), product), null);
    for (const bearing of ['small', 'large']) assert.equal(add([], configuration('new-294-294', bearing)).length, 1);
    assert.equal(add([], configuration('regrind-272-266', 'large'))[0].configuration.bearing, '');
    assert.equal(shop.normaliseConfiguration(configuration('unknown'), product), null);
});

test('all six engine fields are required and numeric fields must contain positive finite decimals', () => {
    for (const key of Object.keys(engine)) {
        const value = configuration();
        delete value.values[key];
        assert.equal(shop.normaliseConfiguration(value, product), null, key);
        value.values[key] = '   ';
        assert.equal(shop.normaliseConfiguration(value, product), null, key);
    }
    for (const field of product.wizard.fields.filter(field => field.type === 'number')) {
        for (const invalid of ['0', '-1', 'abc', 'NaN', 'Infinity', '1e999', '0x10', true, {}, [], null]) {
            const value = configuration();
            value.values[field.id] = invalid;
            assert.equal(shop.normaliseConfiguration(value, product), null, field.id + ': ' + invalid);
        }
    }
    const value = configuration();
    value.values.bore = ' 75,5 ';
    value.values.rockerRatio = '1.50';
    value.values.engineType = '  Škoda\n136  ';
    assert.deepEqual(shop.normaliseConfiguration(value, product).values, { ...engine, bore: '75.5', rockerRatio: '1.5' });
    value.values.engineType = 'x'.repeat(121);
    assert.equal(shop.normaliseConfiguration(value, product), null);
});

test('stored prices, contact details and injected option descriptions never survive loading', () => {
    const item = add([], configuration('new-320-320', 'large'))[0];
    item.price = 1;
    item.email = 'private@example.test';
    item.configuration.price = 1;
    item.configuration.description = '<script>bad()</script>';
    item.configuration.values.email = item.email;
    const cleaned = load([item]);
    assert.equal(shop.basketSummary(cleaned, catalog.products).subtotalCents, 1320000);
    assert.ok(!JSON.stringify(cleaned).includes('private@example.test'));
    assert.ok(!JSON.stringify(cleaned).includes('script'));
    assert.deepEqual(Object.keys(cleaned[0]), ['id', 'variant', 'quantity', 'lineId', 'configuration']);
    assert.deepEqual(Object.keys(cleaned[0].configuration), ['profile', 'bearing', 'values']);
    const repriced = catalog.products.map(p => p.id !== product.id ? p : { ...p, wizard: { ...p.wizard,
        profiles: p.wizard.profiles.map(profile => ({ ...profile, price: 15000 })) } });
    assert.equal(shop.basketSummary(cleaned, repriced).subtotalCents, 1500000);
});

test('malformed configured rows, forged quantities and duplicate instance IDs are rejected safely', () => {
    const item = add()[0];
    for (const invalid of [{ ...item, quantity: 2 }, { ...item, lineId: undefined }, { ...item, lineId: '<bad>' },
        { ...item, configuration: null }, { ...item, configuration: configuration('missing') }]) {
        assert.deepEqual(load([invalid]), []);
    }
    assert.deepEqual(load([item, item]), [item]);
    const items = [item];
    assert.equal(add(items), items);
    assert.equal(shop.addConfiguredItem(items, 'resonance-exhaust', configuration(), catalog.products, 'other'), items);
    const full = Array.from({ length: shop.MAX_ITEMS }, (_, index) => ({ ...item, lineId: 'line-' + index }));
    assert.equal(add(full, configuration(), 'extra'), full);
});

test('old standard baskets remain supported; removed camshafts prompt reconfiguration without guessing', () => {
    const ordinary = { id: 'resonance-exhaust', variant: '', quantity: 2 };
    const value = { version: 1, items: [ordinary, { id: 'camshaft-regrind', quantity: 1 }, { id: 'camshaft-new', quantity: 1 }] };
    assert.equal(shop.hasLegacyCamshafts(value), true);
    assert.deepEqual(shop.normaliseBasket(value, catalog.products), [ordinary]);
    assert.equal(shop.hasLegacyCamshafts({ version: 1, items: [ordinary] }), false);
    assert.equal(Boolean(shop.hasLegacyCamshafts(null)), false);
});

test('all languages include every selected specification in the basket summary and order email', () => {
    const items = add([], configuration('new-324-324', 'large'));
    const order = shop.orderDetails({ deliveryMethod: 'postal', email: 'example@example.test', fullName: 'Test', street: 'Test 1', city: 'Test', postcode: '12345', country: 'CZ' });
    for (const locale of catalog.languages) {
        const config = { locale, currency: 'CZK', text: texts[locale], products: catalog.products.map(p => ({ ...p, name: p.translations[locale].name })) };
        const details = shop.configurationDetails(items[0], product, config);
        assert.equal(details.length, 11);
        const body = shop.orderText(items, order, config);
        for (const [label, value] of details) {
            assert.ok(body.includes(label + ': ' + value), locale + ': ' + label);
        }
        for (const value of ['324°/ 324°', '7,5 / 7,2 mm', '40,5-40-30', 'Škoda 136', '75.5 mm', '1.45']) {
            assert.ok(body.includes(value), locale + ': ' + value);
        }
        assert.ok(!/undefined|null/.test(body));
        const decoded = new URL(shop.mailtoUrl(catalog.orderEmail, texts[locale].orderSubject, body));
        assert.equal(decoded.searchParams.get('body'), body);
    }
});

test('Czech camshaft order details describe the operation as Úkon: Výroba', () => {
    const items = add([], configuration('new-294-294', 'small'));
    const config = { locale: 'cs', currency: 'CZK', text: texts.cs,
        products: catalog.products.map(p => ({ ...p, name: p.translations.cs.name })) };
    const details = shop.configurationDetails(items[0], product, config);
    assert.deepEqual(details[0], ['Úkon', 'Výroba']);
    const body = shop.orderText(items, shop.orderDetails({ deliveryMethod: 'postal' }), config);
    assert.ok(body.includes('Úkon: Výroba'));
    assert.ok(!body.includes('Provedení:'));
    assert.ok(!body.includes('Nová hřídel'));
});

// Synthetic controls test the actual shared validator and wizard event handlers;
// no browser interaction, real basket changes, or email transmission is involved.
function node(initial = {}) {
    const handlers = new Map(), attrs = new Map(), classes = new Set();
    return Object.assign({ id: '', value: '', textContent: '', style: {}, disabled: false, required: false,
        classList: { toggle(name, on) { if (on) classes.add(name); else classes.delete(name); }, contains: name => classes.has(name) },
        getAttribute: name => attrs.get(name) ?? null, setAttribute: (name, value) => attrs.set(name, value),
        addEventListener(type, fn) { if (!handlers.has(type)) handlers.set(type, []); handlers.get(type).push(fn); },
        dispatchEvent(event) { for (const handler of handlers.get(event.type) || []) handler({ target: this, preventDefault() {}, ...event }); },
        fire(type, target) { for (const handler of handlers.get(type) || []) handler({ target: target || this, preventDefault() {} }); },
        closest: () => null, focus() { this.focused = true; },
    }, initial);
}

function wizardFixture(enhanced = true) {
    const form = node({ id: 'wizard-test' });
    const warnings = { 'profile-warning': node({ textContent: 'Required' }), 'bearing-warning': node({ textContent: 'Required' }) };
    const radios = product.wizard.profiles.map(profile => {
        const radio = node({ type: 'radio', name: 'profile', value: profile.id, required: true, checked: false });
        radio.setAttribute('data-warning-id', 'profile-warning');
        return radio;
    });
    const bearing = node({ name: 'bearing', type: 'select-one' });
    bearing.setAttribute('data-warning-id', 'bearing-warning');
    const fields = product.wizard.fields.map(field => {
        const input = node({ name: field.id, type: field.type, required: true,
            nextElementSibling: node({ textContent: field.type === 'number' ? 'Positive number required' : 'Required' }) });
        if (field.type === 'number') input.setAttribute('data-positive', '');
        return input;
    });
    const status = node({ hidden: true }), wrapper = node(), submit = node({ disabled: true });
    const added = [];
    const choices = { enabled: false, resets: 0, enable() { this.enabled = true; }, disable() { this.enabled = false; },
        setChoiceByValue(value) { assert.equal(value, ''); this.resets++; } };
    form.querySelectorAll = selector => { assert.equal(selector, '.validate-me'); return [...radios, bearing, ...fields]; };
    form.querySelector = selector => ({ '[data-bearing-fields]': wrapper, '.shop-wizard-status': status, 'button[type="submit"]': submit,
        '#profile-warning': warnings['profile-warning'], '#bearing-warning': warnings['bearing-warning'] })[selector];
    form.elements = { namedItem(name) { return name === 'profile' ? { value: radios.find(r => r.checked)?.value || '' }
        : name === 'bearing' ? bearing : fields.find(field => field.name === name); } };
    shop.initWizardForm(form, product, SiteForm, enhanced ? new Map([[bearing, choices]]) : new Map(), texts.cs,
        value => { added.push(value); return true; });
    return { form, radios, bearing, fields, wrapper, status, submit, choices, added, warnings,
        select(id) { radios.forEach(radio => { radio.checked = radio.value === id; });
            const selected = radios.find(radio => radio.checked); selected.fire('change'); form.fire('change', selected); },
        fill() { fields.forEach(field => { field.value = engine[field.name]; }); },
    };
}

test('wizard validates empty submissions with the shared warnings and focuses the radio group', () => {
    const f = wizardFixture();
    assert.equal(f.submit.disabled, false);
    f.form.fire('submit');
    assert.equal(f.added.length, 0);
    assert.equal(f.radios[0].focused, true);
    assert.equal(f.warnings['profile-warning'].style.display, 'block');
    for (const field of f.fields) assert.equal(field.getAttribute('aria-invalid'), 'true');
    f.select('regrind-262-248');
    assert.ok(f.radios.every(radio => radio.getAttribute('aria-invalid') === 'false'));
    assert.equal(f.warnings['profile-warning'].style.display, 'none');
});

for (const enhanced of [true, false]) {
    test(`conditional bearings and submission work with ${enhanced ? 'Choices' : 'native select fallback'}`, () => {
        const f = wizardFixture(enhanced);
        assert.equal(f.wrapper.hidden, true);
        assert.equal(f.bearing.disabled, true);
        f.fill();
        f.select('new-294-294');
        assert.equal(f.wrapper.hidden, false);
        assert.equal(f.bearing.required, true);
        assert.equal(f.bearing.disabled, false);
        if (enhanced) assert.equal(f.choices.enabled, true);
        f.form.fire('submit');
        assert.equal(f.added.length, 0);
        assert.equal(f.bearing.getAttribute('aria-invalid'), 'true');
        f.bearing.value = 'large';
        f.bearing.fire('change');
        f.form.fire('submit');
        assert.equal(f.added.length, 1);
        assert.equal(f.added[0].bearing, 'large');
        assert.equal(f.status.textContent, texts.cs.configuredAdded);
        f.select('regrind-272-266');
        assert.equal(f.bearing.value, '');
        assert.equal(f.bearing.disabled, true);
        assert.equal(f.bearing.required, false);
        assert.equal(f.wrapper.hidden, true);
        if (enhanced) assert.equal(f.choices.enabled, false);
        assert.deepEqual(Object.fromEntries(f.fields.map(field => [field.name, field.value])), engine);
        f.form.fire('submit');
        assert.equal(f.added.length, 2);
        assert.equal(f.added[1].bearing, '');
        f.select('new-320-320');
        f.form.fire('submit');
        assert.equal(f.added.length, 2); // Must choose bearings again after a regrind.
    });
}

test('zero or missing engine dimensions block submission and valid replacements clear inline warnings', () => {
    const f = wizardFixture();
    f.select('regrind-262-248');
    f.fill();
    for (const field of f.fields) {
        const original = field.value;
        field.value = field.type === 'number' ? '0' : '';
        field.fire('input');
        assert.equal(field.getAttribute('aria-invalid'), 'true');
        f.form.fire('submit');
        assert.equal(f.added.length, 0);
        field.value = original;
        field.fire('input');
        assert.equal(field.getAttribute('aria-invalid'), 'false');
    }
    f.form.fire('submit');
    f.form.fire('submit');
    assert.equal(f.added.length, 2);
});
