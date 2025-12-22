/* HERO CONTENT ANIMATION */

const forwardToBackwardDelay = 3000;
const backwardToForwardDelay = 500;

const forwardsPerCharacter = 0.10;
const backwardsPerCharacter = 0.04;

function getBackwardsAnimation(el, realWidth, charCount) {
    return el.animate(
        [
            {width: realWidth},
            {width: "0"},
        ],
        {
            duration: charCount * backwardsPerCharacter * 1000,
            easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
            fill: 'forwards'
        }
    );
}

function getForwardsAnimation(el, realWidth, charCount) {
    return el.animate(
        [
            {width: "0"},
            {width: realWidth}
        ],
        {
            duration: charCount * forwardsPerCharacter * 1000,
            easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
            fill: 'forwards'
        }
    );
}

function caretBlinking(el) {
    el.animate(
        [
            {borderColor: "transparent", offset: 0},
            {borderColor: "transparent", offset: 0.5},
            {borderColor: "var(--accent)", offset: 0.5},
            {borderColor: "var(--accent)", offset: 1}
        ],
        {
            duration: 1050,
            easing: `ease`,
            iterations: Infinity
        }
    );
}

function reinstallHeroContentAnimations() {
    if (document.getElementById('home-section').offsetWidth > 0) {

        document.querySelectorAll('#home-section .sys-label')
        .forEach((el) => {
            if (el.getAnimations().length > 0) {
                return;
            }

            const isCJK = el.classList.contains('sys-label-cjk');
            const realWidth = el.clientWidth + 'px';
            const charCount = el.textContent.trim().length * (isCJK ? 2 : 1);

            const backwardsAnimation =
                getBackwardsAnimation(el, realWidth, charCount);
            backwardsAnimation.pause();

            const forwardsAnimation =
                getForwardsAnimation(el, realWidth, charCount);

            caretBlinking(el);

            forwardsAnimation.onfinish = () => {
                setTimeout(() => {
                    forwardsAnimation.cancel();
                    backwardsAnimation.play();
                }, forwardToBackwardDelay);
            };

            backwardsAnimation.onfinish = () => {
                setTimeout(() => {
                    backwardsAnimation.cancel();
                    forwardsAnimation.play();
                }, backwardToForwardDelay);
            };
        });
    }

    if (document.getElementById('home-section-mobile').offsetWidth > 0) {

        document.querySelectorAll('#home-section-mobile .sys-label-stack')
        .forEach((stackEl) => {
            const isCJK = stackEl.classList.contains('sys-label-cjk');
            const [line1, line2] =
                stackEl.querySelectorAll('.sys-line');

            if (line1.getAnimations().length > 0) {
                return;
            }

            //////////////////////

            const line1RealWidth = line1.clientWidth + 'px';
            const line1CharCount = line1.textContent.trim().length * (isCJK ? 2
                : 1);

            const line1Backwards =
                getBackwardsAnimation(line1, line1RealWidth, line1CharCount);
            line1Backwards.pause();

            const line1Forwards =
                getForwardsAnimation(line1, line1RealWidth, line1CharCount);

            caretBlinking(line1);

            //////////////////////

            const line2RealWidth = line2.clientWidth + 'px';
            const line2CharCount = line2.textContent.trim().length * (isCJK ? 2
                : 1);

            const line2Backwards =
                getBackwardsAnimation(line2, line2RealWidth, line2CharCount);
            line2Backwards.pause();

            const line2Forwards =
                getForwardsAnimation(line2, line2RealWidth, line2CharCount);
            line2Forwards.pause();

            caretBlinking(line2);

            //////////////////////

            line1.style.visibility = 'visible';

            line1Forwards.onfinish = () => {
                setTimeout(() => {
                    line1Forwards.cancel();
                    line1Backwards.play();
                }, forwardToBackwardDelay);
            };
            line1Backwards.onfinish = () => {
                setTimeout(() => {
                    line1Backwards.cancel();
                    line1.style.visibility = 'hidden';
                    line2.style.visibility = 'visible';
                    line2Forwards.play();
                }, backwardToForwardDelay);
            };
            line2Forwards.onfinish = () => {
                setTimeout(() => {
                    line2Forwards.cancel();
                    line2Backwards.play();
                }, forwardToBackwardDelay);
            };
            line2Backwards.onfinish = () => {
                setTimeout(() => {
                    line2Backwards.cancel();
                    line2.style.visibility = 'hidden';
                    line1.style.visibility = 'visible';
                    line1Forwards.play();
                }, backwardToForwardDelay);
            };
        });
    }
}

