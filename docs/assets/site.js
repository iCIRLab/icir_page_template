// Shared behavior for iCIR Lab project pages. build.py does not regenerate this file.

// Autoplay muted clips only while visible; hidden translations stay paused.
const visibleVideos = new Set();
function updateVideoPlayback(video) {
    if (visibleVideos.has(video) && !document.hidden && !video.closest('[hidden]')) {
        video.play().catch(() => { /* Native controls remain available if autoplay is blocked. */ });
    } else {
        video.pause();
    }
}
const videoObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
        if (entry.isIntersecting && entry.intersectionRatio >= 0.15) visibleVideos.add(entry.target);
        else visibleVideos.delete(entry.target);
        updateVideoPlayback(entry.target);
    });
}, { threshold: [0, 0.15] });
document.querySelectorAll('video').forEach(video => videoObserver.observe(video));
document.addEventListener('visibilitychange', () => {
    visibleVideos.forEach(updateVideoPlayback);
});

const contentRoot = document.getElementById('project-content');
// Absent on single-language pages; everything below still runs for the menu.
const languageToggle = document.getElementById('language-toggle');
const languagePanels = contentRoot.querySelectorAll('.localized-content');
const languages = [...languagePanels].map(panel => panel.lang);
const languageStatus = document.getElementById('language-status');
const languageStorageKey = `content-language:${location.pathname}`;
const sectionNav = document.querySelector('.section-nav');
const sectionLinks = [...sectionNav.querySelectorAll('a')];
const siteHeader = document.querySelector('.site-header');
const topNav = document.querySelector('.top-nav');
const headerSides = [document.querySelector('.lab-brand'), document.querySelector('.top-nav-controls')];
const menuToggle = document.getElementById('section-menu-toggle');
const menuMeasure = sectionNav.cloneNode(true);
menuMeasure.removeAttribute('id');
menuMeasure.removeAttribute('aria-label');
menuMeasure.classList.add('section-nav-measure');
menuMeasure.setAttribute('aria-hidden', 'true');
menuMeasure.inert = true;
siteHeader.append(menuMeasure);
const measuredLinks = [...menuMeasure.querySelectorAll('a')];
const measuredList = menuMeasure.querySelector('ul');
let compactMenu = false;
let menuOpen = false;
let currentLanguage = languages[0];

function setMenuOpen(open, restoreFocus = false) {
    menuOpen = compactMenu && open;
    menuToggle.setAttribute('aria-expanded', String(menuOpen));
    menuToggle.setAttribute('aria-label', currentLanguage === 'ko'
        ? (menuOpen ? '섹션 메뉴 닫기' : '섹션 메뉴 열기')
        : (menuOpen ? 'Close section menu' : 'Open section menu'));
    sectionNav.hidden = compactMenu && !menuOpen;
    if (restoreFocus && compactMenu) menuToggle.focus();
}

function updateHeaderOffset() {
    // Equal side columns keep the menu centered on the full viewport.
    const sideWidth = Math.ceil(Math.max(...headerSides.map(element => element.getBoundingClientRect().width)));
    topNav.style.setProperty('--header-side-width', `${sideWidth}px`);
    const layout = getComputedStyle(topNav);
    const availableWidth = topNav.clientWidth - parseFloat(layout.paddingLeft)
        - parseFloat(layout.paddingRight) - 2 * sideWidth - 2 * parseFloat(layout.columnGap);
    const nextCompact = measuredList.getBoundingClientRect().width > availableWidth;
    if (nextCompact !== compactMenu) {
        const menuHadFocus = sectionNav.contains(document.activeElement);
        const toggleHadFocus = document.activeElement === menuToggle;
        compactMenu = nextCompact;
        siteHeader.dataset.menuCompact = String(compactMenu);
        menuToggle.hidden = !compactMenu;
        setMenuOpen(false);
        if (compactMenu && menuHadFocus) menuToggle.focus();
        if (!compactMenu && toggleHadFocus) sectionLinks[0].focus();
    }
    siteHeader.dataset.menuReady = 'true';
    document.documentElement.style.setProperty('--header-offset', `${siteHeader.getBoundingClientRect().height + 20}px`);
}
const headerObserver = new ResizeObserver(updateHeaderOffset);
headerObserver.observe(siteHeader);
headerSides.forEach(element => headerObserver.observe(element));
headerObserver.observe(measuredList);
window.addEventListener('resize', updateHeaderOffset);
document.fonts?.ready.then(updateHeaderOffset);
updateHeaderOffset();

menuToggle.addEventListener('click', () => setMenuOpen(!menuOpen));
sectionLinks.forEach(link => link.addEventListener('click', event => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (compactMenu) {
        setMenuOpen(false);
        const target = document.getElementById(link.hash.slice(1));
        if (target) {
            target.tabIndex = -1;
            target.focus({ preventScroll: true });
        }
    }
}));
document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && menuOpen) {
        event.preventDefault();
        setMenuOpen(false, true);
    }
});
document.addEventListener('click', event => {
    if (menuOpen && !siteHeader.contains(event.target)) setMenuOpen(false);
});
siteHeader.addEventListener('focusout', () => {
    requestAnimationFrame(() => {
        if (menuOpen && !siteHeader.contains(document.activeElement)) setMenuOpen(false);
    });
});

