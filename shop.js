/* Browser-only basket. Never persist customer contact or delivery details. */
(function (root) {
    'use strict';

    const STORAGE_KEY = 'muckova-shop-basket';
    const MAX_QUANTITY = 9999;

    function lineKey(id, variant = '') { return id + ':' + variant; }

    function normaliseBasket(value, products) {
        const rows = value && value.version === 1 && Array.isArray(value.items) ? value.items : [];
        const catalog = new Map(products.map(product => [product.id, product]));
        const items = new Map();
        rows.slice(0, 500).forEach(row => {
            if (!row || typeof row !== 'object') return;
            const product = catalog.get(row.id);
            if (!product || !Number.isInteger(row.quantity) || row.quantity < 1) return;
            const variant = typeof row.variant === 'string' ? row.variant : '';
            if (product.variants.length ? !product.variants.some(v => v.id === variant) : variant !== '') return;
            const key = lineKey(product.id, variant);
            const quantity = Math.min(MAX_QUANTITY, row.quantity + (items.get(key)?.quantity || 0));
            items.set(key, { id: product.id, variant, quantity });
        });
        return [...items.values()];
    }

    function setQuantity(items, id, variant, quantity, products) {
        if (!Number.isFinite(quantity)) return items;
        const key = lineKey(id, variant);
        const next = items.map(item => lineKey(item.id, item.variant) === key ? { id, variant, quantity: Math.min(MAX_QUANTITY, Math.floor(quantity)) } : item);
        if (quantity > 0 && !items.some(item => lineKey(item.id, item.variant) === key)) {
            next.push({ id, variant, quantity: Math.min(MAX_QUANTITY, Math.floor(quantity)) });
        }
        return normaliseBasket({ version: 1, items: next }, products);
    }

    function basketSummary(items, products) {
        const catalog = new Map(products.map(product => [product.id, product]));
        return items.reduce((result, item) => {
            const product = catalog.get(item.id);
            if (!product) return result;
            result.count += item.quantity;
            if (product.priceType === 'fixed') result.subtotalCents += product.price * 100 * item.quantity;
            else result.quotedCount += item.quantity;
            return result;
        }, { count: 0, subtotalCents: 0, quotedCount: 0 });
    }

    function orderDetails(values) {
        const read = name => String(values[name] || '').trim();
        if (read('deliveryMethod') !== 'postal') throw new Error('Unsupported delivery method');
        return {
            email: read('email'),
            phone: read('phone'),
            delivery: { method: 'postal', address: {
                fullName: read('fullName'), company: read('company'), street: read('street'),
                city: read('city'), postcode: read('postcode'), country: read('country'),
            } },
            notes: read('notes'),
        };
    }

    function formatPrice(product, config, quantity = 1) {
        if (product.priceType === 'quote') return config.text.quote;
        const amount = new Intl.NumberFormat(config.locale, { style: 'currency', currency: config.currency, maximumFractionDigits: 0 }).format(product.price * quantity);
        return product.priceType === 'from' ? config.text.from + ' ' + amount : amount;
    }

    function orderText(items, details, config) {
        const t = config.text;
        const products = new Map(config.products.map(product => [product.id, product]));
        const summary = basketSummary(items, config.products);
        const money = new Intl.NumberFormat(config.locale, { style: 'currency', currency: config.currency, maximumFractionDigits: 0 });
        const lines = items.map(item => {
            const product = products.get(item.id);
            const variant = product.variants.find(v => v.id === item.variant);
            return `${item.quantity} × ${product.name}${variant ? ' / ' + variant.label : ''} [${product.id}${item.variant ? ':' + item.variant : ''}] — ${formatPrice(product, config, item.quantity)}`;
        });
        const address = details.delivery.address;
        return [
            t.orderSubject, '', ...lines, '',
            t.subtotal + ': ' + money.format(summary.subtotalCents / 100),
            ...(summary.quotedCount ? [t.quoteNotice] : []), t.deliveryNotice, '',
            t.email + ': ' + details.email,
            ...(details.phone ? [t.phone + ': ' + details.phone] : []),
            t.delivery + ': ' + t.postal,
            address.fullName, ...(address.company ? [t.company + ': ' + address.company] : []),
            address.street, address.postcode + ' ' + address.city, address.country,
            '', t.notes + ':', details.notes || '—', '', t.confirmation,
        ].join('\n');
    }

    function mailtoUrl(email, subject, body) {
        return 'mailto:' + email + '?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
    }

    function initNavigation(doc, viewport) {
        const menus = [...doc.querySelectorAll('button[aria-controls]')].map(trigger => ({
            trigger, panel: doc.getElementById(trigger.getAttribute('aria-controls')),
        })).filter(menu => menu.panel);

        function setOpen(menu, open, restoreFocus = false) {
            menu.panel.hidden = !open;
            menu.panel.style.display = open ? 'block' : '';
            menu.trigger.setAttribute('aria-expanded', String(open));
            if (open) menu.panel.querySelector('a[href]')?.focus();
            else if (restoreFocus) menu.trigger.focus();
        }
        menus.forEach(menu => {
            menu.trigger.addEventListener('click', () => {
                const open = menu.panel.hidden;
                menus.forEach(other => { if (other !== menu) setOpen(other, false); });
                setOpen(menu, open, !open);
            });
            menu.panel.addEventListener('click', event => {
                const link = event.target.closest('a[href]');
                if (!link) return;
                setOpen(menu, false);
                const href = link.getAttribute('href');
                if (href.startsWith('#')) {
                    const target = doc.getElementById(href.slice(1));
                    if (target) {
                        event.preventDefault();
                        target.scrollIntoView({ behavior: 'auto' });
                    }
                }
            });
        });
        doc.addEventListener('keydown', event => {
            const menu = menus.find(item => !item.panel.hidden);
            if (!menu) return;
            if (event.key === 'Escape') {
                event.preventDefault();
                setOpen(menu, false, true);
            } else if (event.key === 'Tab') {
                const links = [...menu.panel.querySelectorAll('a[href]')];
                const first = links[0], last = links[links.length - 1];
                if (event.shiftKey && doc.activeElement === first) {
                    event.preventDefault(); last.focus();
                } else if (!event.shiftKey && doc.activeElement === last) {
                    event.preventDefault(); first.focus();
                }
            }
        });
        viewport.matchMedia('(min-width: 1400px)').addEventListener('change', event => {
            if (event.matches) menus.forEach(menu => setOpen(menu, false));
        });
    }

    function initVariantSelects(doc, ChoicesClass) {
        // Keep native variant selection working if the shared CDN script is unavailable.
        if (typeof ChoicesClass !== 'function') return;
        doc.querySelectorAll('.shop-variant .custom-select').forEach(select => {
            new ChoicesClass(select, {
                searchEnabled: false, itemSelectText: '', shouldSort: false,
                allowHTML: false, labelId: select.labels[0].id,
            });
        });
    }

    function initPhotoViewer(doc) {
        const viewer = doc.getElementById('shop-lightbox');
        // The image links still work if the browser has no native dialog support.
        if (!viewer || typeof viewer.showModal !== 'function') return;
        const image = viewer.querySelector('.lightbox-img');
        const closeButton = viewer.querySelector('.shop-lightbox-close');
        const links = [...doc.querySelectorAll('.shop-photo-link')];
        let opener = null;

        function setPointerFocus(pointer) {
            viewer.classList.toggle('shop-photo-pointer-focus', pointer);
            opener?.classList.toggle('shop-photo-pointer-focus', pointer);
        }

        links.forEach(link => {
            link.addEventListener('pointerdown', () => link.classList.add('shop-photo-pointer-focus'));
            link.addEventListener('click', event => {
                if (event.defaultPrevented || event.button > 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                event.preventDefault();
                image.src = link.href;
                image.alt = link.querySelector('img').alt;
                viewer.setAttribute('aria-label', image.alt);
                opener = link;
                // Keyboard activation has no pointer type and a click count of zero.
                setPointerFocus(event.detail > 0 || Boolean(event.pointerType));
                viewer.showModal();
                viewer.classList.add('active');
                closeButton.focus({ preventScroll: true });
            });
        });
        doc.addEventListener('keydown', event => {
            if (event.key !== 'Tab') return;
            setPointerFocus(false);
            links.forEach(link => link.classList.remove('shop-photo-pointer-focus'));
        });
        viewer.addEventListener('pointerdown', () => setPointerFocus(true));
        // Match the blog: clicking the enlarged photo or its backdrop closes it.
        viewer.addEventListener('click', event => {
            setPointerFocus(event.detail > 0 || Boolean(event.pointerType));
            viewer.close();
        });
        viewer.addEventListener('cancel', event => {
            event.preventDefault();
            // Escape dismisses the viewer without changing the current input mode.
            viewer.close();
        });
        viewer.addEventListener('close', () => {
            viewer.classList.remove('active');
            opener?.focus({ preventScroll: true });
            opener = null;
        });
    }

    function basketRemoveButton(doc, item, name, label) {
        const button = doc.createElement('button');
        button.type = 'button';
        button.className = 'shop-basket-remove';
        button.dataset.remove = '';
        button.dataset.focusKey = lineKey(item.id, item.variant) + ':remove';
        button.setAttribute('aria-label', label + ': ' + name);
        button.title = label + ': ' + name;
        const icon = doc.createElement('span');
        icon.className = 'mdi mdi-close';
        icon.setAttribute('aria-hidden', 'true');
        button.append(icon);
        return button;
    }

    function initBasketQuantitySelection(container) {
        const selectQuantity = event => {
            const input = event.target;
            if (input.matches('input[data-quantity]') && !input.disabled && !input.readOnly) {
                input.select();
            }
        };
        // Delegation survives basket-row replacement. Selecting on click as well
        // as focus prevents clicking the field's padding from leaving a caret.
        container.addEventListener('focusin', selectQuantity);
        container.addEventListener('click', selectQuantity);
    }

    const api = { STORAGE_KEY, MAX_QUANTITY, lineKey, normaliseBasket, setQuantity, basketSummary, orderDetails, orderText, mailtoUrl, initNavigation, initVariantSelects, initPhotoViewer, basketRemoveButton, initBasketQuantitySelection };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    if (!root.document) return;

    function init() {
        initNavigation(document, window);
        initVariantSelects(document, root.Choices);
        initPhotoViewer(document);
        const configNode = document.getElementById('shop-config');
        if (!configNode) return;
        const config = JSON.parse(configNode.textContent);
        const t = config.text;
        const products = new Map(config.products.map(product => [product.id, product]));
        const money = new Intl.NumberFormat(config.locale, { style: 'currency', currency: config.currency, maximumFractionDigits: 0 });
        const form = document.getElementById('shop-order-form');
        const validation = root.SiteForm.initValidation(form);
        const draft = document.getElementById('order-draft');
        const basketList = document.getElementById('basket-items');
        initBasketQuantitySelection(basketList);
        let items = [];

        function storageUnavailable() { document.getElementById('shop-storage-notice').hidden = false; }
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            try { items = normaliseBasket(JSON.parse(saved), config.products); } catch (_) { items = []; }
            localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, items }));
        } catch (_) { storageUnavailable(); }

        function invalidateDraft() {
            draft.hidden = true;
            document.getElementById('order-draft-text').value = '';
            document.getElementById('order-mailto').removeAttribute('href');
            document.getElementById('order-copy-status').textContent = '';
        }

        function persist() {
            try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, items })); }
            catch (_) { storageUnavailable(); }
        }

        function quantity(id, variant) { return items.find(item => item.id === id && item.variant === variant)?.quantity || 0; }

        function element(tag, className, text) {
            const node = document.createElement(tag);
            if (className) node.className = className;
            if (text !== undefined) node.textContent = text;
            return node;
        }

        function controls(id, variant, name, value) {
            const group = element('div', 'shop-quantity');
            group.setAttribute('role', 'group');
            group.setAttribute('aria-label', t.quantity + ': ' + name);
            [-1, 0, 1].forEach(change => {
                const control = element(change ? 'button' : 'input', '', change ? (change === 1 ? '+' : '−') : undefined);
                if (change) {
                    control.type = 'button'; control.dataset.change = String(change);
                    control.setAttribute('aria-label', (change === 1 ? t.increase : t.decrease) + ': ' + name);
                    control.disabled = change === 1 && value >= MAX_QUANTITY;
                } else {
                    control.type = 'number'; control.min = '0'; control.max = String(MAX_QUANTITY); control.step = '1';
                    control.inputMode = 'numeric'; control.value = String(value); control.dataset.quantity = '';
                    control.setAttribute('aria-label', t.quantity + ': ' + name);
                }
                control.dataset.focusKey = lineKey(id, variant) + ':' + change;
                group.append(control);
            });
            return group;
        }

        function render() {
            const focusKey = document.activeElement?.dataset.focusKey;
            const basketScrollTop = basketList.scrollTop;
            basketList.replaceChildren();
            items.forEach(item => {
                const product = products.get(item.id);
                const variant = product.variants.find(v => v.id === item.variant);
                const name = product.name + (variant ? ' / ' + variant.label : '');
                const row = element('li', 'shop-basket-item');
                row.dataset.product = item.id; row.dataset.variantId = item.variant;
                row.append(element('h3', '', name), basketRemoveButton(document, item, name, t.remove),
                    element('p', '', formatPrice(product, config, item.quantity)), controls(item.id, item.variant, name, item.quantity));
                basketList.append(row);
            });
            document.querySelectorAll('.shop-product').forEach(card => {
                const product = products.get(card.dataset.product);
                const variant = card.querySelector('[data-variant]')?.value || '';
                const validVariant = !product.variants.length || product.variants.some(v => v.id === variant);
                const value = quantity(product.id, variant);
                card.querySelector('[data-quantity]').value = String(value);
                card.querySelector('[data-quantity]').disabled = !validVariant;
                card.querySelector('[data-change="-1"]').disabled = !validVariant || !value;
                card.querySelector('[data-change="1"]').disabled = !validVariant || value >= MAX_QUANTITY;
            });
            const summary = basketSummary(items, config.products);
            document.querySelectorAll('[data-basket-count]').forEach(node => { node.textContent = summary.count; });
            document.getElementById('basket-subtotal').textContent = money.format(summary.subtotalCents / 100);
            document.getElementById('basket-empty').hidden = !!items.length;
            document.getElementById('basket-quote-notice').hidden = !summary.quotedCount;
            document.getElementById('order-prepare').disabled = !items.length;
            document.getElementById('order-empty-note').hidden = !!items.length;
            // Rebuilding rows must not jump the independently scrolling list to the top.
            basketList.scrollTop = basketScrollTop;
            if (focusKey) {
                const target = [...basketList.querySelectorAll('[data-focus-key]')].find(node => node.dataset.focusKey === focusKey);
                (target && !target.disabled ? target : document.getElementById('basket')).focus({ preventScroll: true });
            }
        }

        function update(id, variant, value) {
            items = setQuantity(items, id, variant, value, config.products);
            persist(); invalidateDraft(); render();
            const summary = basketSummary(items, config.products);
            document.getElementById('shop-status').textContent = t.cartUpdated + '. ' + t.totalItems + ': ' + summary.count + '. ' + t.subtotal + ': ' + money.format(summary.subtotalCents / 100);
        }

        function targetItem(control) {
            const card = control.closest('[data-product]');
            if (!card) return null;
            return { id: card.dataset.product, variant: card.dataset.variantId ?? (card.querySelector('[data-variant]')?.value || '') };
        }

        document.addEventListener('click', event => {
            const control = event.target.closest('[data-change], [data-remove]');
            if (!control) return;
            const item = targetItem(control);
            if (!item) return;
            const next = control.hasAttribute('data-remove') ? 0 : quantity(item.id, item.variant) + Number(control.dataset.change);
            update(item.id, item.variant, next);
        });
        document.addEventListener('change', event => {
            if (event.target.matches('[data-variant]')) { render(); return; }
            if (!event.target.matches('[data-quantity]')) return;
            const item = targetItem(event.target);
            const value = event.target.value === '' ? 0 : event.target.valueAsNumber;
            if (!Number.isInteger(value) || value < 0 || value > MAX_QUANTITY) {
                event.target.reportValidity(); render(); return;
            }
            update(item.id, item.variant, value);
        });
        window.addEventListener('storage', event => {
            if (event.key !== STORAGE_KEY && event.key !== null) return;
            try { items = normaliseBasket(JSON.parse(event.newValue), config.products); } catch (_) { items = []; }
            invalidateDraft(); render();
        });

        form.addEventListener('input', invalidateDraft);
        form.addEventListener('change', invalidateDraft);
        form.addEventListener('submit', event => {
            event.preventDefault();
            if (!items.length) { document.getElementById('basket').focus(); return; }
            if (!validation.validate()) return;
            const details = orderDetails(Object.fromEntries(new FormData(form)));
            const body = orderText(items, details, config);
            document.getElementById('order-draft-text').value = body;
            document.getElementById('order-mailto').href = mailtoUrl(config.email, t.orderSubject, body);
            draft.hidden = false;
            draft.focus();
        });
        document.getElementById('order-copy').addEventListener('click', async () => {
            const text = document.getElementById('order-draft-text');
            try {
                if (!navigator.clipboard) throw new Error('Clipboard unavailable');
                await navigator.clipboard.writeText(text.value);
                document.getElementById('order-copy-status').textContent = t.copied;
            } catch (_) {
                text.focus(); text.select();
                document.getElementById('order-copy-status').textContent = t.copyManual;
            }
        });
        render();
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})(typeof globalThis !== 'undefined' ? globalThis : this);