/* END OF HERO CONTENT ANIMATION */

document.addEventListener('DOMContentLoaded', function () {
    /* HERO SECTION HEIGHT SETTER */
    (function () {
        const orientationMQ = window.matchMedia('(orientation: portrait)');
        const heroCSS = document.getElementById('home-section-mobile').style;

        const setHeroSectionHeightOnMobile = () => {
            heroCSS.height = window.innerHeight + 'px';
        };

        setHeroSectionHeightOnMobile();
        orientationMQ.addEventListener('change', function (e) {
            window.requestAnimationFrame(setHeroSectionHeightOnMobile);
        });
    })();
    /* end of HERO SECTION HEIGHT SETTER */

    const selects = document.querySelectorAll('.custom-select');
    selects.forEach(select => {
        new Choices(select,
            {searchEnabled: false, itemSelectText: '', shouldSort: false});
    });

    // Mobile inquiry-btn
    function gotoContact(e) {
        e.preventDefault();
        document.querySelector("#contact")?.scrollIntoView(
            {behavior: 'smooth'});
    }

    const inquiryBtn = document.querySelector('#inquiry-btn');
    if (inquiryBtn) {
        inquiryBtn.addEventListener('click', function (e) {
            gotoContact(e);
        });
        inquiryBtn.addEventListener('touchstart', function (e) {
            gotoContact(e);
        });
    }

    /* =========================================
       LAZY LOAD BACKGROUND IMAGE
       ========================================= */
    // 1. Define the path relative to the HTML file location
    // Since your HTML is in /cs/ and assets are in ../assets/
    // const bgImageUrl = '../assets/bg-texture.jpg';
    let bgImageUrl = new URL(getComputedStyle(document.body, "::before")
    .backgroundImage.slice(5, -2));

    // 2. Create a new Image object in memory (not in DOM)
    let imgLoader = new Image();

    // 3. Define what happens when it finishes downloading
    imgLoader.onload = function () {
        // Add the class that triggers the CSS opacity transition
        document.body.classList.add('bg-loaded');
    };

    // 4. Start downloading
    imgLoader.src = bgImageUrl;

    /* =========================================
       2. HERO IMAGE LAZY FADE-IN
       ========================================= */
    function lazyLoadHero(id) {
        let element = document.getElementById(id);
        if (!element) {
            return;
        }
        let computedStyle = getComputedStyle(element, "::before")
        .backgroundImage.split(',');

        bgImageUrl = new URL(computedStyle[computedStyle.length - 1]
        .trim().slice(5, -2));

        // 2. Create a new Image object in memory (not in DOM)
        imgLoader = new Image();

        // 3. Define what happens when it finishes downloading
        imgLoader.onload = function () {
            // Add the class that triggers the CSS opacity transition
            element.classList.add('loaded');
        };

        // 4. Start downloading
        imgLoader.src = bgImageUrl;
    }

    lazyLoadHero("home-section");       // Desktop ID
    lazyLoadHero("home-section-mobile"); // Mobile ID

    // Detect current language from HTML lang attribute or URL path
    const lang = document.documentElement.lang || 'cs';

    const translations = {
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

    const t = translations[lang] || translations.cs;

    function checkTotalFileSize() {
        let totalSize = 0;
        document.querySelectorAll('.file-upload-input').forEach(input => {
            if (input.files[0]) {
                totalSize += input.files[0].size;
            }
        });
        return totalSize;
    }

    document.querySelectorAll('.file-upload-input').forEach(input => {
        input.addEventListener('change', function () {
            if (this.files[0]) {
                const totalSize = checkTotalFileSize();
                if (totalSize > 8388608) {
                    alert(t.fileTooLarge);
                    this.value = "";
                    this.parentElement.querySelector(
                        '.file-msg').textContent = t.selectFile;
                    this.parentElement.style.borderColor = "#ff0000";
                } else {
                    this.parentElement.querySelector(
                        '.file-msg').textContent = this.files[0].name;
                    this.parentElement.style.borderColor = "#ff3333";
                }
            }
        });
    });

    /* =========================================
       4. FAQ ACCORDION (One at a time)
       ========================================= */
    const details = document.querySelectorAll("details");

    function expandFaq(e, targetDetail) {
        // If we are clicking a summary to open it
        if (e.target.tagName.toLowerCase() === 'summary' || e.target.closest(
            'summary')) {
            // Close all others
            details.forEach((detail) => {
                if (detail !== targetDetail) {
                    detail.removeAttribute("open");
                }
            });
        }
    }

    details.forEach((targetDetail) => {
        targetDetail.addEventListener("click", (e) => {
            expandFaq(e, targetDetail);
        });
    });

    const form = document.getElementById('inquiryForm');

    function validateInput(input) {
        const warning = input.nextElementSibling;
        if (!warning || !warning.classList.contains('warning-msg')) {
            return;
        }

        input.classList.remove('input-warning');
        warning.style.display = 'none';

        if (input.hasAttribute('required') && !input.value) {
            input.classList.add('input-warning');
            warning.textContent = "Toto pole je povinné.";
            warning.style.display = 'block';
            return;
        }
        if (input.type === 'email' && input.value && !/\S+@\S+\.\S+/.test(
            input.value)) {
            input.classList.add('input-warning');
            warning.textContent = "Neplatný formát emailu.";
            warning.style.display = 'block';
        }
        if (input.id === 'phoneInput' && input.value && !/^[\d\s+]{9,20}$/.test(
            input.value)) {
            input.classList.add('input-warning');
            warning.textContent = "Zadejte platné telefonní číslo.";
            warning.style.display = 'block';
        }
        if (input.name === 'year' && input.value && parseInt(input.value)
            < 1900) {
            input.classList.add('input-warning');
            warning.textContent = "Zadejte platný rok.";
            warning.style.display = 'block';
        }
    }

    document.querySelectorAll('.validate-me').forEach(input => {
        input.addEventListener('input', () => validateInput(input));
        input.addEventListener('change', () => validateInput(input));
    });

    form?.addEventListener('submit', async (e) => {
        e.preventDefault();

        let valid = true;
        document.querySelectorAll('.validate-me').forEach(input => {
            validateInput(input);
            if (input.classList.contains('input-warning')) {
                valid = false;
            }
        });

        if (valid) {
            const btn = form.querySelector('.btn-submit');
            const originalText = btn.innerText;
            btn.innerText = t.emailSubmissionSendingBtnText;
            btn.disabled = true;

            const formData = new FormData(form);

            try {
                const response = await fetch(
                    '/backend/contact_form_handler.php',
                    {
                        method: 'POST',
                        body: formData,
                        credentials: 'same-origin'
                    });
                const msgDiv = document.getElementById('form-message');
                msgDiv.style.display = 'block';

                if (response.ok) {
                    msgDiv.innerHTML = `<div class="msg-success">${t.emailSubmissionSucceededMsg}</div>`;
                    form.reset();
                } else {
                    msgDiv.innerHTML = `<div class="msg-error">${t.emailSubmissionFailedMsg}</div>`;
                }

                // Hide message after 5 seconds ===
                setTimeout(() => {
                    msgDiv.style.display = 'none';
                    msgDiv.innerHTML = ''; // Optional: Clear the text content
                }, 5000);

            } catch (err) {
                console.error(err);
            } finally {
                btn.innerText = originalText;
                btn.disabled = false;
            }
        }
    });

    /* desktop navmenu links */
    const desktopNavMenuItems = document.querySelectorAll('.nav-links a');
    desktopNavMenuItems.forEach(link => {
        link.addEventListener('click', function (e) {
            const href = link.getAttribute('href');

            // Internal Anchor (#)
            if (href.startsWith('#')) {
                e.preventDefault(); // Stop instant jump

                // Scroll to target
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({behavior: 'smooth'});
                }
            }
        });
    });

    /* mobile navmenu */
    const mobileNavMenuOverlay = document.getElementById('mobile-menu-overlay');
    const mobileNavMenuItems = document.querySelectorAll('.mobile-menu-item');
    const mobileNavMenuTriggerBtn = document.querySelector(
        '.mobile-menu-trigger'); // Your hamburger button
    // --- STATE MANAGEMENT ---
    let mobileNavMenuIsOpen = false;

    // 1. OPEN / CLOSE LOGIC
    function toggleMobileNavMenu(show) {
        if (show) {
            mobileNavMenuOverlay.style.display = 'block';
            mobileNavMenuIsOpen = true;
        } else {
            mobileNavMenuOverlay.style.display = 'none';
            mobileNavMenuIsOpen = false;
        }
    }

    // Connect to your Hamburger Button
    mobileNavMenuTriggerBtn.addEventListener('click', () => {
        toggleMobileNavMenu(!mobileNavMenuIsOpen);
    });
    mobileNavMenuTriggerBtn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        toggleMobileNavMenu(!mobileNavMenuIsOpen);
    });
    // Close on Escape Key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && mobileNavMenuIsOpen) {
            toggleMobileNavMenu(false);
        }
    });
    // 2. CLICK & NAVIGATION LOGIC
    mobileNavMenuItems.forEach(link => {
        link.addEventListener('click', (e) => {
            const href = link.getAttribute('href');

            // Internal Anchor (#)
            if (href.startsWith('#')) {
                e.preventDefault(); // Stop instant jump
                toggleMobileNavMenu(false); // Close menu first

                // Scroll to target
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({behavior: 'auto'});
                }
            }
            // External Link (/blog)
            else {
                // Allow default behavior (page load), but close menu just in case user comes back
                toggleMobileNavMenu(false);
            }
        });
    });

    /* mobile language menu */
    const mobileLangMenuOverlay = document.getElementById(
        'mobile-langchooser-overlay');
    const mobileLangMenuItems = document.querySelectorAll(
        '.mobile-langchooser-item');
    const mobileLangMenuTriggerBtn = document.querySelector('.copy-right'); // Your hamburger button
    // --- STATE MANAGEMENT ---
    let mobileLangMenuIsOpen = false;

    // 1. OPEN / CLOSE LOGIC
    function toggleMobileLangMenu(show) {
        if (show) {
            mobileLangMenuOverlay.style.display = 'block';
            mobileLangMenuIsOpen = true;
        } else {
            mobileLangMenuOverlay.style.display = 'none';
            mobileLangMenuIsOpen = false;
        }
    }

    // Connect to your Hamburger Button
    mobileLangMenuTriggerBtn.addEventListener('click', () => {
        toggleMobileLangMenu(!mobileLangMenuIsOpen);
    });
    mobileLangMenuTriggerBtn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        toggleMobileLangMenu(!mobileLangMenuIsOpen);
    });
    // Close on Escape Key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && mobileLangMenuIsOpen) {
            toggleMobileLangMenu(false);
        }
    });
    // 2. CLICK & NAVIGATION LOGIC
    mobileLangMenuItems.forEach(link => {
        link.addEventListener('click', (e) => {

            // const href = link.getAttribute('href');
            toggleMobileLangMenu(false); // Close menu first
            //
            // // Scroll to target
            // window.location.href = href;
        });
    });
    /*SECTION SCROLL SPY*/
    const observerOptions = {
        root: null,
        rootMargin: '-45% 0px -45% 0px', // Active line in middle of screen
        threshold: 0
    };
    const sectionObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                // 1. Get ID of section currently on screen
                let id = entry.target.id;

                // Fix ID Mismatch (if your section is 'home-section' but link is '#home')
                if (id === 'home-section') {
                    id = 'home';
                }

                desktopNavMenuItems.forEach((link) => {
                    link.classList.remove("active-link");
                    // Check if href contains the ID (e.g. href="#specs" contains "specs")
                    if (link.getAttribute("href").includes(id)) {
                        link.classList.add("active-link");
                    }
                });

                // 2. Remove active class from ALL items
                mobileNavMenuItems.forEach(
                    item => item.classList.remove('is-active'));

                // 3. Add active class to matching item
                const activeMobileNavLink = document.querySelector(
                    `.mobile-menu-item[data-target="${id}"]`);
                if (activeMobileNavLink) {
                    activeMobileNavLink.classList.add('is-active');
                }
            }
        });
    }, observerOptions);
    // Observe all sections that have an ID
    document.querySelectorAll('section[id], header[id]').forEach(
        section => {
            sectionObserver.observe(section);
        });
    /*END of SECTION SCROLL SPY*/

    /* HERO CONTENT ANIMATION */
    document.fonts.ready.then(() => {
        reinstallHeroContentAnimations();

        const onDesktop = window.matchMedia('(min-width: 1400px)');

        function handleDisplayChange(e) {
            reinstallHeroContentAnimations();
        }

        onDesktop.addEventListener('change', handleDisplayChange);
    });
});
