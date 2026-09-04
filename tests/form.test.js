const { test } = require('node:test');
const assert = require('node:assert/strict');
const { initValidation } = require('../form.js');

// Synthetic form controls exercise the shared behavior without a live browser,
// real customer data, network requests, or changes to a saved basket.
function node() {
    const target = new EventTarget();
    const attrs = new Map();
    const classes = new Set();
    return Object.assign(target, {
        id: '', style: {}, textContent: '',
        setAttribute: (name, value) => attrs.set(name, value),
        getAttribute: name => attrs.get(name) ?? null,
        classList: {
            toggle(name, force) { if (force) classes.add(name); else classes.delete(name); },
            contains: name => classes.has(name),
        },
    });
}

function fixture(kind = 'shop', messages = {}) {
    const copy = {
        required: 'Toto pole je povinné.', email: 'Zadejte platný email.',
        phone: 'Zadejte platné telefonní číslo.', year: 'Zadejte platný rok.', ...messages,
    };
    const form = node();
    form.id = kind === 'shop' ? 'shop-order-form' : 'inquiryForm';
    const fields = [
        { name: kind === 'shop' ? 'fullName' : 'fullname', value: 'Test Customer', required: true },
        { name: 'email', type: 'email', value: 'customer@example.test', required: true },
        { name: 'phone', type: kind === 'shop' ? 'tel' : 'text', value: '+420 604 123 456', required: kind !== 'shop' },
        { name: 'city', value: 'Test City', required: true },
        ...(kind === 'shop' ? [
            { name: 'street', value: 'Test Street 1', required: true },
            { name: 'postcode', value: '123 45', required: true },
            { name: 'country', value: 'Test Country', required: true },
        ] : [{ name: 'year', type: 'number', value: '', required: false }]),
    ].map(settings => {
        const input = Object.assign(node(), { type: 'text', disabled: false, ...settings });
        const warning = node();
        warning.textContent = copy[input.name] || copy.required;
        warning.style.display = 'none';
        input.nextElementSibling = warning;
        input.focus = () => { form.focused = input; };
        return input;
    });
    form.querySelectorAll = selector => {
        assert.equal(selector, '.validate-me');
        return fields;
    };
    fields[0].setAttribute('aria-describedby', 'existing-hint');
    const validation = initValidation(form);
    return { form, fields, validation, copy, get: name => fields.find(field => field.name === name) };
}

function edit(input, value, type = 'input') {
    input.value = value;
    input.dispatchEvent(new Event(type));
}

function assertWarning(input, expected) {
    assert.equal(input.classList.contains('input-warning'), Boolean(expected));
    assert.equal(input.getAttribute('aria-invalid'), String(Boolean(expected)));
    assert.equal(input.nextElementSibling.style.display, expected ? 'block' : 'none');
    if (expected) assert.equal(input.nextElementSibling.textContent, expected);
}

test('enhanced selects use explicit warning targets and focus the visible accessible control', () => {
    const form = node();
    form.id = 'wizard-form';
    const select = Object.assign(node(), { name: 'bearing', type: 'select-one', value: '', required: true, disabled: false });
    const warning = node();
    warning.id = 'bearing-warning';
    warning.textContent = 'Choose bearings.';
    select.setAttribute('data-warning-id', warning.id);
    // The warning is not the select's next sibling after Choices enhances it.
    select.nextElementSibling = null;
    const visible = node(), inner = node();
    select.closest = selector => { assert.equal(selector, '.choices'); return visible; };
    visible.querySelector = selector => { assert.equal(selector, '.choices__inner'); return inner; };
    visible.focus = () => { form.focused = visible; };
    form.querySelectorAll = () => [select];
    form.querySelector = selector => { assert.equal(selector, '#bearing-warning'); return warning; };
    const validation = initValidation(form);
    assert.equal(validation.validate(), false);
    assert.equal(form.focused, visible);
    assert.equal(visible.getAttribute('aria-invalid'), 'true');
    assert.equal(visible.getAttribute('aria-describedby'), 'bearing-warning');
    assert.equal(inner.classList.contains('input-warning'), true);
    edit(select, 'small', 'change');
    assert.equal(visible.getAttribute('aria-invalid'), 'false');
    assert.equal(inner.classList.contains('input-warning'), false);
    assert.equal(warning.style.display, 'none');
});

