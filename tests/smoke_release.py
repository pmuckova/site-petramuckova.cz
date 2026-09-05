"""Run the complete release pipeline in a disposable tree, leaving release/ alone.

Uses existing local npm dependencies; does not install or download anything.
Run with .venv/bin/python tests/smoke_release.py.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def main():
    catalog = json.loads((ROOT / 'shop/catalog.json').read_text())
    release_before = {str(p.relative_to(ROOT / 'release')): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in (ROOT / 'release').rglob('*') if p.is_file()}
    with tempfile.TemporaryDirectory(prefix='muckova-release-smoke-') as directory:
        workspace = Path(directory)
        for filename in ['release.py', 'build_shop.py', 'main.css', 'blog.css', 'shop.css',
                         'index.js', 'blog.js', 'shop.js', 'form.js', 'favicon.ico', 'robots.txt',
                         'BingSiteAuth.xml']:
            shutil.copy2(ROOT / filename, workspace / filename)
        for verification in ROOT.glob('seznam-*.txt'):
            shutil.copy2(verification, workspace / verification.name)
        shutil.copytree(ROOT / 'shop', workspace / 'shop')
        (workspace / 'assets').symlink_to(ROOT / 'assets', target_is_directory=True)
        for language in catalog['languages']:
            shutil.copytree(ROOT / language, workspace / language)
        for tool_dir in ('cssnano', 'terser', 'html-minifier'):
            target = workspace / tool_dir
            target.mkdir()
            for source in (ROOT / tool_dir).iterdir():
                if source.is_file() and source.suffix in ('.json', '.js'):
                    shutil.copy2(source, target / source.name)
            (target / 'node_modules').symlink_to(ROOT / tool_dir / 'node_modules', target_is_directory=True)
        (workspace / 'backend').mkdir()
        # A minimal non-secret fixture exercises root config copying/rendering.
        (workspace / 'backend/.htaccess').write_text(
            'Header always set X-Site-Release "{{RELEASE_VERSION}}"\n'
            'RewriteRule ^$ /cs/?v={{RELEASE_VERSION_URL}} [L,R=302,NE]\n'
            'RewriteRule ^([a-z]{2})/shop/?$ $1/shop.html [L]\n'
        )
        shutil.copy2(ROOT / 'backend/.user.ini', workspace / 'backend/.user.ini')
        subprocess.run([sys.executable, 'release.py', 'main', 'shop-smoke-test'], cwd=workspace, check=True)
        release = workspace / 'release'
        for filename in ('shop.css', 'shop.js', 'form.js', 'sitemap.xml', '.htaccess', '.user.ini'):
            assert (release / filename).stat().st_size > 0, filename
        assert (release / '.user.ini').read_bytes() == (ROOT / 'backend/.user.ini').read_bytes()
        assert 'position:sticky' in (release / 'shop.css').read_text().replace(' ', '')
        for language in catalog['languages']:
            soup = BeautifulSoup((release / language / 'shop.html').read_text(), 'html.parser')
            assert len(soup.select('.shop-product')) == len(catalog['products']), language
            assert soup.select_one('#catalog > .shop-catalog-notes + .shop-grid')
            assert soup.select_one('link[rel=canonical]')['href'].endswith(f'/{language}/shop')
            assert all(image['src'].startswith('https://cdn.jsdelivr.net/gh/pmuckova/site-petramuckova.cz@main/') for image in soup.select('.shop-product img'))
            assert len(soup.select('img[data-placeholder]')) == sum(not p['image'] for p in catalog['products'])
            assert (release / catalog['placeholderImage'].lstrip('/')).is_file()
            config = json.loads(soup.select_one('#shop-config').string)
            assert config['locale'] == language
            assert all(product['price'] == catalog['products'][index]['price'] for index, product in enumerate(config['products']))
            configured_prices = {
                product['id']: [profile['price'] for profile in product['wizard']['profiles']]
                for product in config['products'] if product.get('kind') == 'wizard'
            }
            assert configured_prices == {
                'skoda-ohv-camshaft': [5600, 5600, 11400, 11400, 13200, 11400],
                'taz-camshaft': [4400, 4400, 11500, 15500],
            }
            assert soup.select_one('.shop-product > h3.shop-product-title')
            for card in soup.select('.shop-product'):
                source_product = next(product for product in catalog['products'] if product['id'] == card['id'])
                wizard = card.select_one('form[data-wizard]')
                assert len(card.find_all(recursive=False)) == 4
                assert card.find(recursive=False).name == 'h3'
                assert card.select_one(':scope > .shop-photo img')
                assert card.select_one(':scope > .shop-product-content > .shop-product-body .shop-description')
                if wizard:
                    assert len(wizard.select('input[name=profile]')) == len(source_product['wizard']['profiles'])
                    expected_fields = source_product['wizard']['fields']
                    assert len(wizard.select('input[type=number][required]')) == sum(
                        field['type'] == 'number' and field['required'] for field in expected_fields)
                    assert len(card.select('.shop-description')) == len(
                        source_product['translations'][language]['description'].split('\n\n'))
                    assert wizard.select_one('button[type=submit].btn-submit')
                    assert not wizard.select('.mandatory-note, [id$="-profile-title"]')
                    bearing = wizard.select_one('[data-bearing]')
                    profile_fields = wizard.select_one('.shop-profile-table > tbody[data-profile-fields][hidden]')
                    assert profile_fields
                    if source_product['wizard']['bearings']:
                        assert bearing and profile_fields.select_one(':scope > tr[data-bearing-fields][hidden]')
                    else:
                        assert not bearing and not wizard.select('[data-bearing-fields]')
                    assert not wizard.select(':scope > h4.form-section-title')
                    profiles = wizard.select_one(':scope > fieldset.shop-profile-options:not([aria-labelledby])')
                    assert profiles
                    assert wizard.find(recursive=False) is profiles
                    legend = profiles.find('legend', recursive=False)
                    assert legend['class'] == ['shop-sr-only']
                    assert legend.get_text() == config['text']['configure']
                    assert len(profiles.select('thead > tr > th')) == 4
                    for option in profiles.select('tbody.shop-profile-option'):
                        rows = option.find_all('tr', recursive=False)
                        assert len(rows) == 2
                        cells = rows[0].find_all('td', recursive=False)
                        assert len(cells) == 4
                        assert cells[0].select_one('input[type=radio]')
                        assert [cell['rowspan'] for cell in cells[1:]] == ['2', '2', '2']
                        assert 'shop-profile-price' in cells[-1]['class']
                        assert len(rows[1].find_all('td', recursive=False)) == 1
                        assert rows[1].select_one('td > .shop-profile-description')
                    field_rows = profile_fields.select(':scope > tr.shop-engine-field')
                    assert len(field_rows) == len(expected_fields)
                    assert all(row.th['scope'] == 'row' and row.td['colspan'] == '3' for row in field_rows)
                    assert [field['name'] for field in profile_fields.select('[data-engine-field]')] == [
                        field['id'] for field in expected_fields]
                    assert all(field.has_attr('disabled') for field in profile_fields.select('[data-engine-field]'))
                    assert 'Ø' not in wizard.get_text()
                    assert not card.select('[data-quantity], [data-change]')
                else:
                    item_form = card.select_one('form[data-order-product]')
                    assert item_form.select_one('table.shop-profile-table input[type=radio][name=option]')
                    assert item_form.select_one('tbody[data-profile-fields][hidden] input[data-order-quantity][disabled]')
                    assert item_form.select_one('tbody[data-profile-fields] button[type=submit].btn-submit[disabled]')
                    assert not card.select('.shop-prices, .shop-product-order, [data-change], [data-quantity]')
                    assert not card.select('.shop-dealer-minimum')
                    assert item_form.select_one('input[data-order-quantity]')['max'] == '9999'
                photo_links = card.select('.shop-photo-link')
                for photo_link in photo_links:
                    assert photo_link['href'] == photo_link.img['src']
                    assert photo_link.select_one(':scope > .tech-frame > img')
                if source_product.get('images'):
                    assert bool(card.select_one('.shop-photo-gallery')) == (len(source_product['images']) > 1)
                    assert len(photo_links) == len(source_product['images'])
                    for photo_link, source_image in zip(photo_links, source_product['images']):
                        assert photo_link['href'].endswith(source_image['src'])
                        assert photo_link.img['alt'] == source_image['alt'][language]
                        assert (int(photo_link.img['width']), int(photo_link.img['height'])) == (source_image['width'], source_image['height'])
                        relative_path = source_image['src'].lstrip('/')
                        assert (release / relative_path).read_bytes() == (ROOT / relative_path).read_bytes()
                assert not card.select('.blog-img-frame')
            assert soup.select_one('dialog#shop-lightbox.lightbox-modal .lightbox-img')
            assert soup.select_one('script[src*="choices.js@11.1.0"][defer]')
            assert soup.select_one('link[href*="choices.js@11.1.0"]')
            assert len(soup.select('select[data-order-variant]')) == sum(len(option['variantIds']) > 1 for p in catalog['products'] for option in p.get('options', []))
            assert urlsplit(soup.select_one('#navLinks > li > a.active-link')['href']).path == f'/{language}/shop'
            assert soup.select_one('.blog-sidebar > #basket.toc-wrapper')
            assert soup.select_one('main .shop-layout > .shop-sidebar > #basket')
            assert soup.main.find_next_sibling('footer') is soup.footer
            assert not soup.select_one('#basket-clear')
            order = soup.select_one('#order.section')
            assert 'blog-card' not in order['class']
            assert order.select_one(':scope > .contact-intro + form.terminal-form')
            assert order.select_one('.contact-intro > h2').get_text() == config['text']['checkout']
            assert order.select_one('.contact-sub-1').get_text() == config['text']['confirmation']
            assert order.select_one('.mandatory-note').get_text() == config['text']['requiredFields']
            assert not order.select('label small')
            assert 'optional' not in config['text']
            for field_id, name, field_type in (('order-company', 'company', 'text'), ('order-phone', 'phone', 'tel')):
                field = order.find(id=field_id)
                assert field['name'] == name and field['type'] == field_type
                assert not field.has_attr('required')
                assert order.find('label', attrs={'for': field_id}).get_text() == config['text'][name]
            assert order.select_one('#order-street[required]')
            assert order.find('label', attrs={'for': 'order-street'}).get_text() == config['text']['street'] + ' *'
            assert order.select_one('h4#order-delivery-title.form-section-title + fieldset[aria-labelledby="order-delivery-title"]')
            assert order.select_one('h4#order-notes-title.form-section-title + textarea[aria-labelledby="order-notes-title"]')
            assert order.select_one('form[novalidate]')
            assert len(order.select('.validate-me + .warning-msg')) == 7
            main = BeautifulSoup((release / language / 'index.html').read_text(), 'html.parser')
            for page, controller in ((main, 'index.js'), (soup, 'shop.js')):
                scripts = [node['src'] for node in page.select('script[src]')]
                shared = next(src for src in scripts if '/form.js' in src)
                assert Path(shared.split('?')[0]).name == 'form.js'
                assert (release / 'form.js').is_file()
                assert scripts.index(shared) < next(i for i, src in enumerate(scripts) if f'/{controller}' in src)
            assert not order.select('#order-extra, [name="addressExtra"]')
            assert 'addressExtra' not in config['text']
            assert 'bg-loaded' in soup.body['class']
            assert any('/blog.css?' in link['href'] for link in soup.select('link[rel=stylesheet]'))
            blog = BeautifulSoup((release / language / 'blog.html').read_text(), 'html.parser')
            assert blog.select_one('#article-1 .blog-shop-link.link-ext')
            public_paths = {path for lang in catalog['languages']
                            for path in (f'/{lang}', f'/{lang}/',
                                         *[f'/{lang}/{page}{suffix}' for page in ('index', 'blog', 'shop')
                                           for suffix in ('', '/', '.html')])}
            for page in (main, blog, soup):
                versioned = 0
                for link in page.select('a[href]'):
                    url = urlsplit(link['href'])
                    if (url.path in public_paths and url.scheme in ('', 'http', 'https')
                            and url.hostname in (None, 'petramuckova.cz', 'www.petramuckova.cz')):
                        assert parse_qs(url.query).get('v') == ['vshop-smoke-test'], link['href']
                        versioned += 1
                assert versioned > 0
                for link in page.select('link[rel=canonical], link[rel=alternate]'):
                    assert not urlsplit(link['href']).query
        sitemap = ET.fromstring((release / 'sitemap.xml').read_text())
        locations = sitemap.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        assert len(locations) == 30
        assert len([loc for loc in locations if loc.text.endswith('/shop.html')]) == 10
        image_locations = sitemap.findall('.//{http://www.google.com/schemas/sitemap-image/1.1}loc')
        for product in catalog['products']:
            for image in product.get('images', []):
                assert any(loc.text.endswith(image['src']) for loc in image_locations)
        assert catalog['placeholderImage'] not in (release / 'sitemap.xml').read_text()
        assert 'vshop-smoke-test' in (release / '.htaccess').read_text()
        assert '{{RELEASE_' not in (release / '.htaccess').read_text()
    release_after = {str(p.relative_to(ROOT / 'release')): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in (ROOT / 'release').rglob('*') if p.is_file()}
    assert release_before == release_after, 'Existing release directory changed!'
    print('PASS: full isolated release, 30 pages, 10 shop routes, CDN assets, metadata; existing release unchanged.')


if __name__ == '__main__':
    main()