function captureReadingPosition() {
    const scrollY = window.scrollY;
    const readingLine = siteHeader.getBoundingClientRect().bottom + 20;
    const panel = [...languagePanels].find(panel => !panel.hidden);
    const sections = panel ? [...panel.querySelectorAll(':scope > section')] : [];
    for (let index = sections.length - 1; index >= 0; index--) {
        const section = sections[index];
        const rect = section.getBoundingClientRect();
        if (rect.top > readingLine) continue;
        const end = sections[index + 1]?.getBoundingClientRect().top ?? rect.bottom;
        return {
            scrollY,
            section: section.getAttribute('aria-labelledby').replace(/-(en|ko)$/, ''),
            progress: Math.min(1, (readingLine - rect.top) / Math.max(1, end - rect.top))
        };
    }
    return { scrollY };
}

function restoreReadingPosition(position, language) {
    let top = position.scrollY;
    if (position.section) {
        const section = document.getElementById(`${position.section}-${language}`)?.closest('section');
        if (section) {
            const rect = section.getBoundingClientRect();
            const end = section.nextElementSibling?.getBoundingClientRect().top ?? rect.bottom;
            const readingLine = siteHeader.getBoundingClientRect().bottom + 20;
            top = window.scrollY + rect.top + position.progress * (end - rect.top) - readingLine;
        }
    }
    window.scrollTo({ top, left: window.scrollX, behavior: 'instant' });
}

let languageScrollFrame;
function setContentLanguage(language, announce = false, preservePosition = false) {
    if (!languages.includes(language)) return;
    // Capture the viewport before hiding a panel; the URL hash may refer to an older section.
    const readingPosition = preservePosition ? captureReadingPosition() : null;
    if (readingPosition) {
        cancelAnimationFrame(languageScrollFrame);
        document.documentElement.classList.add('switching-language');
    }
    currentLanguage = language;
    document.documentElement.lang = language;
    if (languageToggle) {
        languageToggle.dataset.language = language;
        languageToggle.lang = language;
        languageToggle.setAttribute('aria-label', language === 'ko'
            ? '현재 본문 언어: 한국어. 영어로 전환합니다.'
            : 'Current content language: English. Switch to Korean.');
        languageToggle.title = language === 'ko' ? 'Switch to English' : '한국어로 전환';
    }
    languagePanels.forEach(panel => {
        panel.hidden = panel.lang !== language;
        if (panel.hidden) panel.querySelectorAll('video').forEach(video => video.pause());
    });
    // Shared header and demo copy: one element per language, generated by build.py.
    document.querySelectorAll('[data-lang]').forEach(element => {
        element.hidden = element.dataset.lang !== language;
    });
    sectionNav.lang = language;
    menuToggle.lang = language;
    sectionNav.setAttribute('aria-label', language === 'ko' ? '페이지 목차' : 'Page sections');
    sectionLinks.forEach(link => {
        if (link.dataset.section) {
            const heading = document.getElementById(`${link.dataset.section}-${language}`);
            link.setAttribute('href', `#${heading.id}`);
            link.textContent = heading.textContent;
        } else {
            link.textContent = link.getAttribute(`data-label-${language}`);
        }
    });
    measuredLinks.forEach((link, index) => { link.textContent = sectionLinks[index].textContent; });
    menuMeasure.lang = language;
    updateHeaderOffset();
    setMenuOpen(menuOpen);
    // Translate the URL fragment without navigating away from the current reading position.
    const anchoredLink = sectionLinks.find(link => link.dataset.section &&
        languages.some(lang => location.hash === `#${link.dataset.section}-${lang}`));
    if (anchoredLink && location.hash !== anchoredLink.hash) {
        history.replaceState(history.state, '', anchoredLink.hash);
    }
    if (announce) {
        languageStatus.lang = language;
        languageStatus.textContent = language === 'ko'
            ? '전체 본문을 한국어로 표시합니다.'
            : 'All content is now displayed in English.';
    }
    try {
        localStorage.setItem(languageStorageKey, language);
    } catch {
        // Language switching also works when browser storage is unavailable.
    }
    if (readingPosition) {
        restoreReadingPosition(readingPosition, language);
        languageScrollFrame = requestAnimationFrame(() => {
            document.documentElement.classList.remove('switching-language');
        });
    }
}

languageToggle?.addEventListener('click', () => {
    const next = languages[(languages.indexOf(currentLanguage) + 1) % languages.length];
    setContentLanguage(next, true, true);
});

function hashLanguage() {
    const target = document.getElementById(location.hash.slice(1));
    return target?.closest('.localized-content')?.lang;
}

window.addEventListener('hashchange', () => {
    const language = hashLanguage();
    if (language && language !== currentLanguage) {
        setContentLanguage(language);
        document.getElementById(location.hash.slice(1)).scrollIntoView();
    }
});

let storedLanguage = null;
try {
    storedLanguage = localStorage.getItem(languageStorageKey);
} catch {
    // Fall back to the page's first language.
}
setContentLanguage(hashLanguage() || (languages.includes(storedLanguage) ? storedLanguage : languages[0]));
