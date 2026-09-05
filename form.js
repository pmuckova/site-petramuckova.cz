/* Shared terminal-form behavior for the main contact form and shop inquiry. */
(function (root) {
    'use strict';

    function initValidation(form, options = {}) {
        if (!form) return null;
        const fields = [...form.querySelectorAll('.validate-me')];
        const warnings = new Map(fields.map(input => [input, input.getAttribute('data-warning-id')
            ? form.querySelector('#' + input.getAttribute('data-warning-id')) : input.nextElementSibling]));
        // Keep the localized messages from the markup, even after a required-field
        // warning temporarily replaces an email/phone/year format warning.
        const messages = new Map(fields.map(input => [input, warnings.get(input).textContent.trim()]));
        const requiredField = fields.find(input => input.required && input.type === 'text');
        const requiredMessage = options.requiredMessage || messages.get(requiredField) || 'This field is required.';

        function showWarning(input, message) {
            input.classList.toggle('input-warning', Boolean(message));
            input.setAttribute('aria-invalid', String(Boolean(message)));
            const choices = input.closest?.('.choices');
            choices?.querySelector('.choices__inner')?.classList.toggle('input-warning', Boolean(message));
            choices?.setAttribute('aria-invalid', String(Boolean(message)));
            const warning = warnings.get(input);
            warning.textContent = message || messages.get(input);
            warning.style.display = message ? 'block' : 'none';
        }

        function validateInput(input) {
            const value = input.type === 'radio'
                ? (fields.some(field => field.type === 'radio' && field.name === input.name && field.checked && !field.disabled) ? 'selected' : '')
                : input.value.trim();
            let message = '';
            if (!input.disabled) {
                if (input.required && !value) {
                    message = requiredMessage;
                } else if (value) {
                    const invalidEmail = input.type === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
                    const invalidPhone = (input.name === 'phone' || input.type === 'tel') && !/^[\d\s+]{9,20}$/.test(value);
                    const invalidYear = input.name === 'year' && Number(value) < 1900;
                    const invalidPositive = input.getAttribute('data-positive') !== null && !(Number(value) > 0 && Number.isFinite(Number(value)));
                    if (invalidEmail || invalidPhone || invalidYear || invalidPositive || input.validity?.valid === false) {
                        message = messages.get(input);
                    }
                } else if (input.validity?.badInput) {
                    message = messages.get(input);
                }
            }
            showWarning(input, message);
            return !message;
        }

        fields.forEach(input => {
            const warning = warnings.get(input);
            if (!input.id) input.id = `${form.id}-${input.name}`;
            if (!warning.id) warning.id = `${input.id}-warning`;
            const describedBy = new Set((input.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
            describedBy.add(warning.id);
            input.setAttribute('aria-describedby', [...describedBy].join(' '));
            input.closest?.('.choices')?.setAttribute('aria-describedby', [...describedBy].join(' '));
            warning.setAttribute('aria-live', 'polite');
            const validateChanged = () => {
                if (input.type === 'radio') fields.filter(field => field.type === 'radio' && field.name === input.name).forEach(validateInput);
                else validateInput(input);
            };
            input.addEventListener('input', validateChanged);
            input.addEventListener('change', validateChanged);
        });

        function reset() { fields.forEach(input => showWarning(input, '')); }
        form.addEventListener('reset', reset);

        return {
            validate() {
                let firstInvalid;
                fields.forEach(input => {
                    const trimmed = input.value.trim();
                    // Do not reassign an unchanged numeric value: doing so clears
                    // the browser's badInput state before it can be validated.
                    if (input.value !== trimmed) input.value = trimmed;
                    if (!validateInput(input) && !firstInvalid) firstInvalid = input;
                });
                // Choices keeps its native select hidden; focus the visible control.
                const focusTarget = firstInvalid?.closest?.('.choices') || firstInvalid;
                focusTarget?.focus();
                return !firstInvalid;
            },
            reset,
        };
    }

    const api = { initValidation };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    root.SiteForm = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
