const { test } = require('node:test');
const assert = require('node:assert/strict');
const shop = require('../shop.js');

function fixture(value = '1') {
    const input = Object.assign(new EventTarget(), { value, disabled: true, readOnly: false });
    Object.defineProperty(input, 'valueAsNumber', { get() { return this.value === '' ? NaN : Number(this.value); } });
    const buttons = [-1, 1].map(change => Object.assign(new EventTarget(), {
        dataset: { orderChange: String(change) }, disabled: true,
    }));
    const form = {
        querySelector(selector) { assert.equal(selector, '[data-order-quantity]'); return input; },
        querySelectorAll(selector) { assert.equal(selector, '[data-order-change]'); return buttons; },
    };
    const events = [];
    input.addEventListener('input', event => events.push(event));
    const sync = shop.initOrderQuantitySpinner(form);
    const click = index => buttons[index].dispatchEvent(new Event('click'));
    return { input, buttons, events, sync, click };
}

test('draft spinner is disabled until an option opens the subform and never goes below one', () => {
    const { input, buttons, events, sync, click } = fixture();
    assert.ok(buttons.every(button => button.disabled));
    click(1);
    assert.equal(input.value, '1');
    assert.equal(events.length, 0);
    input.disabled = false;
    sync();
    assert.equal(buttons[0].disabled, true);
    assert.equal(buttons[1].disabled, false);
    click(1);
    assert.equal(input.value, '2');
    assert.ok(buttons.every(button => !button.disabled));
    click(0);
    click(0);
    assert.equal(input.value, '1');
    assert.equal(events.length, 2);
    assert.ok(events.every(event => event.type === 'input' && event.bubbles));
});

test('draft spinner honors 9999 after clicks and direct typing', () => {
    const { input, buttons, sync, click } = fixture('9998');
    input.disabled = false;
    sync();
    click(1);
    click(1);
    assert.equal(input.value, '9999');
    assert.equal(buttons[1].disabled, true);
    click(0);
    assert.equal(input.value, '9998');
    assert.equal(buttons[1].disabled, false);
    input.value = '9999';
    input.dispatchEvent(new Event('input'));
    assert.equal(buttons[1].disabled, true);
    input.value = '1';
    input.dispatchEvent(new Event('change'));
    assert.equal(buttons[0].disabled, true);
    assert.equal(buttons[1].disabled, false);
});

test('draft spinner repairs blank input without bypassing disabled or read-only state', () => {
    const { input, buttons, sync, click } = fixture('');
    input.disabled = false;
    sync();
    click(1);
    assert.equal(input.value, '1');
    input.readOnly = true;
    sync();
    assert.ok(buttons.every(button => button.disabled));
    click(1);
    assert.equal(input.value, '1');
    input.readOnly = false;
    input.disabled = true;
    sync();
    click(1);
    assert.equal(input.value, '1');
});