for (const kind of ['main', 'shop']) {
    test(`${kind}: fields use localized inline warnings on input and change`, () => {
        const { fields, validation, copy } = fixture(kind);
        assert.ok(fields.every(field => field.nextElementSibling.style.display === 'none'));
        edit(fields[0], '');
        assertWarning(fields[0], copy.required);
        edit(fields[0], 'Another Customer', 'change');
        assertWarning(fields[0], '');
        assert.equal(validation.validate(), true);
    });

    test(`${kind}: submission validates every field and focuses the first invalid one`, () => {
        const { form, fields, validation, copy } = fixture(kind);
        fields.forEach(input => { input.value = ''; });
        assert.equal(validation.validate(), false);
        assert.equal(form.focused, fields[0]);
        for (const input of fields) assertWarning(input, input.required ? copy.required : '');
    });

    test(`${kind}: required and format messages do not overwrite each other`, () => {
        const { get, copy } = fixture(kind);
        const email = get('email');
        edit(email, '');
        assertWarning(email, copy.required);
        for (const value of ['invalid', 'customer@', 'customer@example', 'customer@@example.test', 'bad address@example.test']) {
            edit(email, value);
            assertWarning(email, copy.email);
        }
        edit(email, 'customer@example.test');
        assertWarning(email, '');
    });

    test(`${kind}: phone validation uses the same format rule`, () => {
        const { get, copy } = fixture(kind);
        const phone = get('phone');
        for (const value of ['abc', '12345', '+420 invalid']) {
            edit(phone, value);
            assertWarning(phone, copy.phone);
        }
        edit(phone, '+420 604 123 456');
        assertWarning(phone, '');
        edit(phone, '');
        assertWarning(phone, kind === 'main' ? copy.required : '');
    });

    test(`${kind}: whitespace-only required fields fail and valid submissions are trimmed`, () => {
        const { fields, validation, copy } = fixture(kind);
        fields[0].value = '   ';
        assert.equal(validation.validate(), false);
        assertWarning(fields[0], copy.required);
        fields[0].value = '  Test Customer  ';
        assert.equal(validation.validate(), true);
        assert.equal(fields[0].value, 'Test Customer');
        assertWarning(fields[0], '');
    });

    test(`${kind}: reset clears warning borders and screen-reader error state`, () => {
        const { form, fields, validation } = fixture(kind);
        fields.forEach(field => { field.value = ''; });
        assert.equal(validation.validate(), false);
        form.dispatchEvent(new Event('reset'));
        for (const field of fields) assertWarning(field, '');
    });

    test(`${kind}: warnings are associated with their controls without losing existing hints`, () => {
        const { fields, form } = fixture(kind);
        for (const field of fields) {
            assert.equal(field.id, `${form.id}-${field.name}`);
            assert.equal(field.nextElementSibling.id, `${field.id}-warning`);
            assert.equal(field.nextElementSibling.getAttribute('aria-live'), 'polite');
            assert.ok(field.getAttribute('aria-describedby').split(' ').includes(field.nextElementSibling.id));
        }
        assert.ok(fields[0].getAttribute('aria-describedby').startsWith('existing-hint '));
    });
}

test('shop: optional phone can be blank without blocking the order', () => {
    const { get, validation } = fixture();
    get('phone').value = '';
    assert.equal(validation.validate(), true);
});

test('main: optional year retains its lower bound and handles malformed numeric input', () => {
    const { get, copy } = fixture('main');
    const year = get('year');
    edit(year, '1899');
    assertWarning(year, copy.year);
    edit(year, '1900');
    assertWarning(year, '');
    year.validity = { valid: false, badInput: true };
    edit(year, '');
    assertWarning(year, copy.year);
    year.validity = { valid: true, badInput: false };
    edit(year, '');
    assertWarning(year, '');
});

test('main: submit does not clear a numeric badInput error by reassigning its value', () => {
    const { get, validation, copy } = fixture('main');
    const year = get('year');
    year.validity = { valid: false, badInput: true };
    Object.defineProperty(year, 'value', {
        get: () => '',
        set: () => { year.validity = { valid: true, badInput: false }; },
    });
    assert.equal(validation.validate(), false);
    assertWarning(year, copy.year);
});

test('validation respects browser constraints without calling reportValidity', () => {
    const { fields, validation, copy } = fixture();
    fields[0].validity = { valid: false };
    assert.equal(validation.validate(), false);
    assertWarning(fields[0], copy.required);
    fields[0].disabled = true;
    assert.equal(validation.validate(), true);
    assertWarning(fields[0], '');
});

test('messages come from localized markup, never hard-coded Czech errors', () => {
    const { get, fields } = fixture('shop', {
        required: 'This field is mandatory.', email: 'Enter a valid email.',
    });
    edit(fields[0], '');
    assertWarning(fields[0], 'This field is mandatory.');
    edit(get('email'), 'bad');
    assertWarning(get('email'), 'Enter a valid email.');
});

test('missing form needs no initialization', () => {
    assert.equal(initValidation(null), null);
});
