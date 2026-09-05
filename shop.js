/* Browser-only basket. Never persist customer contact or delivery details. */
(function (root) {
    'use strict';

    const STORAGE_KEY = 'muckova-shop-basket';
    const MAX_QUANTITY = 9999;
    const MAX_ITEMS = 500;

    function lineKey(id, variant = '') { return id + ':' + variant; }
    function basketLineKey(item) {
        if (item.lineId) return item.id + ':@' + item.lineId;
        // Structured keys keep free-text specifications containing punctuation distinct.
        const parameters = Object.keys(item.parameters || {}).sort().map(key => [key, item.parameters[key]]);
        return lineKey(item.id, item.variant) + (parameters.length ? ':' + JSON.stringify(parameters) : '');
    }

    function positiveInteger(value) {
        return (typeof value === 'number' || typeof value === 'string') && /^\d+$/.test(String(value).trim())
            && Number.isSafeInteger(Number(value)) && Number(value) > 0;
    }

    function normaliseOrderParameter(value, field) {
        if (field.type === 'text') {
            if (typeof value !== 'string') return null;
            const text = value.replace(/[\s\u0000-\u001f\u007f]+/g, ' ').trim();
            return text && text.length <= field.maxLength ? text : null;
        }
        if (field.type === 'decimal') {
            if (typeof value !== 'string' && typeof value !== 'number') return null;
            const decimal = String(value).trim().replace(',', '.');
            if (decimal.length > 32 || !/^(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(decimal)
                || !Number.isFinite(Number(decimal)) || Number(decimal) <= 0) return null;
            return String(Number(decimal));
        }
        return positiveInteger(value) ? String(Number(value)) : null;
    }

    function normaliseOrderParameters(value, product, variantId) {
        const fields = product.variants.find(variant => variant.id === variantId)?.fields || [];
        const parameters = {};
        for (const field of fields) {
            const parameter = normaliseOrderParameter(value?.[field.id], field);
            if (parameter === null) return null;
            parameters[field.id] = parameter;
        }
        if (fields.some(field => field.minimumField && Number(parameters[field.id]) < Number(parameters[field.minimumField]))) return null;
        return parameters;
    }

    function normaliseConfiguration(value, product) {
        if (product?.kind !== 'wizard' || !value || typeof value !== 'object') return null;
        const profile = product.wizard.profiles.find(option => option.id === value.profile);
        if (!profile) return null;
        const needsBearing = profile.manufacture === 'new' && product.wizard.bearings.length > 0;
        const bearing = needsBearing ? value.bearing : '';
        if (needsBearing && !product.wizard.bearings.some(option => option.id === bearing)) return null;
        const values = {};
        for (const field of product.wizard.fields) {
            const raw = value.values?.[field.id];
            if (raw !== undefined && typeof raw !== 'string' && typeof raw !== 'number') return null;
            let text = raw === undefined ? '' : String(raw).trim();
            if (!text && field.required) return null;
            if (field.type === 'text') {
                text = text.replace(/[\s\u0000-\u001f\u007f]+/g, ' ').trim();
                if ((field.required && !text) || text.length > field.maxLength) return null;
            } else if (text) {
                // Accept decimal input, not JS-specific hexadecimal or Infinity.
                const decimal = text.replace(',', '.');
                if (decimal.length > 32 || !/^(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(decimal)
                    || !Number.isFinite(Number(decimal)) || Number(decimal) <= 0) return null;
                text = String(Number(decimal));
            }
            values[field.id] = text;
        }
        return { profile: profile.id, bearing, values };
    }

    function addConfiguredItem(items, id, configuration, products, lineId) {
        const product = products.find(product => product.id === id);
        const cleaned = normaliseConfiguration(configuration, product);
        if (!cleaned || items.length >= MAX_ITEMS || typeof lineId !== 'string' || !/^[a-zA-Z0-9-]{1,80}$/.test(lineId)
            || items.some(item => item.lineId === lineId)) return items;
        return [...items, { id, variant: '', quantity: 1, lineId, configuration: cleaned }];
    }

    function removeBasketItem(items, key) { return items.filter(item => basketLineKey(item) !== key); }

    function hasLegacyCamshafts(value) {
        return value?.version === 1 && Array.isArray(value.items)
            && value.items.some(row => row && ['camshaft-regrind', 'camshaft-new'].includes(row.id));
    }

    function hasLegacyRotors(value) {
        return value?.version === 1 && Array.isArray(value.items)
            && value.items.some(row => row?.id === 'distributor-rotor' && !row.variant);
    }

    function normaliseBasket(value, products) {
        const rows = value && value.version === 1 && Array.isArray(value.items) ? value.items : [];
        const catalog = new Map(products.map(product => [product.id, product]));
        const legacy = new Map(products.flatMap(product => (product.legacyItems || []).map(item =>
            [item.id, { id: product.id, sourceVariant: item.variant, variant: item.targetVariant }])));
        const items = new Map();
        rows.slice(0, MAX_ITEMS).forEach(row => {
            if (!row || typeof row !== 'object') return;
            if (!catalog.has(row.id)) {
                const replacement = legacy.get(row.id);
                if (!replacement || (row.variant || '') !== replacement.sourceVariant) return;
                row = { ...row, id: replacement.id, variant: replacement.variant };
            }
            const product = catalog.get(row.id);
            if (!product || !Number.isInteger(row.quantity) || row.quantity < 1) return;
            if (product.kind === 'wizard') {
                const configuration = normaliseConfiguration(row.configuration, product);
                if (row.quantity !== 1 || !configuration || typeof row.lineId !== 'string' || !/^[a-zA-Z0-9-]{1,80}$/.test(row.lineId)) return;
                const key = basketLineKey(row);
                if (!items.has(key)) items.set(key, { id: product.id, variant: '', quantity: 1, lineId: row.lineId, configuration });
                return;
            }
            const variant = typeof row.variant === 'string' ? row.variant : '';
            if (product.variants.length ? !product.variants.some(v => v.id === variant) : variant !== '') return;
            const parameters = normaliseOrderParameters(row.parameters, product, variant);
            if (!parameters) return;
            const item = { id: product.id, variant, ...(Object.keys(parameters).length ? { parameters } : {}) };
            const key = basketLineKey(item);
            const quantity = Math.min(MAX_QUANTITY, row.quantity + (items.get(key)?.quantity || 0));
            items.set(key, { ...item, quantity });
        });
        return [...items.values()];
    }

    function setQuantity(items, id, variant, quantity, products, parameters) {
        if (!Number.isFinite(quantity) || products.find(product => product.id === id)?.kind === 'wizard') return items;
        const key = basketLineKey({ id, variant, parameters });
        const next = items.map(item => basketLineKey(item) === key ? { ...item, quantity: Math.min(MAX_QUANTITY, Math.floor(quantity)) } : item);
        if (quantity > 0 && !items.some(item => basketLineKey(item) === key)) {
            next.push({ id, variant, parameters, quantity: Math.min(MAX_QUANTITY, Math.floor(quantity)) });
        }
        return normaliseBasket({ version: 1, items: next }, products);
    }

    function addOrderItem(items, id, variant, quantity, products, values) {
        const product = products.find(product => product.id === id);
        if (!product || product.kind === 'wizard' || !Number.isInteger(quantity) || quantity < 1 || quantity > MAX_QUANTITY
            || (product.variants.length ? !product.variants.some(value => value.id === variant) : variant !== '')) return items;
        const parameters = normaliseOrderParameters(values, product, variant);
        if (!parameters) return items;
        const key = basketLineKey({ id, variant, parameters });
        const existing = items.find(item => basketLineKey(item) === key);
        if ((!existing && items.length >= MAX_ITEMS) || quantity + (existing?.quantity || 0) > MAX_QUANTITY) return items;
        return setQuantity(items, id, variant, quantity + (existing?.quantity || 0), products, parameters);
    }

    function basketSummary(items, products) {
        const catalog = new Map(products.map(product => [product.id, product]));
        return items.reduce((result, item) => {
            const product = itemPrice(item, catalog.get(item.id));
            if (!product) return result;
            result.count += item.quantity;
            if (product.priceType === 'fixed') result.subtotalCents += product.price * 100 * item.quantity;
            else result.quotedCount += item.quantity;
            return result;
        }, { count: 0, subtotalCents: 0, quotedCount: 0 });
    }

    function itemPrice(item, product) {
        if (!product) return null;
        if (product.kind !== 'wizard') {
            const variant = product.variants.find(variant => variant.id === item.variant);
            return { price: variant && Object.hasOwn(variant, 'price') ? variant.price : product.price,
                priceType: variant?.priceType || product.priceType };
        }
        const profile = product.wizard.profiles.find(profile => profile.id === item.configuration?.profile);
        return profile ? { price: profile.price, priceType: 'fixed' } : null;
    }

    function configurationDetails(item, product, config) {
        if (product.kind !== 'wizard') {
            const fields = product.variants.find(variant => variant.id === item.variant)?.fields || [];
            return fields.map(field => [config.text[field.labelKey], item.parameters[field.id]]);
        }
        const t = config.text;
        const selected = item.configuration;
        const profile = product.wizard.profiles.find(profile => profile.id === selected.profile);
        const bearing = product.wizard.bearings.find(bearing => bearing.id === selected.bearing);
        return [
            [t.profileHeading, t[profile.manufacture === 'new' ? 'manufactureNew' : 'manufactureRegrind']],
            [t.camDuration, profile.duration], [t.camLift, profile.lift],
            [t.profileDescription, profile.description || profile.translations[config.locale]],
            ...(bearing ? [[t.bearings, t[bearing.labelKey] + ' ' + bearing.diameters]] : []),
            ...product.wizard.fields.filter(field => selected.values[field.id]).map(field => [
                t[field.labelKey], selected.values[field.id] + (field.unit ? ' ' + field.unit : ''),
            ]),
        ];
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
        return ['from', 'approx'].includes(product.priceType) ? config.text[product.priceType] + ' ' + amount : amount;
    }

    function orderText(items, details, config) {
        const t = config.text;
        const products = new Map(config.products.map(product => [product.id, product]));
        const summary = basketSummary(items, config.products);
        const money = new Intl.NumberFormat(config.locale, { style: 'currency', currency: config.currency, maximumFractionDigits: 0 });
        const lines = items.map(item => {
            const product = products.get(item.id);
            const variant = product.variants.find(v => v.id === item.variant);
            const heading = `${item.quantity} × ${product.name}${variant ? ' / ' + variant.label : ''} [${product.id}${item.variant ? ':' + item.variant : ''}] — ${formatPrice(itemPrice(item, product), config, item.quantity)}`;
            return [heading, ...configurationDetails(item, product, config).map(([label, value]) => `  ${label}: ${value}`)].join('\n');
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
        const menus = [...doc.querySelectorAll('button[aria-controls="mobile-menu-overlay"], button[aria-controls="mobile-langchooser-overlay"]')].map(trigger => ({
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
        const instances = new Map();
        // Keep native variant selection working if the shared CDN script is unavailable.
        if (typeof ChoicesClass !== 'function') return instances;
        doc.querySelectorAll('.shop-variant .custom-select').forEach(select => {
            instances.set(select, new ChoicesClass(select, {
                searchEnabled: false, itemSelectText: '', shouldSort: false,
                allowHTML: false, labelId: select.labels[0].id,
            }));
        });
        return instances;
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

    function initPhotoGalleries(doc) {
        doc.querySelectorAll('.shop-photo-gallery').forEach(gallery => {
            const links = [...gallery.querySelectorAll('.shop-photo-link')];
            if (links.length < 2) return;
            const thumbnails = doc.createElement('div');
            thumbnails.className = 'shop-photo-thumbnails';
            thumbnails.setAttribute('role', 'group');
            thumbnails.setAttribute('aria-label', gallery.closest('.shop-product').querySelector('.shop-product-title').textContent);
            const buttons = links.map((link, index) => {
                const button = doc.createElement('button');
                const photo = link.querySelector('img');
                button.type = 'button';
                button.className = 'shop-photo-thumbnail';
                button.setAttribute('aria-label', photo.alt);
                button.setAttribute('aria-controls', link.id);
                button.setAttribute('aria-pressed', String(index === 0));
                const thumbnail = photo.cloneNode(false);
                thumbnail.alt = '';
                thumbnail.loading = 'lazy';
                button.append(thumbnail);
                button.addEventListener('click', () => {
                    links.forEach((item, selected) => { item.hidden = selected !== index; });
                    buttons.forEach((item, selected) => item.setAttribute('aria-pressed', String(selected === index)));
                });
                return button;
            });
            thumbnails.append(...buttons);
            gallery.append(thumbnails);
            links.forEach((link, index) => { link.hidden = index !== 0; });
            gallery.classList.add('is-enhanced');
        });
    }

    function basketRemoveButton(doc, item, name, label) {
        const button = doc.createElement('button');
        button.type = 'button';
        button.className = 'shop-basket-remove';
        button.dataset.remove = '';
        button.dataset.focusKey = basketLineKey(item) + ':remove';
        button.setAttribute('aria-label', label + ': ' + name);
        button.title = label + ': ' + name;
        const icon = doc.createElement('span');
        icon.className = 'mdi mdi-close';
        icon.setAttribute('aria-hidden', 'true');
        button.append(icon);
        return button;
    }

    function initBasketQuantitySelection(container, selector = 'input[data-quantity]') {
        const selectQuantity = event => {
            const input = event.target;
            if (input.matches(selector) && !input.disabled && !input.readOnly) {
                input.select();
            }
        };
        // Delegation survives basket-row replacement. Selecting on click as well
        // as focus prevents clicking the field's padding from leaving a caret.
        // Wizard engine fields reuse the same behavior with their own selector.
        container.addEventListener('focusin', selectQuantity);
        container.addEventListener('click', selectQuantity);
    }

    function initRadioSubform(form, name, onSelect) {
        const fields = form.querySelector('[data-profile-fields]');
        let selected = null;
        function sync() {
            selected = form.querySelector(`input[name="${name}"]:checked`);
            const option = selected?.closest('.shop-profile-option');
            fields.hidden = !option;
            if (option) option.after(fields);
            onSelect(selected?.value || '');
        }
        form.addEventListener('click', event => {
            const radio = event.target;
            if (event.defaultPrevented || radio.type !== 'radio' || radio.name !== name) return;
            if (radio === selected) {
                radio.checked = false;
                radio.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
        form.addEventListener('keydown', event => {
            const radio = event.target;
            if (event.key !== ' ' || radio.type !== 'radio' || radio.name !== name) return;
            event.preventDefault();
            if (!event.repeat) radio.click();
        });
        form.addEventListener('change', event => { if (event.target.name === name) sync(); });
        sync();
        return () => selected?.value || '';
    }

    function initOrderQuantitySpinner(form) {
        const input = form.querySelector('[data-order-quantity]');
        const buttons = [...form.querySelectorAll('[data-order-change]')];
        function sync() {
            buttons.forEach(button => {
                const change = Number(button.dataset.orderChange);
                button.disabled = input.disabled || input.readOnly
                    || (change < 0 ? input.valueAsNumber <= 1 : input.valueAsNumber >= MAX_QUANTITY);
            });
        }
        buttons.forEach(button => button.addEventListener('click', () => {
            if (button.disabled || input.disabled || input.readOnly) return;
            const current = Number.isFinite(input.valueAsNumber) ? input.valueAsNumber : 0;
            input.value = String(Math.max(1, Math.min(MAX_QUANTITY, Math.floor(current) + Number(button.dataset.orderChange))));
            // Only update the draft and its validation. Add to order remains explicit.
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }));
        input.addEventListener('input', sync);
        input.addEventListener('change', sync);
        sync();
        return sync;
    }

    function initOrderParameterFields(form, message) {
        const rows = [...form.querySelectorAll('[data-order-field-row]')];
        const inputs = rows.map(row => row.querySelector('[data-order-field]'));
        function syncValidity() {
            inputs.forEach(input => {
                const field = { type: input.dataset.orderFieldType, maxLength: input.maxLength };
                const parameter = normaliseOrderParameter(input.value, field);
                const minimum = inputs.find(other => !other.disabled && other.dataset.orderField === input.dataset.minimumField)?.value;
                const invalid = parameter === null || (minimum && Number(parameter) < Number(minimum));
                input.setCustomValidity(!input.disabled && input.value && invalid ? input.dataset.orderFieldWarning || message : '');
            });
        }
        let refreshing = false;
        function refresh(event) {
            if (refreshing) return;
            refreshing = true;
            syncValidity();
            inputs.filter(input => !input.disabled && input.value && input.dataset.minimumField === event.target.dataset.orderField)
                .forEach(input => input.dispatchEvent(new Event('change', { bubbles: true })));
            refreshing = false;
        }
        inputs.forEach(input => {
            input.addEventListener('input', refresh);
            input.addEventListener('change', refresh);
        });
        return {
            select(variant) {
                rows.forEach((row, index) => {
                    row.hidden = row.dataset.orderFieldRow !== variant;
                    inputs[index].disabled = row.hidden;
                });
                syncValidity();
            },
            read() {
                syncValidity();
                return Object.fromEntries(inputs.filter(input => !input.disabled).map(input => [input.dataset.orderField, input.value]));
            },
        };
    }

    function initOrderItemForm(form, product, siteForm, selectInstances, text, onAdd) {
        // Register parameter constraints before the shared inline validation handlers.
        const parameterFields = initOrderParameterFields(form, text.rpmWarning);
        const validation = siteForm.initValidation(form, { requiredMessage: text.requiredWarning });
        const quantity = form.querySelector('[data-order-quantity]');
        const variantRows = [...form.querySelectorAll('[data-order-variant-fields]')];
        const submit = form.querySelector('button[type="submit"]');
        const status = form.querySelector('.shop-wizard-status');
        let selectedOption = null;
        let variantSelect = null;
        const syncQuantity = initOrderQuantitySpinner(form);
        initBasketQuantitySelection(form, 'input[data-order-quantity], input[data-order-field]');
        const syncParameters = () => parameterFields.select(variantSelect ? variantSelect.value : selectedOption?.variants[0]?.id || '');
        initRadioSubform(form, 'option', value => {
            selectedOption = product.options.find(option => option.id === value);
            variantSelect = null;
            quantity.disabled = !selectedOption;
            syncQuantity();
            submit.disabled = !selectedOption;
            variantRows.forEach(row => {
                const select = row.querySelector('select');
                const choices = selectInstances.get(select);
                const active = row.dataset.orderVariantFields === value;
                row.hidden = !active;
                select.disabled = !active;
                choices?.setChoiceByValue('');
                select.value = '';
                if (active) { choices?.enable(); variantSelect = select; }
                else choices?.disable();
            });
            syncParameters();
            validation.reset();
            status.hidden = true;
        });
        form.addEventListener('input', () => { status.hidden = true; });
        form.addEventListener('change', event => {
            status.hidden = true;
            if (event.target === variantSelect) syncParameters();
        });
        form.addEventListener('submit', event => {
            event.preventDefault();
            status.hidden = true;
            const parameters = parameterFields.read();
            if (!selectedOption || !validation.validate()) return;
            const variant = variantSelect ? variantSelect.value : selectedOption.variants[0]?.id || '';
            if (selectedOption.variants.length && !selectedOption.variants.some(option => option.id === variant)) return;
            const count = Number(quantity.value);
            if (!Number.isInteger(count) || count < 1 || count > MAX_QUANTITY) return;
            const error = onAdd(variant, count, parameters);
            if (error) { status.textContent = error; status.hidden = false; }
        });
    }

    function initWizardForm(form, product, siteForm, selectInstances, text, onAdd) {
        const validation = siteForm.initValidation(form, { requiredMessage: text.requiredWarning });
        initBasketQuantitySelection(form, 'input[data-engine-field]');
        const bearing = form.elements.namedItem('bearing');
        const bearingFields = form.querySelector('[data-bearing-fields]');
        const engineFields = [...form.querySelectorAll('[data-engine-field]')];
        const bearingSelect = selectInstances.get(bearing);
        const status = form.querySelector('.shop-wizard-status');
        const submit = form.querySelector('button[type="submit"]');
        const read = name => form.elements.namedItem(name)?.value || '';

        function syncBearings(profile) {
            if (!bearing || !bearingFields) return;
            const available = profile?.manufacture === 'new';
            bearingFields.hidden = !available;
            bearing.disabled = !available;
            bearing.required = available;
            if (available) bearingSelect?.enable();
            else {
                bearingSelect?.setChoiceByValue('');
                bearing.value = '';
                bearingSelect?.disable();
                bearing.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

        const selectedProfile = initRadioSubform(form, 'profile', value => {
            const profile = product.wizard.profiles.find(option => option.id === value);
            engineFields.forEach(field => { field.disabled = !profile; });
            submit.disabled = !profile;
            syncBearings(profile);
            // The optional radio group opens/closes the subform; it is not a
            // validated order field. Closing it also clears its field warnings.
            if (!profile) validation.reset();
        });
        form.addEventListener('input', () => { status.hidden = true; });
        form.addEventListener('change', event => {
            status.hidden = true;
        });
        form.addEventListener('submit', event => {
            event.preventDefault();
            status.hidden = true;
            status.textContent = '';
            if (!selectedProfile() || !validation.validate()) return;
            const configuration = normaliseConfiguration({
                profile: read('profile'), bearing: read('bearing'),
                values: Object.fromEntries(product.wizard.fields.map(field => [field.id, read(field.id)])),
            }, product);
            if (!configuration) return;
            if (!onAdd(configuration)) {
                status.textContent = text.basketFull;
                status.hidden = false;
            }
        });
    }

    const api = { STORAGE_KEY, MAX_QUANTITY, MAX_ITEMS, lineKey, basketLineKey, normaliseBasket, normaliseOrderParameters, hasLegacyRotors, normaliseConfiguration, addConfiguredItem, addOrderItem, removeBasketItem, hasLegacyCamshafts, itemPrice, configurationDetails, setQuantity, basketSummary, orderDetails, orderText, mailtoUrl, initNavigation, initVariantSelects, initPhotoViewer, initPhotoGalleries, basketRemoveButton, initBasketQuantitySelection, initRadioSubform, initOrderQuantitySpinner, initOrderItemForm, initOrderParameterFields, initWizardForm };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    if (!root.document) return;

    function init() {
        initNavigation(document, window);
        const selectInstances = initVariantSelects(document, root.Choices);
        initPhotoGalleries(document);
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
            try {
                const parsed = JSON.parse(saved);
                items = normaliseBasket(parsed, config.products);
                document.getElementById('shop-legacy-notice').hidden = !hasLegacyCamshafts(parsed);
                document.getElementById('shop-legacy-rotor-notice').hidden = !hasLegacyRotors(parsed);
            } catch (_) { items = []; }
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

        function element(tag, className, text) {
            const node = document.createElement(tag);
            if (className) node.className = className;
            if (text !== undefined) node.textContent = text;
            return node;
        }

        function controls(item, name) {
            const value = item.quantity;
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
                control.dataset.focusKey = basketLineKey(item) + ':' + change;
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
                row.dataset.lineKey = basketLineKey(item);
                row.append(element('h3', '', name), basketRemoveButton(document, item, name, t.remove),
                    element('p', '', formatPrice(itemPrice(item, product), config, item.quantity)));
                const specifications = configurationDetails(item, product, config);
                if (specifications.length) {
                    const details = element('dl', 'shop-basket-configuration');
                    specifications.forEach(([label, value]) => {
                        const entry = element('div');
                        entry.append(element('dt', '', label), element('dd', '', value));
                        details.append(entry);
                    });
                    row.append(details);
                }
                if (product.kind !== 'wizard') row.append(controls(item, name));
                basketList.append(row);
            });
            const summary = basketSummary(items, config.products);
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

        function basketChanged() {
            persist(); invalidateDraft(); render();
            const summary = basketSummary(items, config.products);
            document.getElementById('shop-status').textContent = t.cartUpdated + '. ' + t.totalItems + ': ' + summary.count + '. ' + t.subtotal + ': ' + money.format(summary.subtotalCents / 100);
        }

        function update(id, variant, value, parameters) {
            items = setQuantity(items, id, variant, value, config.products, parameters);
            basketChanged();
        }

        function targetItem(control) {
            const card = control.closest('.shop-basket-item');
            if (!card) return null;
            const item = items.find(item => basketLineKey(item) === card.dataset.lineKey);
            return item ? { ...item, key: card.dataset.lineKey } : null;
        }

        document.addEventListener('click', event => {
            const control = event.target.closest('[data-change], [data-remove]');
            if (!control) return;
            const item = targetItem(control);
            if (!item) return;
            if (control.hasAttribute('data-remove') && item.key) {
                items = removeBasketItem(items, item.key);
                basketChanged();
                return;
            }
            const next = control.hasAttribute('data-remove') ? 0 : item.quantity + Number(control.dataset.change);
            update(item.id, item.variant, next, item.parameters);
        });
        document.addEventListener('change', event => {
            if (!event.target.matches('[data-quantity]')) return;
            const item = targetItem(event.target);
            const value = event.target.value === '' ? 0 : event.target.valueAsNumber;
            if (!Number.isInteger(value) || value < 0 || value > MAX_QUANTITY) {
                event.target.reportValidity(); render(); return;
            }
            update(item.id, item.variant, value, item.parameters);
        });
        window.addEventListener('storage', event => {
            if (event.key !== STORAGE_KEY && event.key !== null) return;
            try { items = normaliseBasket(JSON.parse(event.newValue), config.products); } catch (_) { items = []; }
            invalidateDraft(); render();
        });

        document.querySelectorAll('form[data-order-product]').forEach(itemForm => {
            const product = products.get(itemForm.dataset.orderProduct);
            initOrderItemForm(itemForm, product, root.SiteForm, selectInstances, t, (variant, count, parameters) => {
                const key = basketLineKey({ id: product.id, variant, parameters });
                const existing = items.find(item => basketLineKey(item) === key);
                if (count + (existing?.quantity || 0) > MAX_QUANTITY) return t.quantityLimit;
                const next = addOrderItem(items, product.id, variant, count, config.products, parameters);
                if (next === items) return t.basketFull;
                items = next;
                basketChanged();
                return '';
            });
        });

        document.querySelectorAll('form[data-wizard]').forEach(wizardForm => {
            const product = products.get(wizardForm.dataset.wizard);
            initWizardForm(wizardForm, product, root.SiteForm, selectInstances, t, configuration => {
                const lineId = root.crypto.randomUUID ? root.crypto.randomUUID()
                    : [...root.crypto.getRandomValues(new Uint8Array(16))].map(byte => byte.toString(16).padStart(2, '0')).join('');
                const next = addConfiguredItem(items, product.id, configuration, config.products, lineId);
                if (next === items) return false;
                items = next;
                basketChanged();
                return true;
            });
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
