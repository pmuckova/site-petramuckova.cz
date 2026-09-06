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

    const t = SiteForm.submissionText(lang);

    const attachments = SiteForm.initAttachments(document.getElementById('inquiryForm'), { text: t });

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
    const validation = SiteForm.initValidation(form);

    SiteForm.initSubmission(form, {
        validation, attachments, text: t, endpoint: '/backend/contact_form_handler.php',
        message: document.getElementById('form-message'), messageTimeout: 5000,
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
