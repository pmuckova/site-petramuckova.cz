/* Shared terminal-form behavior for the main contact form and shop inquiry. */
(function (root) {
    'use strict';

    const submissionTranslations = {
        cs: {
            fileTooLarge: "CHYBA: Celková velikost souborů překročila 8MB! Zmenšete celkovou velikost všech souborů.",
            selectFile: "Vybrat soubor...",
            emailSubmissionSendingBtnText: "ODESÍLÁM...",
            emailSubmissionSucceededMsg: "EMAIL ODESLÁN!",
            emailSubmissionFailedMsg: "NASTAL CHYBA! EMAIL NEBYL ODESLÁN. ZKUSTE TO PROSÍM ZNOVU, NEBO PIŠTE ROVNOU NA info@petramuckova.cz"
        },
        en: {
            fileTooLarge: "ERROR: Total file size exceeds 8MB! Please reduce the total size of all files.",
            selectFile: "Select file...",
            emailSubmissionSendingBtnText: "SENDING...",
            emailSubmissionSucceededMsg: "EMAIL SENT!",
            emailSubmissionFailedMsg: "AN ERROR OCCURRED! EMAIL WAS NOT SENT. PLEASE TRY AGAIN OR EMAIL DIRECTLY AT info@petramuckova.cz"
        },
        de: {
            fileTooLarge: "FEHLER: Die Gesamtgröße der Dateien überschreitet 8MB! Bitte reduzieren Sie die Gesamtgröße aller Dateien.",
            selectFile: "Datei auswählen...",
            emailSubmissionSendingBtnText: "SENDEN...",
            emailSubmissionSucceededMsg: "E-MAIL GESENDET!",
            emailSubmissionFailedMsg: "EIN FEHLER IST AUFGETRETEN! E-MAIL WURDE NICHT GESENDET. BITTE VERSUCHEN SIE ES ERNEUT ODER SCHREIBEN SIE DIREKT AN info@petramuckova.cz"
        },
        fr: {
            fileTooLarge: "ERREUR: La taille totale des fichiers dépasse 8MB! Veuillez réduire la taille totale de tous les fichiers.",
            selectFile: "Sélectionner un fichier...",
            emailSubmissionSendingBtnText: "ENVOI...",
            emailSubmissionSucceededMsg: "EMAIL ENVOYÉ!",
            emailSubmissionFailedMsg: "UNE ERREUR S'EST PRODUITE! L'EMAIL N'A PAS ÉTÉ ENVOYÉ. VEUILLEZ RÉESSAYER OU ÉCRIRE DIRECTEMENT À info@petramuckova.cz"
        },
        it: {
            fileTooLarge: "ERRORE: La dimensione totale dei file supera gli 8MB! Ridurre la dimensione totale di tutti i file.",
            selectFile: "Seleziona file...",
            emailSubmissionSendingBtnText: "INVIO...",
            emailSubmissionSucceededMsg: "EMAIL INVIATA!",
            emailSubmissionFailedMsg: "SI È VERIFICATO UN ERRORE! L'EMAIL NON È STATA INVIATA. RIPROVA O SCRIVI DIRETTAMENTE A info@petramuckova.cz"
        },
        es: {
            fileTooLarge: "ERROR: ¡El tamaño total de los archivos supera los 8MB! Reduzca el tamaño total de todos los archivos.",
            selectFile: "Seleccionar archivo...",
            emailSubmissionSendingBtnText: "ENVIANDO...",
            emailSubmissionSucceededMsg: "¡EMAIL ENVIADO!",
            emailSubmissionFailedMsg: "¡OCURRIÓ UN ERROR! EL EMAIL NO FUE ENVIADO. INTÉNTELO DE NUEVO O ESCRIBA DIRECTAMENTE A info@petramuckova.cz"
        },
        pl: {
            fileTooLarge: "BŁĄD: Całkowity rozmiar plików przekracza 8MB! Zmniejsz całkowity rozmiar wszystkich plików.",
            selectFile: "Wybierz plik...",
            emailSubmissionSendingBtnText: "WYSYŁANIE...",
            emailSubmissionSucceededMsg: "EMAIL WYSŁANY!",
            emailSubmissionFailedMsg: "WYSTĄPIŁ BŁĄD! EMAIL NIE ZOSTAŁ WYSŁANY. SPRÓBUJ PONOWNIE LUB NAPISZ BEZPOŚREDNIO NA info@petramuckova.cz"
        },
        nl: {
            fileTooLarge: "FOUT: Totale bestandsgrootte overschrijdt 8MB! Verklein de totale grootte van alle bestanden.",
            selectFile: "Selecteer bestand...",
            emailSubmissionSendingBtnText: "VERZENDEN...",
            emailSubmissionSucceededMsg: "E-MAIL VERZONDEN!",
            emailSubmissionFailedMsg: "ER IS EEN FOUT OPGETREDEN! E-MAIL IS NIET VERZONDEN. PROBEER HET OPNIEUW OF SCHRIJF DIRECT NAAR info@petramuckova.cz"
        },
        el: {
            fileTooLarge: "ΣΦΑΛΜΑ: Το συνολικό μέγεθος αρχείων υπερβαίνει τα 8MB! Μειώστε το συνολικό μέγεθος όλων των αρχείων.",
            selectFile: "Επιλογή αρχείου...",
            emailSubmissionSendingBtnText: "ΑΠΟΣΤΟΛΗ...",
            emailSubmissionSucceededMsg: "EMAIL ΣΤALΘΗΚΕ!",
            emailSubmissionFailedMsg: "ΠΡΟΕΚΥΨΕ ΣΦΑΛΜΑ! ΤΟ EMAIL ΔΕΝ ΣΤΑΛΘΗΚΕ. ΠΑΡΑΚΑΛΩ ΔΟΚΙΜΑΣΤΕ ΞΑΝΑ Ή ΓΡΑΨΤΕ ΑΠΕΥΘΕΙΑΣ ΣΤΟ info@petramuckova.cz"
        },
        pt: {
            fileTooLarge: "ERRO: O tamanho total dos arquivos excede 8MB! Reduza o tamanho total de todos os arquivos.",
            selectFile: "Selecionar arquivo...",
            emailSubmissionSendingBtnText: "ENVIANDO...",
            emailSubmissionSucceededMsg: "EMAIL ENVIADO!",
            emailSubmissionFailedMsg: "OCORREU UM ERRO! O EMAIL NÃO FOI ENVIADO. TENTE NOVAMENTE OU ESCREVA DIRETAMENTE PARA info@petramuckova.cz"
        },
        sv: {
            fileTooLarge: "FEL: Total filstorlek överstiger 8MB! Minska den totala storleken på alla filer.",
            selectFile: "Välj fil...",
            emailSubmissionSendingBtnText: "SKICKAR...",
            emailSubmissionSucceededMsg: "E-POST SKICKAD!",
            emailSubmissionFailedMsg: "ETT FEL UPPSTOD! E-POSTEN SKICKADES INTE. FÖRSÖK IGEN ELLER SKRIV DIREKT TILL info@petramuckova.cz"
        },
        da: {
            fileTooLarge: "FEJL: Samlet filstørrelse overstiger 8MB! Reducer den samlede størrelse af alle filer.",
            selectFile: "Vælg fil...",
            emailSubmissionSendingBtnText: "SENDER...",
            emailSubmissionSucceededMsg: "EMAIL SENDT!",
            emailSubmissionFailedMsg: "DER OPSTOD EN FEJL! EMAIL BLEV IKKE SENDT. PRØV IGEN ELLER SKRIV DIREKTE TIL info@petramuckova.cz"
        },
        fi: {
            fileTooLarge: "VIRHE: Tiedostojen kokonaiskoko ylittää 8MB! Pienennä kaikkien tiedostojen kokonaiskokoa.",
            selectFile: "Valitse tiedosto...",
            emailSubmissionSendingBtnText: "LÄHETETÄÄN...",
            emailSubmissionSucceededMsg: "SÄHKÖPOSTI LÄHETETTY!",
            emailSubmissionFailedMsg: "TAPAHTUI VIRHE! SÄHKÖPOSTIA EI LÄHETETTY. YRITÄ UUDELLEEN TAI KIRJOITA SUORAAN OSOITTEESEEN info@petramuckova.cz"
        },
        ro: {
            fileTooLarge: "EROARE: Dimensiunea totală a fișierelor depășește 8MB! Reduceți dimensiunea totală a tuturor fișierelor.",
            selectFile: "Selectați fișier...",
            emailSubmissionSendingBtnText: "TRIMITERE...",
            emailSubmissionSucceededMsg: "EMAIL TRIMIS!",
            emailSubmissionFailedMsg: "A APĂRUT O EROARE! EMAILUL NU A FOST TRIMIS. ÎNCERCAȚI DIN NOU SAU SCRIEȚI DIRECT LA info@petramuckova.cz"
        },
        hu: {
            fileTooLarge: "HIBA: A fájlok teljes mérete meghaladja a 8MB-ot! Csökkentse az összes fájl teljes méretét.",
            selectFile: "Fájl kiválasztása...",
            emailSubmissionSendingBtnText: "KÜLDÉS...",
            emailSubmissionSucceededMsg: "EMAIL ELKÜLDVE!",
            emailSubmissionFailedMsg: "HIBA TÖRTÉNT! AZ EMAIL NEM LETT ELKÜLDVE. KÉRJÜK, PRÓBÁLJA ÚJRA, VAGY ÍRJON KÖZVETLENÜL AZ info@petramuckova.cz CÍMRE"
        },
        sk: {
            fileTooLarge: "CHYBA: Celková veľkosť súborov prekročila 8MB! Zmenšite celkovú veľkosť všetkých súborov.",
            selectFile: "Vybrať súbor...",
            emailSubmissionSendingBtnText: "ODOSIELAM...",
            emailSubmissionSucceededMsg: "EMAIL ODOSLANÝ!",
            emailSubmissionFailedMsg: "NASTALA CHYBA! EMAIL NEBOL ODOSLANÝ. SKÚSTE TO PROSÍM ZNOVU, ALEBO PÍŠTE PRIAMO NA info@petramuckova.cz"
        },
        bg: {
            fileTooLarge: "ГРЕШКА: Общият размер на файловете надвишава 8MB! Моля, намалете общия размер на всички файлове.",
            selectFile: "Избери файл...",
            emailSubmissionSendingBtnText: "ИЗПРАЩАНЕ...",
            emailSubmissionSucceededMsg: "ИМЕЙЛЪТ Е ИЗПРАТЕН!",
            emailSubmissionFailedMsg: "ВЪЗНИКНА ГРЕШКА! ИМЕЙЛЪТ НЕ БЕ ИЗПРАТЕН. МОЛЯ, ОПИТАЙТЕ ОТНОВО ИЛИ ПИШЕТЕ ДИРЕКТНО НА info@petramuckova.cz"
        },
        hr: {
            fileTooLarge: "GREŠKA: Ukupna veličina datoteka prelazi 8MB! Smanjite ukupnu veličinu svih datoteka.",
            selectFile: "Odaberi datoteku...",
            emailSubmissionSendingBtnText: "SLANJE...",
            emailSubmissionSucceededMsg: "EMAIL POSLAN!",
            emailSubmissionFailedMsg: "DOŠLO JE DO GREŠKE! EMAIL NIJE POSLAN. POKUŠAJTE PONOVNO ILI PIŠITE IZRAVNO NA info@petramuckova.cz"
        },
        sl: {
            fileTooLarge: "NAPAKA: Skupna velikost datotek presega 8MB! Zmanjšajte skupno velikost vseh datotek.",
            selectFile: "Izberi datoteko...",
            emailSubmissionSendingBtnText: "POŠILJANJE...",
            emailSubmissionSucceededMsg: "E-POŠTA POSLANA!",
            emailSubmissionFailedMsg: "PRIŠLO JE DO NAPAKE! E-POŠTA NI BILA POSLANA. PROSIMO, POSKUSITE ZNOVA ALI PIŠITE NEPOSREDNO NA info@petramuckova.cz"
        },
        et: {
            fileTooLarge: "VIGA: Failide kogusuurus ületab 8MB! Vähendage kõigi failide kogusuurust.",
            selectFile: "Vali fail...",
            emailSubmissionSendingBtnText: "SAATMINE...",
            emailSubmissionSucceededMsg: "E-KIRI SAADETUD!",
            emailSubmissionFailedMsg: "TEKKIS VIGA! E-KIRJA EI SAADETUD. PALUN PROOVIGE UUESTI VÕI KIRJUTAGE OTSE AADRESSILE info@petramuckova.cz"
        },
        lv: {
            fileTooLarge: "KĻŪDA: Kopējais failu izmērs pārsniedz 8MB! Lūdzu, samaziniet visu failu kopējo izmēru.",
            selectFile: "Izvēlēties failu...",
            emailSubmissionSendingBtnText: "SŪTĪŠANA...",
            emailSubmissionSucceededMsg: "E-PASTS NOSŪTĪTS!",
            emailSubmissionFailedMsg: "RADĀS KĻŪDA! E-PASTS NETIKA NOSŪTĪTS. LŪDZU, MĒĢINIET VĒLREIZ VAI RAKSTIET TIEŠI UZ info@petramuckova.cz"
        },
        lt: {
            fileTooLarge: "KLAIDA: Bendras failų dydis viršija 8MB! Sumažinkite bendrą visų failų dydį.",
            selectFile: "Pasirinkti failą...",
            emailSubmissionSendingBtnText: "SIUNČIAMA...",
            emailSubmissionSucceededMsg: "EL. LAIŠKAS IŠSIŲSTAS!",
            emailSubmissionFailedMsg: "ĮVYKO KLAIDA! EL. LAIŠKAS NEBUVO IŠSIŲSTAS. BANDYKITE DAR KARTĄ ARBA RAŠYKITE TIESIOGIAI info@petramuckova.cz"
        },
        uk: {
            fileTooLarge: "ПОМИЛКА: Загальний розмір файлів перевищує 8MB! Зменшіть загальний розмір усіх файлів.",
            selectFile: "Вибрати файл...",
            emailSubmissionSendingBtnText: "НАДСИЛАННЯ...",
            emailSubmissionSucceededMsg: "EMAIL НАДІСЛАНО!",
            emailSubmissionFailedMsg: "СТАЛАСЯ ПОМИЛКА! EMAIL НЕ БУЛО НАДІСЛАНО. БУДЬ ЛАСКА, СПРОБУЙТЕ ЩЕ РАЗ АБО ПИШІТЬ БЕЗПОСЕРЕДНЬО НА info@petramuckova.cz"
        }
    };

    function submissionText(locale) { return submissionTranslations[locale] || submissionTranslations.cs; }


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

    const MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024;
    const MAX_ATTACHMENTS = 3;

    function initAttachments(form, { text, onError = message => root.alert(message) } = {}) {
        const inputs = [...form.querySelectorAll('.file-upload-input')];
        function paint(input) {
            const selected = input.files?.[0];
            input.parentElement.querySelector('.file-msg').textContent = selected ? selected.name : text.selectFile;
            input.parentElement.style.borderColor = selected ? '#ff3333' : '';
        }
        function validate() {
            const files = inputs.flatMap(input => [...(input.files || [])]);
            if (files.length > MAX_ATTACHMENTS || files.reduce((size, file) => size + file.size, 0) > MAX_ATTACHMENT_BYTES) {
                onError(text.fileTooLarge);
                return false;
            }
            return true;
        }
        function reset() { inputs.forEach(paint); }
        inputs.forEach(input => input.addEventListener('change', () => {
            const valid = validate();
            if (!valid) input.value = '';
            paint(input);
            if (!valid) input.parentElement.style.borderColor = '#ff0000';
        }));
        form.addEventListener('reset', () => queueMicrotask(reset));
        return { validate, reset };
    }

    // Both public forms share validation, pending state, POST handling and feedback.
    function initSubmission(form, options) {
        const button = form.querySelector('.btn-submit');
        const message = options.message;
        const text = options.text;
        message.setAttribute('role', 'status');
        message.setAttribute('aria-live', 'polite');
        message.setAttribute('aria-atomic', 'true');
        let busy = false, timer;
        function showMessage(content, success = false) {
            if (timer) root.clearTimeout(timer);
            const block = form.ownerDocument.createElement('div');
            block.className = success ? 'msg-success' : 'msg-error';
            block.textContent = content;
            message.replaceChildren(block);
            message.hidden = false;
            message.style.display = 'block';
            if (options.messageTimeout) timer = root.setTimeout(() => {
                message.style.display = 'none';
                message.replaceChildren();
            }, options.messageTimeout);
        }
        async function submit(event) {
            event.preventDefault();
            if (busy || options.canSubmit?.() === false) return;
            if (!options.validation.validate() || options.attachments?.validate() === false) return;
            const data = new root.FormData(form);
            const context = options.prepareData?.(data);
            const controls = [...form.querySelectorAll('input, select, textarea, button')].map(control => [control, control.disabled]);
            const originalText = button.textContent;
            busy = true;
            controls.forEach(([control]) => { control.disabled = true; });
            button.textContent = text.emailSubmissionSendingBtnText;
            form.setAttribute('aria-busy', 'true');
            message.replaceChildren();
            message.style.display = 'none';
            options.onBusy?.(true);
            try {
                const result = options.request ? await options.request(data) : await root.fetch(options.endpoint, {
                    method: 'POST', body: data, credentials: 'same-origin',
                });
                if (!options.request && !result.ok) throw new Error('Submission failed');
                options.onSuccess?.(result, context);
                form.reset();
                options.attachments?.reset();
                showMessage(options.successText?.(result) || text.emailSubmissionSucceededMsg, true);
            } catch (error) {
                showMessage(options.errorText?.(error) || text.emailSubmissionFailedMsg);
            } finally {
                controls.forEach(([control, disabled]) => { control.disabled = disabled; });
                button.textContent = originalText;
                form.removeAttribute('aria-busy');
                busy = false;
                options.onBusy?.(false);
                options.afterSubmit?.();
            }
        }
        form.addEventListener('submit', submit);
        return { submit, showMessage, get busy() { return busy; } };
    }

    const api = { initValidation, submissionText, initAttachments, initSubmission, MAX_ATTACHMENT_BYTES, MAX_ATTACHMENTS };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    root.SiteForm = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
