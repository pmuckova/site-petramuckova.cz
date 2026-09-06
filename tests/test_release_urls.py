import contextlib
import html
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

import release


class ReleaseUrlTests(unittest.TestCase):
    def render(self, content, version='v2026-09+1'):
        # Exercise only URL rewriting in a disposable directory, never release/.
        with tempfile.TemporaryDirectory(prefix='muckova-url-test-') as directory:
            target = Path(directory) / 'cs' / 'shop.html'
            target.parent.mkdir()
            target.write_text(content, encoding='utf-8')
            with patch.object(release, 'RELEASE_DIR', directory), contextlib.redirect_stdout(io.StringIO()):
                release.append_version_to_public_urls(version)
            return target.read_text(encoding='utf-8')

    def links(self, urls, version='v2026-09+1'):
        content = ''.join(f'<a href="{html.escape(url, quote=True)}">Link</a>' for url in urls)
        soup = BeautifulSoup(self.render(content, version), 'html.parser')
        return [anchor['href'] for anchor in soup.select('a[href]')]

    def test_every_language_and_page_type_gets_the_site_version(self):
        urls = []
        for lang in release.CONTENT_DIRS:
            urls.extend((f'/{lang}', f'/{lang}/'))
            for page in ('index', 'blog', 'shop'):
                urls.extend(f'/{lang}/{page}{suffix}' for suffix in ('', '/', '.html'))
        for original, updated in zip(urls, self.links(urls)):
            with self.subTest(url=original):
                self.assertEqual(urlsplit(updated).path, original)
                self.assertEqual(parse_qs(urlsplit(updated).query), {'v': ['v2026-09+1']})

    def test_absolute_same_site_links_are_versioned(self):
        urls = [f'{origin}/{page}'
                for origin in ('https://petramuckova.cz', 'https://www.petramuckova.cz',
                               'http://petramuckova.cz', '//www.petramuckova.cz')
                for page in ('cs/blog', 'cs/blog/', 'cs/shop', 'en/shop.html')]
        for original, updated in zip(urls, self.links(urls)):
            with self.subTest(url=original):
                before, after = urlsplit(original), urlsplit(updated)
                self.assertEqual((after.scheme, after.netloc, after.path),
                                 (before.scheme, before.netloc, before.path))
                self.assertEqual(parse_qs(after.query)['v'], ['v2026-09+1'])

    def test_existing_query_and_fragment_survive_and_old_versions_are_replaced(self):
        urls = ['/cs/shop?category=parts&v=old&v=older#order',
                '/en/blog.html?query=A%2BB&empty=#post-2-title']
        updated = self.links(urls)
        self.assertEqual(parse_qs(urlsplit(updated[0]).query),
                         {'category': ['parts'], 'v': ['v2026-09+1']})
        self.assertEqual(urlsplit(updated[0]).fragment, 'order')
        self.assertEqual(parse_qs(urlsplit(updated[1]).query, keep_blank_values=True),
                         {'query': ['A+B'], 'empty': [''], 'v': ['v2026-09+1']})
        self.assertEqual(urlsplit(updated[1]).fragment, 'post-2-title')
        self.assertIn('v=v2026-09%2B1', updated[0])

    def test_rewriting_is_idempotent_and_supports_both_quote_styles(self):
        source = '<a href="/cs/shop">Shop</a><a href=\'/cs/blog/#post-8-title\'>Blog</a>'
        once = self.render(source)
        self.assertEqual(self.render(once), once)
        self.assertIn('href="/cs/shop?v=v2026-09%2B1"', once)
        self.assertIn("href='/cs/blog/?v=v2026-09%2B1#post-8-title'", once)

    def test_non_page_links_are_unchanged(self):
        urls = ['#order', '#basket', '/', 'mailto:info@petramuckova.cz', 'tel:+420604487263',
                '/assets/desktop/eshop-placeholder.webp', '/shop.js?v=asset-hash',
                '/cs/shop-extra', '/cs/blog/category', '/unknown/shop',
                'https://example.com/cs/shop', '//petramuckova.cz.example.com/cs/blog']
        self.assertEqual(self.links(urls), urls)

    def test_canonical_alternates_social_metadata_and_assets_stay_unversioned(self):
        source = '''<link rel="canonical" href="https://www.petramuckova.cz/cs/shop">
<link rel="alternate" hreflang="en" href="https://www.petramuckova.cz/en/shop">
<meta property="og:url" content="https://www.petramuckova.cz/cs/shop">
<script src="/shop.js?v=asset-hash"></script>
<a href="/cs/shop#order">Order</a>'''
        before = BeautifulSoup(source, 'html.parser')
        after = BeautifulSoup(self.render(source), 'html.parser')
        for selector in ('link[rel=canonical]', 'link[rel=alternate]', 'meta[property="og:url"]', 'script'):
            self.assertEqual(str(after.select_one(selector)), str(before.select_one(selector)))
        self.assertEqual(after.a['href'], '/cs/shop?v=v2026-09%2B1#order')

    def test_without_a_release_version_nothing_is_changed(self):
        source = '<a href="/cs/shop#order">Order</a>'
        self.assertEqual(self.render(source, None), source)


if __name__ == '__main__':
    unittest.main()
