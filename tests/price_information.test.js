const { test } = require('node:test');
const assert = require('node:assert/strict');
const { initPriceInformation } = require('../shop.js');

function fixture() {
    const eventTarget = () => ({
        events: {},
        addEventListener(name, handler) { this.events[name] = handler; },
    });
    const node = rect => ({
        ...eventTarget(), rect, style: {}, attributes: {}, hidden: true,
        getBoundingClientRect() { return this.rect; },
        setAttribute(name, value) { this.attributes[name] = value; },
        contains(target) { return target === this || target?.parent === this; },
    });
    const toggle = node({ top: 600, bottom: 632, right: 950 });
    const popup = node({ width: 340, height: 220 });
    const basket = node({});
    const nodes = { 'basket-price-info-toggle': toggle, 'basket-price-info': popup, basket };
    const doc = { ...eventTarget(), documentElement: { clientWidth: 1000 },
        getElementById: id => nodes[id], activeElement: null };
    const timers = new Map(), frames = [];
    let timerId = 0;
    const viewport = {
        ...eventTarget(), innerHeight: 800,
        setTimeout(callback) { const id = ++timerId; timers.set(id, callback); return id; },
        clearTimeout(id) { timers.delete(id); },
        requestAnimationFrame(callback) { frames.push(callback); return frames.length; },
        ResizeObserver: class { constructor(callback) { this.callback = callback; } observe() {} },
    };
    const api = initPriceInformation(doc, viewport);
    const flushTimers = () => { const pending = [...timers.values()]; timers.clear(); pending.forEach(fn => fn()); };
    const flushFrames = () => { while (frames.length) frames.shift()(); };
    return { toggle, popup, doc, viewport, api, flushTimers, flushFrames };
}

test('keyboard focus reveals the notes, Escape closes them without moving focus', () => {
    const { toggle, popup, doc, flushTimers } = fixture();
    assert.equal(popup.hidden, true);
    doc.activeElement = toggle;
    toggle.events.focus();
    assert.equal(popup.hidden, false);
    assert.equal(toggle.attributes['aria-expanded'], 'true');
    let prevented = false;
    doc.events.keydown({ key: 'Escape', preventDefault() { prevented = true; } });
    assert.equal(popup.hidden, true);
    assert.equal(toggle.attributes['aria-expanded'], 'false');
    assert.equal(doc.activeElement, toggle);
    assert.equal(prevented, true);
    toggle.events.focus();
    doc.activeElement = null;
    toggle.events.blur();
    flushTimers();
    assert.equal(popup.hidden, true);
});

test('click or tap pins focused information, then closes on a second click or outside', () => {
    const { toggle, popup, doc, flushTimers } = fixture();
    toggle.events.pointerenter({ pointerType: 'touch' });
    assert.equal(popup.hidden, true);
    toggle.events.focus();
    toggle.events.click();
    toggle.events.pointerleave();
    toggle.events.blur();
    flushTimers();
    assert.equal(popup.hidden, false);
    doc.events.pointerdown({ target: { parent: popup } });
    assert.equal(popup.hidden, false);
    toggle.events.click();
    assert.equal(popup.hidden, true);
    toggle.events.click();
    doc.events.pointerdown({ target: {} });
    assert.equal(popup.hidden, true);
});

test('hovering from the icon into the text keeps it readable', () => {
    const { toggle, popup, flushTimers } = fixture();
    toggle.events.pointerenter({ pointerType: 'mouse' });
    assert.equal(popup.hidden, false);
    toggle.events.pointerleave();
    popup.events.pointerenter({ pointerType: 'mouse' });
    flushTimers();
    assert.equal(popup.hidden, false);
    popup.events.pointerleave();
    flushTimers();
    assert.equal(popup.hidden, true);
});

test('information sits above the icon and stays within narrow or short viewports', () => {
    const { toggle, popup, doc, viewport, api, flushFrames } = fixture();
    api.show();
    assert.deepEqual(popup.style, { left: '610px', top: '372px' });
    doc.documentElement.clientWidth = 390;
    viewport.innerHeight = 500;
    toggle.rect = { top: 30, bottom: 62, right: 357 };
    viewport.events.resize();
    flushFrames();
    assert.deepEqual(popup.style, { left: '17px', top: '70px' });
    toggle.rect.right = 30;
    toggle.rect.top = 200;
    toggle.rect.bottom = 232;
    popup.rect.height = 476;
    api.position();
    assert.deepEqual(popup.style, { left: '12px', top: '12px' });
});

test('scrolling keeps the panel anchored, or dismisses it when the icon leaves view', () => {
    const { toggle, popup, viewport, api, flushFrames } = fixture();
    api.show();
    toggle.rect.top = 500;
    toggle.rect.bottom = 532;
    viewport.events.scroll();
    flushFrames();
    assert.equal(popup.style.top, '272px');
    toggle.rect.top = -50;
    toggle.rect.bottom = -18;
    viewport.events.scroll();
    flushFrames();
    assert.equal(popup.hidden, true);
});

test('pages without basket information do not need enhancement', () => {
    assert.equal(initPriceInformation({ getElementById: () => null }, {}), undefined);
});
