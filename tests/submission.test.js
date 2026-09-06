const { test } = require('node:test');
const assert = require('node:assert/strict');
const { initSubmission, initAttachments, MAX_ATTACHMENT_BYTES, submissionText } = require('../form.js');
const { removeSubmittedItems, sendOrder } = require('../shop.js');

function element() {
    const target = new EventTarget(), attributes = new Map();
    return Object.assign(target, { style: {}, textContent: '', children: [],
        setAttribute: (name, value) => attributes.set(name, value),
        removeAttribute: name => attributes.delete(name),
        getAttribute: name => attributes.get(name),
        replaceChildren(...children) { this.children = children; },
    });
}

function formFixture(t, extra = {}) {
    const form = element(), button = element(), message = element();
    button.textContent = 'Objednat'; button.disabled = false;
    const input = { value: 'Keep me', disabled: false }, disabledInput = { disabled: true };
    form.ownerDocument = { createElement: element };
    form.querySelector = () => button;
    form.querySelectorAll = () => [input, disabledInput, button];
    form.reset = () => { input.value = ''; form.dispatchEvent(new Event('reset')); };
    t.mock.method(global, 'FormData', function () { return new Map([['fullName', input.value]]); });
    const options = { validation: { validate: () => true }, attachments: { validate: () => true, reset() {} },
        text: submissionText('cs'), message, request: async () => ({ status: 'success' }), ...extra };
    const submission = initSubmission(form, options);
    return { form, button, input, disabledInput, message, submission, options };
}

test('shared submission has one pending request, locks fields, restores initial disabled states, and resets on success', async t => {
    let resolve, requests = 0, submitted;
    const fixture = formFixture(t, {
        request: data => { requests++; assert.equal(data.get('fullName'), 'Keep me'); return new Promise(done => { resolve = done; }); },
        prepareData: () => 'snapshot', onSuccess: (result, context) => { submitted = context; },
    });
    const { submission, form, input, button, disabledInput, message } = fixture;
    const pending = submission.submit(new Event('submit'));
    assert.equal(submission.busy, true);
    assert.equal(form.getAttribute('aria-busy'), 'true');
    assert.equal(button.disabled, true); assert.equal(input.disabled, true);
    assert.equal(button.textContent, submissionText('cs').emailSubmissionSendingBtnText);
    await submission.submit(new Event('submit'));
    assert.equal(requests, 1);
    resolve({ status: 'success' }); await pending;
    assert.equal(submission.busy, false); assert.equal(button.disabled, false);
    assert.equal(disabledInput.disabled, true); assert.equal(input.disabled, false);
    assert.equal(button.textContent, 'Objednat'); assert.equal(input.value, '');
    assert.equal(submitted, 'snapshot'); assert.equal(message.children[0].className, 'msg-success');
    assert.equal(message.getAttribute('aria-live'), 'polite');
});

test('failed submission retains field data and uses safe text feedback', async t => {
    const { submission, input, button, message } = formFixture(t, {
        request: async () => { throw new Error('server diagnostic'); }, errorText: () => '<Keep & retry>',
    });
    await submission.submit(new Event('submit'));
    assert.equal(input.value, 'Keep me'); assert.equal(button.disabled, false);
    assert.equal(message.children[0].textContent, '<Keep & retry>');
    assert.equal(message.children[0].className, 'msg-error');
});

test('a received order with a failed customer recap shows distinct success feedback and resets', async t => {
    let result;
    const { submission, input, message } = formFixture(t, {
        request: async () => ({ status: 'success', customerEmail: 'failed' }),
        onSuccess: value => { result = value; },
        successText: value => value.customerEmail === 'failed' ? 'Order received; wait for our reply. Do not order again.' : 'Sent',
    });
    await submission.submit(new Event('submit'));
    assert.equal(result.customerEmail, 'failed');
    assert.equal(input.value, '');
    assert.equal(message.children[0].className, 'msg-success');
    assert.match(message.children[0].textContent, /Do not order again/);
});

test('empty basket, invalid fields and oversized attachments never start a request', async t => {
    for (const extra of [{ canSubmit: () => false }, { validation: { validate: () => false } }, { attachments: { validate: () => false } }]) {
        const { submission } = formFixture(t, { ...extra, request: () => assert.fail('Must not send') });
        await submission.submit(new Event('submit'));
        assert.equal(submission.busy, false);
    }
});

