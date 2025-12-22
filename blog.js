document.addEventListener('DOMContentLoaded', function() {

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
    imgLoader.onload = function() {
        // Add the class that triggers the CSS opacity transition
        document.body.classList.add('bg-loaded');
    };

    // 4. Start downloading
    imgLoader.src = bgImageUrl;

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

    lazyLoadHero("home-section-mobile");

    // ==========================================
    // 5. LIGHTBOX LOGIC
    // ==========================================
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightboxImg');
    const triggers = document.querySelectorAll('.blog-figure img'); // Target all blog images
    // Open Lightbox
    triggers.forEach(img => {
        img.addEventListener('click', () => {
            lightboxImg.src = img.src; // Copy image source
            lightbox.classList.add('active'); // Show modal
        });
    });
    // Close Lightbox (Click anywhere)
    lightbox.addEventListener('click', () => {
        lightbox.classList.remove('active');
    });
    // Close on Escape Key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && lightbox.classList.contains('active')) {
            lightbox.classList.remove('active');
        }
    });

    /* mobile navmenu */
    const mobileNavMenuOverlay = document.getElementById('mobile-menu-overlay');
    const mobileNavMenuItems = document.querySelectorAll('.mobile-menu-item');
    const mobileNavMenuTriggerBtn = document.querySelector('.mobile-menu-trigger'); // Your hamburger button
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
        if (e.key === 'Escape' && mobileNavMenuIsOpen) toggleMobileNavMenu(false);
    });
    // 2. CLICK & NAVIGATION LOGIC
    mobileNavMenuItems.forEach(link => {
        link.addEventListener('click', (e) => {
            const href = link.getAttribute('href');

            // Internal Anchor (#)
            if (href.startsWith('#')) {
                e.preventDefault(); // Stop instant jump
                toggleMobileNavMenu(false); // Close menu first

                const target = document.querySelector(href);
                if (target) target.scrollIntoView({behavior: 'auto'});
            }
            // External Link (/)
            else {
                // Allow default behavior (page load), but close menu just in case user comes back
                toggleMobileNavMenu(false);
            }
        });
    });


    /* mobile language menu */
    const mobileLangMenuOverlay = document.getElementById('mobile-langchooser-overlay');
    const mobileLangMenuItems = document.querySelectorAll('.mobile-langchooser-item');
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
        if (e.key === 'Escape' && mobileLangMenuIsOpen) toggleMobileLangMenu(false);
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


    /*article SCROLL SPY*/
    // 1. SELECTORS
    const blogCards = document.querySelectorAll('.blog-card');
    const tocLinks = document.querySelectorAll('.toc-link');
    // 2. CONFIGURATION: The "Center Line" Strategy
    // The browser ignores the top 45% and bottom 45% of the screen.
    // It only looks at the middle 10% strip.
    // If a blog card is in that strip, it is considered "Active".
    const observerOptions = {
        root: null,
        rootMargin: '-45% 0px -45% 0px',
        threshold: 0
    };
    // 3. THE OBSERVER LOGIC
    const observer = new IntersectionObserver((entries) => {
        if (window.matchMedia('(min-width: 1400px)').matches) {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    // A. Find the ID of the title inside the currently viewed card
                    // The card is entry.target, we look for the <h1> inside it
                    const titleElement = entry.target.querySelector('h1');

                    if (titleElement && titleElement.id) {
                        const activeId = titleElement.id;

                        // B. Remove 'is-active' from ALL links (Desktop & Mobile)
                        tocLinks.forEach(link => link.classList.remove('is-active'));

                        // C. Add 'is-active' to the matching link(s)
                        // We look for any link that points to this specific ID (#post-X-title)
                        const activeLinks = document.querySelectorAll(`a[href="#${activeId}"]`);
                        activeLinks.forEach(link => link.classList.add('is-active'));
                    }
                }
            });
        }
    }, observerOptions);
    // 4. START OBSERVING
    blogCards.forEach(card => {
        observer.observe(card);
    });
    /*END of SECTION SCROLL SPY*/
});
