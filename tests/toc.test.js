const { test } = require('node:test');
const assert = require('node:assert/strict');
const { initProductContents, initShopSidebar } = require('../shop.js');

function element(id = '', height = 0) {
    const classes = new Set();
    return {
        id, children: [], attributes: {}, events: {}, computed: {}, scrollTop: 0, scrollHeight: 700,
        rect: { top: 0, bottom: height, height },
        classList: {
            toggle(name, enabled) { if (enabled) classes.add(name); else classes.delete(name); },
            contains(name) { return classes.has(name); },
        },
        style: { setProperty(name, value) { this[name] = value; } },
        getAttribute(name) { return this.attributes[name]; },
        setAttribute(name, value) { this.attributes[name] = value; },
        removeAttribute(name) { delete this.attributes[name]; },
        addEventListener(name, callback) { this.events[name] = callback; },
        getBoundingClientRect() { return this.rect; },
    };
}

function contentsFixture(hash = '') {
    const nav = element('nav', 120);
    nav.rect = { top: 100, bottom: 220, height: 120 };
    const links = ['one', 'two', 'three'].map((id, index) => {
        const link = element(id, 40);
        link.attributes.href = '#' + id;
        link.rect = { top: 110 + index * 80, bottom: 150 + index * 80, height: 40 };
        return link;
    });
    nav.querySelectorAll = () => links;
    const products = links.map(link => element(link.id, 1000));
    const doc = {
        querySelector: () => nav,
        getElementById: id => products.find(product => product.id === id),
    };
    const viewport = {
        location: { hash }, events: {},
        addEventListener(name, callback) { this.events[name] = callback; },
        IntersectionObserver: class {
            constructor(callback, options) { this.callback = callback; this.options = options; this.observed = []; }
            observe(node) { this.observed.push(node); }
        },
    };
    return { nav, links, products, doc, viewport };
}

test('product contents uses the blog scroll spy and scrolls only its own list', () => {
    const fixture = contentsFixture();
    const observer = initProductContents(fixture.doc, fixture.viewport);
    assert.deepEqual(observer.observed, fixture.products);
    assert.deepEqual(observer.options, { root: null, rootMargin: '-45% 0px -45% 0px', threshold: 0 });
    observer.callback([{ target: fixture.products[2], isIntersecting: true }]);
    assert.equal(fixture.links[2].getAttribute('aria-current'), 'location');
    assert.equal(fixture.links[2].classList.contains('is-active'), true);
    assert.equal(fixture.nav.scrollTop, 90);
    observer.callback([{ target: fixture.products[2], isIntersecting: false },
        { target: fixture.products[0], isIntersecting: true }]);
    assert.equal(fixture.links[0].getAttribute('aria-current'), 'location');
    assert.equal(fixture.links[2].getAttribute('aria-current'), undefined);
    assert.equal(fixture.links[2].classList.contains('is-active'), false);
});

test('deep links, hash navigation and native contents clicks work without an observer', () => {
    const { doc, viewport, links } = contentsFixture('#two');
    delete viewport.IntersectionObserver;
    initProductContents(doc, viewport);
    assert.equal(links[1].getAttribute('aria-current'), 'location');
    links[0].events.click();
    assert.equal(links[0].getAttribute('aria-current'), 'location');
    viewport.location.hash = '#three';
    viewport.events.hashchange();
    assert.equal(links[2].getAttribute('aria-current'), 'location');
    viewport.location.hash = '#order';
    viewport.events.hashchange();
    assert.equal(links[2].getAttribute('aria-current'), 'location');
});

function sidebarFixture() {
    const panels = element('panels'), toc = element('shop-contents'), basket = element('basket');
    const items = element('basket-items'), title = element('title', 20), nav = element('nav');
    const summary = element('summary', 300);
    const chrome = { paddingTop: '25px', paddingBottom: '25px' };
    toc.computed = { ...chrome };
    basket.computed = { ...chrome, top: '104px' };
    title.computed.marginBottom = '15px';
    basket.children = [title, items, summary];
    toc.querySelector = selector => selector === '.toc-title' ? title : nav;
    const nodes = { 'shop-contents': toc, basket, 'basket-items': items };
    const doc = { querySelector: () => panels, getElementById: id => nodes[id] };
    const viewport = {
        innerHeight: 1000, desktop: true, events: {}, frames: [],
        getComputedStyle: node => node.computed,
        matchMedia() { return { matches: this.desktop }; },
        addEventListener(name, callback) { this.events[name] = callback; },
        requestAnimationFrame(callback) { this.frames.push(callback); return this.frames.length; },
    };
    const update = initShopSidebar(doc, viewport);
    viewport.frames.shift()();
    return { panels, basket, items, summary, viewport, update };
}

test('sidebar pins both panels when they fit, reserving room for basket items', () => {
    const { panels, basket, items, update } = sidebarFixture();
    assert.equal(panels.classList.contains('is-sticky'), true);
    assert.equal(basket.classList.contains('is-inline'), false);
    assert.equal(panels.style['--shop-toc-height'], '350px');
    items.children.push(element('item', 200));
    update();
    assert.equal(panels.classList.contains('is-sticky'), true);
    assert.equal(basket.classList.contains('is-inline'), false);
});

test('contents gets more space without taking the basket minimum or growing without a cap', () => {
    const { panels, items, viewport, update } = sidebarFixture();
    items.children.push(element('item', 200));
    viewport.innerHeight = 900;
    update();
    assert.equal(panels.classList.contains('is-sticky'), true);
    // 776px available minus 505px for the basket and a 20px gap.
    assert.equal(panels.style['--shop-toc-height'], '251px');
    viewport.innerHeight = 1200;
    update();
    assert.equal(panels.style['--shop-toc-height'], '400px');
});

test('short screens release the contents first and never clip a tall summary', () => {
    const { panels, basket, items, viewport, update } = sidebarFixture();
    items.children.push(element('item', 200));
    viewport.innerHeight = 780;
    update();
    assert.equal(panels.classList.contains('is-sticky'), false);
    assert.equal(basket.classList.contains('is-inline'), false);
    viewport.innerHeight = 400;
    update();
    assert.equal(panels.classList.contains('is-sticky'), false);
    assert.equal(basket.classList.contains('is-inline'), true);
    viewport.desktop = false;
    update();
    assert.equal(panels.classList.contains('is-sticky'), false);
    assert.equal(basket.classList.contains('is-inline'), false);
});

test('sidebar responds to longer notices and coalesces resize work', () => {
    const { panels, summary, viewport, update } = sidebarFixture();
    summary.rect.height = 700;
    update();
    assert.equal(panels.classList.contains('is-sticky'), false);
    viewport.events.resize();
    viewport.events.resize();
    assert.equal(viewport.frames.length, 1);
});

test('contents and sidebar enhancement safely skip pages without their markup', () => {
    const doc = { querySelector: () => null, getElementById: () => null };
    assert.equal(initProductContents(doc, {}), undefined);
    assert.equal(initShopSidebar(doc, {}), undefined);
});