test('contact form retains status-only POST response compatibility', async t => {
    let called;
    t.mock.method(global, 'fetch', async (url, options) => { called = [url, options]; return { ok: true }; });
    const { submission, message } = formFixture(t, { request: undefined, endpoint: '/backend/contact_form_handler.php' });
    await submission.submit(new Event('submit'));
    assert.equal(called[0], '/backend/contact_form_handler.php');
    assert.equal(called[1].method, 'POST'); assert.equal(called[1].credentials, 'same-origin');
    assert.equal(message.children[0].className, 'msg-success');
});

test('attachment controls enforce the same combined 8 MB limit, display filenames, and reset labels', async () => {
    const form = element(), errors = [];
    const inputs = Array.from({ length: 3 }, () => {
        const input = element(), label = element(), name = element();
        input.files = []; input.parentElement = label; label.querySelector = () => name;
        Object.defineProperty(input, 'value', { set() { input.files = []; } });
        return input;
    });
    form.querySelectorAll = () => inputs;
    const uploads = initAttachments(form, { text: submissionText('cs'), onError: text => errors.push(text) });
    inputs[0].files = [{ name: 'Instructions.txt', size: MAX_ATTACHMENT_BYTES }];
    inputs[0].dispatchEvent(new Event('change'));
    assert.equal(inputs[0].parentElement.querySelector().textContent, 'Instructions.txt');
    assert.equal(uploads.validate(), true);
    inputs[1].files = [{ name: 'Too many bytes.txt', size: 1 }];
    inputs[1].dispatchEvent(new Event('change'));
    assert.equal(inputs[1].files.length, 0); assert.equal(errors.length, 1);
    assert.equal(inputs[0].files.length, 1);
    inputs.forEach(input => { input.value = ''; });
    form.dispatchEvent(new Event('reset')); await Promise.resolve();
    assert.equal(inputs[0].parentElement.querySelector().textContent, submissionText('cs').selectFile);
    assert.equal(inputs[0].parentElement.style.borderColor, '');
});

test('successful submission removes only submitted quantities and configured instances', () => {
    const row = (id, quantity, other = {}) => ({ id, variant: '', quantity, ...other });
    const submitted = [row('standard', 2), row('wizard', 1, { lineId: 'first' })];
    const current = [row('standard', 5), ...submitted.slice(1), row('wizard', 1, { lineId: 'second' }), row('new', 1)];
    assert.deepEqual(removeSubmittedItems(current, submitted), [row('standard', 3), row('wizard', 1, { lineId: 'second' }), row('new', 1)]);
    assert.deepEqual(removeSubmittedItems(submitted, submitted), []);
});

test('order protocol uses a same-origin CSRF session and requires an explicit matching delivery receipt', async () => {
    const data = new FormData(); data.set('requestId', 'test-request');
    const calls = [];
    const fetcher = async (url, options) => {
        calls.push([url, options]);
        return { ok: true, json: async () => options.method === 'GET'
            ? { status: 'ready', token: 'a'.repeat(64) } : { status: 'success', reference: 'test-request' } };
    };
    assert.equal((await sendOrder('/backend/order_form_handler.php', data, fetcher)).status, 'success');
    assert.equal(calls.length, 2);
    assert.equal(data.get('csrfToken'), 'a'.repeat(64));
    assert.equal(calls[1][1].body, data);
    assert.ok(calls.every(([, options]) => options.credentials === 'same-origin' && options.cache === 'no-store'));
});

test('order protocol never mistakes a static PHP file or an HTTP error for success', async () => {
    for (const response of [{ ok: true, json: async () => { throw new Error('Not JSON'); } },
        { ok: false, json: async () => ({ code: 'catalog_changed' }) },
        { ok: true, json: async () => ({ status: 'success' }) }]) {
        await assert.rejects(sendOrder('/backend/order_form_handler.php', new FormData(), async () => response));
    }
    const data = new FormData(); data.set('requestId', 'right');
    await assert.rejects(sendOrder('/backend/order_form_handler.php', data, async (url, options) => ({ ok: true,
        json: async () => options.method === 'GET' ? { status: 'ready', token: 'a'.repeat(64) } : { status: 'success', reference: 'wrong' },
    })), /send_failed/);
});
