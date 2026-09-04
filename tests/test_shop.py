import contextlib
import csv
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from build_shop import ROOT, build_shop, load_catalog, money


def css_rules(path):
    """Read flat declaration blocks for source-level form-style regression checks."""
    source = re.sub(r'/\*.*?\*/', '', path.read_text(), flags=re.S)
    for selector, body in re.findall(r'([^{}]+)\{([^{}]*)\}', source):
        declarations = dict(declaration.strip().split(':', 1)
                            for declaration in body.split(';') if ':' in declaration)
        yield selector.strip(), {key: value.strip() for key, value in declarations.items()}


class ShopBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()
        cls.photo_count = sum(len(product.get('images', [])) or 1 for product in cls.catalog['products'])
        cls.tmp = tempfile.TemporaryDirectory(prefix='muckova-shop-test-')
        cls.output = Path(cls.tmp.name)
        with contextlib.redirect_stdout(io.StringIO()):
            build_shop(output_root=cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def pages(self):
        for lang in self.catalog['languages']:
            yield lang, BeautifulSoup((self.output / lang / 'shop.html').read_text(), 'html.parser')

    def test_all_locales_have_complete_static_catalogs(self):
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                self.assertEqual(soup.html['lang'], lang)
                self.assertEqual(len(soup.select('.shop-product')), 16)
                self.assertEqual(len(soup.select('h1')), 1)
                self.assertNotIn('TAZ', soup.h1.text)
                self.assertTrue(soup.select_one('#catalog-title.shop-sr-only'))
                self.assertFalse(soup.select('#catalog > .shop-section-heading'))
                self.assertFalse(soup.select('.shop-intro, .shop-product-code'))

    def test_catalog_information_precedes_products_without_changing_copy(self):
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                self.assertEqual(len(soup.select('.shop-catalog-notes')), 1)
                notes = soup.select_one('#catalog > .shop-catalog-notes')
                self.assertEqual(len(notes.select('p')), 4)
                self.assertNotIn('//', notes.get_text())
                self.assertIsNotNone(soup.select_one('#catalog > .shop-catalog-notes + .shop-grid'))
                self.assertEqual(soup.select_one('#catalog .blog-card'), notes)
                copy = self.catalog['copy'][lang]
                self.assertEqual([paragraph.get_text() for paragraph in notes.select('p')],
                                 [copy['trade'], *copy['notes']])

    def test_titles_lead_the_product_card_and_controls_are_labeled(self):
        for lang, soup in self.pages():
            for product in soup.select('.shop-product'):
                with self.subTest(lang=lang, product=product['id']):
                    self.assertEqual(product.find(recursive=False).name, 'h3')
                    self.assertEqual(product['aria-labelledby'], product.h3['id'])
                    for button in product.select('.shop-quantity button'):
                        self.assertTrue(button.get('aria-label'))
                    for image in product.select('img'):
                        self.assertTrue(image.get('alt'))
                        self.assertTrue((ROOT / image['src'].lstrip('/')).is_file())

    def test_quantity_controls_allow_9999_and_share_the_runtime_limit(self):
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                fields = soup.select('.shop-product input[data-quantity]')
                self.assertEqual(len(fields), sum(p.get('kind') != 'wizard' for p in self.catalog['products']))
                for field in fields:
                    self.assertEqual(field['type'], 'number')
                    self.assertEqual(field['min'], '0')
                    self.assertEqual(field['max'], '9999')
                    self.assertEqual(field['step'], '1')
                    self.assertEqual(field['inputmode'], 'numeric')
        source = (ROOT / 'shop.js').read_text()
        self.assertIn('const MAX_QUANTITY = 9999;', source)
        self.assertIn('control.max = String(MAX_QUANTITY)', source)
        self.assertIn('value >= MAX_QUANTITY', source)
        self.assertIn('value > MAX_QUANTITY', source)
        self.assertIn('initBasketQuantitySelection(basketList);', source)

    def test_product_headings_match_main_team_name_red_underline(self):
        main_rules = dict(css_rules(ROOT / 'main.css'))
        shop_rules = dict(css_rules(ROOT / 'shop.css'))
        shared_heading = main_rules['.shadow-box h3, .shadow-box h4']
        product_heading = shop_rules['.shop-product-title']
        for prop in ('color', 'border-bottom', 'padding-bottom', 'display'):
            self.assertEqual(product_heading[prop], shared_heading[prop], prop)
        self.assertEqual(product_heading['font-size'], 'calc(var(--shop-product-font-size) * 1.8)')
        self.assertEqual(product_heading['text-align'], 'center')
        self.assertEqual(product_heading['justify-self'], 'center')
        self.assertEqual(product_heading['align-self'], 'center')
        self.assertEqual(product_heading['max-width'], '100%')
        self.assertNotIn('border', product_heading)
        self.assertNotIn('text-transform', product_heading)
        self.assertNotIn('.shop-product h3', shop_rules)
        self.assertEqual(main_rules['h1, h2, h3, h4, h5']['text-transform'], 'uppercase')
        for lang, soup in self.pages():
            main = BeautifulSoup((ROOT / lang / 'index.html').read_text(), 'html.parser')
            self.assertTrue(main.select_one('#team .shadow-box h3.team-name'))
            self.assertEqual(len(soup.select('.shop-product > h3.shop-product-title')),
                             len(self.catalog['products']))

    def test_image_column_is_separate_from_ordered_product_content(self):
        for lang, soup in self.pages():
            for product in self.catalog['products']:
                if product.get('kind') == 'wizard':
                    continue  # Configurator structure has its own assertions below.
                with self.subTest(lang=lang, product=product['id']):
                    card = soup.find(id=product['id'])
                    sections = card.find_all(recursive=False)
                    self.assertEqual(len(sections), 3)
                    title, photo, content = sections
                    self.assertIn('shop-product-title', title['class'])
                    self.assertIn('shop-photo', photo['class'])
                    self.assertIn('shop-product-content', content['class'])
                    self.assertFalse(photo.select('h3, .shop-description, .shop-prices, .shop-quantity, .shop-variant'))
                    description, prices, order = content.find_all(recursive=False)
                    self.assertIn('shop-product-body', description['class'])
                    self.assertIn('shop-prices', prices['class'])
                    self.assertIn('shop-product-order', order['class'])
                    self.assertTrue(description.select_one('.shop-description'))
                    self.assertFalse(description.select('.shop-prices, .shop-quantity, .shop-variant'))
                    self.assertEqual(prices.name, 'dl')
                    self.assertTrue(order.find('div', class_='shop-quantity', recursive=False))
                    quantity = order.select_one('[data-quantity]')
                    label = order.find('label', attrs={'for': quantity['id']})
                    self.assertIn('shop-quantity-label', label['class'])
                    self.assertNotIn('shop-sr-only', label['class'])
                    self.assertIn(product['translations'][lang]['name'], label.get_text())
                    self.assertEqual(len(order.select('[data-variant]')), 1 if product['variants'] else 0)

    def test_grid_aligns_photo_with_description_below_the_right_column_title(self):
        rules = list(css_rules(ROOT / 'shop.css'))
        desktop = next(props for selector, props in rules if selector == '.shop-product')
        self.assertEqual(desktop['display'], 'grid')
        self.assertEqual(desktop['grid-template-columns'], 'minmax(0, .9fr) minmax(0, 1.1fr)')
        self.assertEqual(desktop['grid-template-areas'], '". title" "photo content"')
        self.assertEqual(desktop['align-items'], 'start')
        self.assertEqual(desktop['gap'], '18px 24px')
        shared = dict(rules)
        self.assertEqual(shared['.shop-product-title']['grid-area'], 'title')
        self.assertEqual(shared['.shop-photo']['grid-area'], 'photo')
        self.assertEqual(shared['.shop-photo']['align-self'], 'start')
        self.assertEqual(shared['.shop-product-content']['grid-area'], 'content')
        self.assertEqual(shared['.shop-product-content']['flex-direction'], 'column')
        # Narrow cards stack in the same logical order as the source markup.
        mobile = shared['.shop-product']
        self.assertEqual(mobile['grid-template-columns'], 'minmax(0, 1fr)')
        self.assertEqual(mobile['grid-template-areas'], '"title" "photo" "content"')

    def test_product_sections_keep_spacing_without_separator_lines(self):
        rules = dict(css_rules(ROOT / 'shop.css'))
        self.assertEqual(rules['.shop-prices, .shop-product-order'], {'padding-top': '19px'})
        self.assertNotRegex((ROOT / 'shop.css').read_text(),
                            r'\.shop-(?:prices|product-order)::(?:before|after)')
        for selector in ('.shop-prices', '.shop-product-order'):
            self.assertNotIn('width', rules[selector])
            self.assertNotIn('border-top', rules[selector])

    def test_variants_reuse_main_form_dropdowns_and_keep_native_hooks(self):
        for lang, soup in self.pages():
            main = BeautifulSoup((ROOT / lang / 'index.html').read_text(), 'html.parser')
            styles = [link['href'] for link in soup.select('link[rel=stylesheet]')]
            scripts = [script['src'] for script in soup.select('script[src]')]
            choices_css = main.select_one('link[href*="choices.js@"]')['href']
            choices_js = main.select_one('script[src*="choices.js@"]')['src']
            self.assertLess(styles.index(choices_css), styles.index('/main.css'))
            self.assertLess(scripts.index(choices_js), next(i for i, src in enumerate(scripts) if src.startswith('/shop.js?')))
            self.assertTrue(soup.select_one('script[src*="choices.js@"]')['defer'] == '')
            for product in self.catalog['products']:
                card = soup.find(id=product['id'])
                select = card.select_one('.shop-variant.form-group > select.custom-select[data-variant]')
                self.assertEqual(select is not None, bool(product['variants']))
                if select:
                    label = card.find('label', attrs={'for': select['id']})
                    self.assertEqual(label['id'], 'label-' + select['id'])
                    self.assertEqual([option['value'] for option in select.select('option')],
                                     ['', *[variant['id'] for variant in product['variants']]])

    def test_text_fields_keep_main_page_styles_instead_of_shop_overrides(self):
        _, soup = next(self.pages())
        fields = soup.select('input[type="text"], input[type="email"], input[type="tel"], input[type="number"], textarea')
        shared_properties = {
            'font', 'font-family', 'font-size', 'font-weight', 'line-height',
            'background', 'background-color', 'color', 'height', 'padding', 'border-color',
        }
        for selector, declarations in css_rules(ROOT / 'shop.css'):
            overrides = shared_properties.intersection(declarations)
            if not overrides or '::' in selector:
                continue
            matched = soup.select(selector)
            for field in fields:
                # Product cards intentionally use a smaller type scale; all other
                # field properties and the final order form stay shared.
                field_overrides = overrides - {'font-size'} if field.find_parent(class_='shop-product') else overrides
                if field_overrides:
                    self.assertNotIn(field, matched, f'{selector} overrides shared field styles: {field_overrides}')

    def test_product_type_scale_is_14px_with_smaller_headings_and_readable_secondary_text(self):
        all_rules = list(css_rules(ROOT / 'shop.css'))
        rules = dict(all_rules)
        product = next(declarations for selector, declarations in all_rules if selector == '.shop-product')
        self.assertEqual(product['--shop-product-font-size'], '.875rem')
        self.assertEqual(product['--shop-product-small-font-size'], '.8125rem')
        self.assertEqual(product['--shop-product-caption-font-size'], '.75rem')
        self.assertEqual(product['font-size'], 'var(--shop-product-font-size)')
        for selector, size in {
            '.shop-description': 'var(--shop-product-font-size)',
            '.shop-prices': 'var(--shop-product-small-font-size)',
            '.shop-product-body > a': 'var(--shop-product-small-font-size)',
            '.shop-profile-label': 'var(--shop-product-caption-font-size)',
            '.shop-product .warning-msg': 'var(--shop-product-caption-font-size)',
            '.shop-product-title': 'calc(var(--shop-product-font-size) * 1.8)',
            '.shop-product .form-section-title': 'calc(var(--shop-product-font-size) * 1.1)',
            '.shop-product .btn-submit': 'calc(var(--shop-product-font-size) * 1.2)',
        }.items():
            self.assertEqual(rules[selector]['font-size'], size, selector)
        controls_selector = next(selector for selector in rules if selector.startswith('.shop-product label,'))
        self.assertEqual(rules[controls_selector], {'font-size': 'var(--shop-product-font-size)'})
        _, soup = next(self.pages())
        for card in soup.select('.shop-product'):
            for class_name in ('choices', 'choices__inner', 'choices__item'):
                card.append(soup.new_tag('div', attrs={'class': class_name}))
        controlled = soup.select(controls_selector)
        expected = soup.select('.shop-product label, .shop-product input:not([type=radio]), '
                               '.shop-product select, .shop-product .choices, .shop-product .choices__inner, '
                               '.shop-product .choices__item, .shop-product .shop-quantity button')
        self.assertTrue(expected)
        for node in expected:
            self.assertTrue(any(node is match for match in controlled))
        # Every rule referencing the scale is confined to product cards, including
        # newly added select overrides. Main-page and final-order styling is intact.
        for selector, declarations in all_rules:
            if '--shop-product-' not in str(declarations):
                continue
            for node in soup.select(selector):
                self.assertTrue('shop-product' in node.get('class', []) or node.find_parent(class_='shop-product'))
        self.assertEqual(rules['.shop-page']['font-size'], '1rem')
        self.assertEqual(rules['.shop-basket-item h3']['font-size'], '1rem')

    def test_dropdown_fallback_and_field_focus_match_main_form(self):
        main_rules = dict(css_rules(ROOT / 'main.css'))
        shop_rules = dict(css_rules(ROOT / 'shop.css'))
        shared = next(declarations for selector, declarations in main_rules.items()
                      if selector.startswith('input[type="text"]'))
        fallback = shop_rules['.shop-variant > select']
        for prop in ('height', 'padding', 'border', 'background', 'color', 'font-family', 'border-radius'):
            self.assertEqual(fallback[prop], shared[prop], prop)
        self.assertEqual(float(fallback['font-size'].removesuffix('rem')),
                         float(shared['font-size'].removesuffix('rem')))
        for prop in ('border-color', 'background', 'box-shadow'):
            normalize = lambda value: value.replace(' ', '').replace('0.', '.')
            self.assertEqual(normalize(shop_rules['.shop-variant > select:focus'][prop]),
                             normalize(main_rules['input:focus, textarea:focus'][prop]), prop)

        # The shared red border/glow replaces only field outlines, not button/link focus.
        focus_selector = next(selector for selector, declarations in shop_rules.items()
                              if ':is(input[type="text"]' in selector and ':focus-visible' in selector)
        self.assertEqual(shop_rules[focus_selector]['outline'], 'none !important')
        _, soup = next(self.pages())
        choices = soup.new_tag('div', attrs={'class': 'choices'})
        soup.select_one('.shop-variant').append(choices)
        fields = soup.select(focus_selector.replace(':focus-visible', ''))
        for field in soup.select('input[type="text"], input[type="email"], input[type="tel"], input[type="number"], textarea, select.custom-select, .choices'):
            self.assertIn(field, fields)
        self.assertFalse(any(field.name in ('button', 'a') or field.get('type') == 'radio' for field in fields))
        self.assertEqual(shop_rules['.shop-page :focus-visible']['outline'], '2px solid #fff !important')
        body_line_height = main_rules['body']['line-height']
        for selector in ('.shop-layout', '.shop-order', '.shop-order-form'):
            self.assertNotIn('line-height', shop_rules[selector])  # Inherit the main body's rhythm.
        self.assertEqual(shop_rules['.shop-variant']['line-height'], body_line_height)

    def test_photos_use_accessible_zoom_links_and_blog_lightbox_styles(self):
        for lang, soup in self.pages():
            text = json.loads(soup.select_one('#shop-config').string)['text']
            viewer = soup.select_one('dialog#shop-lightbox.lightbox-modal')
            self.assertIsNotNone(viewer)
            self.assertFalse(viewer.has_attr('open'))
            self.assertIsNotNone(viewer.select_one('.lightbox-img'))
            self.assertEqual(viewer.select_one('button')['aria-label'], text['closePhoto'])
            self.assertEqual(len(soup.select('.shop-photo > .shop-photo-link > .tech-frame img')), self.photo_count)
            for photo in soup.select('.shop-photo-link'):
                self.assertEqual(photo['href'], photo.img['src'])
                self.assertEqual(photo['aria-haspopup'], 'dialog')
                self.assertTrue(photo['aria-label'].startswith(text['enlargePhoto']))

    def test_photos_are_horizontally_centered_and_reuse_equipment_faded_edges(self):
        rules = dict(css_rules(ROOT / 'shop.css'))
        self.assertEqual(rules['.shop-photo']['align-self'], 'start')
        self.assertEqual(rules['.shop-photo-link']['cursor'], 'zoom-in')
        self.assertEqual(rules['.shop-photo-link']['width'], 'fit-content')
        self.assertEqual(rules['.shop-photo-link']['max-width'], '100%')
        self.assertEqual(rules['.shop-photo-link']['margin-inline'], 'auto')
        self.assertNotIn('overflow', rules['.shop-photo-link'])
        self.assertEqual(rules['.shop-photo-link:hover .tech-frame::after']['opacity'], '0')
        self.assertEqual(rules['.shop-photo-link:not(.shop-photo-pointer-focus):focus-visible .tech-frame::after']['opacity'], '0')
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                main = BeautifulSoup((ROOT / lang / 'index.html').read_text(), 'html.parser')
                self.assertTrue(main.select_one('#equipment .tech-frame img'))
                self.assertFalse(soup.select('.shop-photo.blog-img-frame, .shop-photo.blog-figure'))
                for link in soup.select('.shop-photo > a.shop-photo-link'):
                    frame = link.select_one(':scope > .tech-frame')
                    self.assertIsNotNone(frame.img)
                    self.assertNotIn('tech-frame', link['class'])  # Keep focus outside the clipped frame.
                    self.assertIsNone(frame.find('figcaption'))
                self.assertFalse(soup.select('#shop-lightbox .tech-frame'))

    def test_pointer_restored_photo_focus_keeps_faded_edges(self):
        main_rules = dict(css_rules(ROOT / 'main.css'))
        shop_rules = dict(css_rules(ROOT / 'shop.css'))
        self.assertEqual(main_rules['.tech-frame::after']['opacity'], '1')
        focus_rule = '.shop-photo-link:not(.shop-photo-pointer-focus):focus-visible .tech-frame::after'
        self.assertEqual(shop_rules[focus_rule]['opacity'], '0')
        self.assertNotIn('.shop-photo-link:focus-visible .tech-frame::after', shop_rules)
        # Model a focused link in static markup: the pointer flag must exclude it
        # from the focus-only fade rule, even if the browser reports :focus-visible.
        selector = focus_rule.replace(':focus-visible', '').removesuffix('::after')
        _, soup = next(self.pages())
        for link in soup.select('.shop-photo-link'):
            frame = link.select_one('.tech-frame')
            link['class'].append('shop-photo-pointer-focus')
            self.assertFalse(any(node is frame for node in soup.select(selector)))
            # Tab clears the pointer flag; genuine keyboard focus can still reveal it.
            link['class'].remove('shop-photo-pointer-focus')
            self.assertTrue(any(node is frame for node in soup.select(selector)))
        self.assertEqual(shop_rules['.shop-photo-link:hover .tech-frame::after']['opacity'], '0')

    def test_product_photos_keep_natural_proportions_without_letterboxing_or_cropping(self):
        rules = dict(css_rules(ROOT / 'shop.css'))
        self.assertEqual(rules['.shop-photo .tech-frame'], {'display': 'block'})
        image = rules['.shop-photo img']
        self.assertEqual(image['display'], 'block')
        self.assertEqual(image['width'], 'auto')
        self.assertEqual(image['max-width'], '100%')
        self.assertEqual(image['height'], 'auto')
        for prop in ('position', 'inset', 'object-fit', 'aspect-ratio'):
            self.assertNotIn(prop, image)
        self.assertNotIn('.shop-photo-placeholder img', rules)
        _, soup = next(self.pages())
        photos = soup.select('.shop-photo img')
        frames = soup.select('.shop-photo .tech-frame')
        # Reject other shop rules that reintroduce fixed frames or image crops.
        for selector, declarations in css_rules(ROOT / 'shop.css'):
            if '::' in selector or not {'height', 'aspect-ratio', 'object-fit'}.intersection(declarations):
                continue
            for node in soup.select(selector):
                if node in photos or node in frames:
                    self.assertNotIn('aspect-ratio', declarations, selector)
                    self.assertNotIn('object-fit', declarations, selector)
                    if 'height' in declarations:
                        self.assertEqual(declarations['height'], 'auto', selector)

    def test_generic_placeholder_is_used_only_where_a_photo_is_missing(self):
        for lang, soup in self.pages():
            text = json.loads(soup.select_one('#shop-config').string)['text']
            self.assertEqual(len(soup.select('.shop-product img')), self.photo_count)
            self.assertEqual(len(soup.select('img[data-placeholder]')), 14)
            self.assertFalse(soup.select('.shop-photo figcaption'))
            for product in self.catalog['products']:
                photo = soup.find(id=product['id']).find('img')
                self.assertEqual(photo['src'], product['image'] or self.catalog['placeholderImage'])
                self.assertEqual(photo.has_attr('data-placeholder'), not bool(product['image']))
                if photo.has_attr('data-placeholder'):
                    self.assertEqual(photo['alt'], text['noPhoto'])
                else:
                    expected_alt = product['images'][0]['alt'][lang] if product.get('images') else product['translations'][lang]['name']
                    self.assertEqual(photo['alt'], expected_alt)
            self.assertFalse(soup.select('[itemprop=availability]'))

    def test_canonical_and_hreflang_are_clean(self):
        for lang, soup in self.pages():
            self.assertEqual(soup.select_one('link[rel=canonical]')['href'], f'https://www.petramuckova.cz/{lang}/shop')
            self.assertEqual(len(soup.select('link[rel=alternate]')), 11)
            self.assertTrue(all('?' not in link['href'] for link in soup.select('link[rel=alternate]')))

    def test_browser_config_matches_visible_products_and_prices(self):
        for lang, soup in self.pages():
            config = json.loads(soup.select_one('#shop-config').string)
            self.assertEqual(config['locale'], lang)
            self.assertEqual(soup.select_one('.shop-totals > span').get_text(), config['text']['subtotal'])
            for product in config['products']:
                self.assertEqual(soup.find(id='name-' + product['id']).text, product['name'])
                source = next(p for p in self.catalog['products'] if p['id'] == product['id'])
                self.assertEqual(product['price'], source['price'])
            for key in ('email', 'fullName', 'street', 'city', 'postcode', 'country'):
                field = soup.select_one(f'[name="{key}"]')
                self.assertTrue(field.has_attr('required'))
                self.assertTrue(soup.find('label', attrs={'for': field['id']}))
            self.assertEqual(soup.select_one('[name=email]')['type'], 'email')
            self.assertEqual(soup.select_one('[name=deliveryMethod]')['value'], 'postal')

    def test_unique_ids_and_no_template_tokens(self):
        for _, soup in self.pages():
            ids = [node['id'] for node in soup.select('[id]')]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertNotRegex(str(soup), r'\$(?:title|products|config|canonical)\b')

    def test_prices_are_visible_and_form_reuses_main_site_components(self):
        for lang, soup in self.pages():
            self.assertFalse(soup.select('.shop-product details'))
            self.assertNotIn('pricingNote', json.loads(soup.select_one('#shop-config').string)['text'])
            for product in self.catalog['products']:
                card = soup.find(id=product['id'])
                prices = card.select('.shop-price-row')
                self.assertEqual(len(prices), 0 if product.get('kind') == 'wizard' else (3 if product['dealerPrice'] else 1))
                self.assertIsNone(card.select_one('.shop-price-note'))
            self.assertTrue(soup.select_one('#shop-order-form.terminal-form'))
            self.assertTrue(soup.select_one('#shop-order-form .form-row .form-group'))
            self.assertTrue(soup.select_one('#order-prepare.btn-submit'))
            self.assertFalse(soup.select_one('#basket .shop-local-note'))

    def test_order_has_main_contact_intro_and_one_form_panel(self):
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                order = soup.select_one('#order.section.shop-order')
                self.assertIsNotNone(order)
                self.assertNotIn('blog-card', order['class'])
                intro = order.select_one(':scope > .contact-intro')
                self.assertEqual(intro.h2['id'], order['aria-labelledby'])
                self.assertTrue(intro.select_one('p.contact-sub-1'))
                self.assertTrue(order.select_one(':scope > .contact-intro + form.terminal-form'))
                self.assertEqual(len(order.select('.terminal-form')), 1)
                self.assertFalse(order.select('.blog-card, .shop-order-heading'))
                self.assertIsNone(intro.find_parent('form'))
                self.assertFalse(order.select('form .contact-intro'))

    def test_order_intro_retains_shared_heading_and_paragraph_styles(self):
        _, soup = next(self.pages())
        intro_nodes = soup.select('#order > .contact-intro, #order > .contact-intro > h2, #order > .contact-intro > p')
        shared_properties = {'margin', 'margin-top', 'margin-bottom', 'margin-block',
                             'font-size', 'line-height', 'text-align', 'color'}
        for selector, declarations in css_rules(ROOT / 'shop.css'):
            if not shared_properties.intersection(declarations) or '::' in selector:
                continue
            matches = soup.select(selector)
            for node in intro_nodes:
                self.assertNotIn(node, matches, f'{selector} overrides the shared contact intro')

    def test_order_copy_and_required_field_note_match_main_form(self):
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                main = BeautifulSoup((ROOT / lang / 'index.html').read_text(), 'html.parser')
                text = json.loads(soup.select_one('#shop-config').string)['text']
                self.assertEqual(soup.select_one('#order-title').get_text(), text['checkout'])
                self.assertEqual(soup.select_one('#order .contact-sub-1').get_text(), text['confirmation'])
                self.assertEqual(soup.select_one('#shop-order-form .mandatory-note').get_text(),
                                 main.select_one('#inquiryForm .mandatory-note').get_text())
                self.assertEqual(text['orderSubject'], 'Mücková / Mück — ' + text['checkout'])
                self.assertNotIn('optional', text)
                self.assertFalse(soup.select('#shop-order-form label small'))
                for field_id in ('order-company', 'order-phone', 'order-notes'):
                    field = soup.find(id=field_id)
                    self.assertFalse(field.has_attr('required'))
                    label = (soup.find(id=field['aria-labelledby']) if field.has_attr('aria-labelledby')
                             else soup.find('label', attrs={'for': field_id}))
                    self.assertNotIn('*', label.get_text())
                if lang == 'cs':
                    self.assertEqual(text['checkout'], 'Objednávka')
                    self.assertEqual(text['confirmation'],
                                     'Jde o nezávaznou objednávku, nikoliv o platbu nebo uzavření smlouvy na dálku.')
                    self.assertNotIn('Poptávka objednávky', soup.get_text())

    def test_order_contact_fields_and_labels_are_updated_in_every_locale(self):
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                text = json.loads(soup.select_one('#shop-config').string)['text']
                form = soup.select_one('#shop-order-form')
                for field_id, name, field_type, autocomplete, limit in (
                    ('order-company', 'company', 'text', 'shipping organization', '160'),
                    ('order-phone', 'phone', 'tel', 'tel', '60'),
                ):
                    field = form.find(id=field_id)
                    self.assertEqual(field['name'], name)
                    self.assertEqual(field['type'], field_type)
                    self.assertEqual(field['autocomplete'], autocomplete)
                    self.assertEqual(field['maxlength'], limit)
                    self.assertFalse(field.has_attr('required'))
                    self.assertEqual(form.find('label', attrs={'for': field_id}).get_text(), text[name])
                for name in ('fullName', 'email', 'street', 'city', 'postcode', 'country', 'notes'):
                    field = form.select_one(f'[name="{name}"]')
                    required = name != 'notes'
                    self.assertEqual(field.has_attr('required'), required)
                    label = (form.find(id=field['aria-labelledby']) if field.has_attr('aria-labelledby')
                             else form.find('label', attrs={'for': field['id']}))
                    self.assertEqual(label.get_text(),
                                     text[name] + (' *' if required else ''))
                groups = form.select(':scope > .form-row > .form-group')
                self.assertEqual([[field['name'] for field in group.select('input')] for group in groups],
                                 [['fullName', 'company'], ['email', 'phone']])
                self.assertFalse(form.select('#order-extra, [name="addressExtra"], [autocomplete="shipping address-line2"]'))
                self.assertNotIn('addressExtra', text)
                if lang == 'cs':
                    for name, label in {'fullName': 'Jméno a příjmení', 'company': 'Firma',
                                        'phone': 'Telefon', 'street': 'Ulice, č.p.',
                                        'city': 'Město', 'notes': 'Poznámka'}.items():
                        self.assertEqual(text[name], label)

    def test_delivery_and_notes_share_the_main_form_section_heading_style(self):
        shop_rules = dict(css_rules(ROOT / 'shop.css'))
        self.assertNotIn('.shop-order-form .form-section-title', shop_rules)
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                text = json.loads(soup.select_one('#shop-config').string)['text']
                main = BeautifulSoup((ROOT / lang / 'index.html').read_text(), 'html.parser')
                main_heading = main.select_one('#inquiryForm h4.form-section-title')
                headings = soup.select('#shop-order-form h4.form-section-title')
                self.assertEqual(len(headings), 3)
                self.assertEqual(headings[0].get_text(), main_heading.get_text())
                for heading in headings:
                    self.assertEqual(heading.name, main_heading.name)
                    self.assertEqual(heading['class'], main_heading['class'])
                fieldset = soup.select_one('#shop-order-form > fieldset')
                self.assertEqual(soup.find(id=fieldset['aria-labelledby']).get_text(), text['delivery'])
                notes = soup.select_one('#order-notes')
                self.assertEqual(soup.find(id=notes['aria-labelledby']).get_text(), text['notes'])
                self.assertEqual(notes['rows'], main.select_one('textarea[name="message"]')['rows'])
                self.assertTrue(fieldset.select_one('[name="deliveryMethod"]'))
                self.assertTrue(fieldset.select_one('[name="street"][required]'))

    def test_form_typography_spacing_and_warnings_have_no_shop_overrides(self):
        _, soup = next(self.pages())
        shared_nodes = soup.select('#shop-order-form, #shop-order-form .form-row, #shop-order-form .form-group, '
                                   '#shop-order-form h4, #shop-order-form label, #shop-order-form .warning-msg, '
                                   '#shop-order-form .mandatory-note, #shop-order-form .disclaimer, #order-prepare')
        shared_properties = {'font', 'font-family', 'font-size', 'font-weight', 'letter-spacing', 'line-height',
                             'color', 'background', 'background-color', 'margin', 'margin-top', 'margin-bottom',
                             'padding', 'text-transform', 'border', 'box-shadow'}
        for selector, declarations in css_rules(ROOT / 'shop.css'):
            overrides = shared_properties.intersection(declarations)
            if selector == '.shop-delivery-method':
                overrides.discard('margin-bottom')  # Space after the postal radio option.
            if not overrides or '::' in selector:
                continue
            matched = soup.select(selector)
            for node in shared_nodes:
                self.assertFalse(any(node is match for match in matched),
                                 f'{selector} overrides shared form styles: {overrides}')

    def test_both_forms_load_shared_validation_and_localized_inline_messages(self):
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                main = BeautifulSoup((ROOT / lang / 'index.html').read_text(), 'html.parser')
                for page, script, form_id in ((main, 'index.js', 'inquiryForm'), (soup, 'shop.js', 'shop-order-form')):
                    scripts = [Path(node['src'].split('?')[0]).name for node in page.select('script[src]')]
                    self.assertLess(scripts.index('form.js'), scripts.index(script))
                    form = page.find(id=form_id)
                    self.assertTrue(form.has_attr('novalidate'))
                    for field in form.select('.validate-me'):
                        self.assertIn('warning-msg', field.find_next_sibling()['class'])
                        self.assertTrue(field.find_next_sibling().get_text(strip=True))
                    self.assertTrue(all('validate-me' in field.get('class', []) for field in form.select('[required]')))
                form = soup.select_one('#shop-order-form')
                self.assertEqual(len(form.select('.validate-me')), 7)
                for name in ('email', 'phone'):
                    self.assertEqual(form.select_one(f'[name="{name}"] + .warning-msg').get_text(),
                                     main.select_one(f'#inquiryForm [name="{name}"] + .warning-msg').get_text())
                for field in form.select('input[type="text"][required]'):
                    self.assertEqual(field.find_next_sibling().get_text(),
                                     main.select_one('[name="fullname"] + .warning-msg').get_text())
        for filename in ('index.js', 'shop.js'):
            source = (ROOT / filename).read_text()
            self.assertIn('SiteForm.initValidation(form)', source)
            self.assertIn('validation.validate()', source)
            self.assertNotIn('form.reportValidity()', source)
            self.assertNotIn('function validateInput(', source)

    def test_basket_has_no_clear_all_action(self):
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                self.assertIsNone(soup.select_one('#basket-clear'))
                self.assertNotIn('clear', json.loads(soup.select_one('#shop-config').string)['text'])
        self.assertNotIn('basket-clear', (ROOT / 'shop.js').read_text())

    def test_sidebar_heading_says_your_order_in_every_language(self):
        headings = {
            'cs': 'Vaše objednávka', 'en': 'Your order', 'de': 'Ihre Bestellung',
            'fr': 'Votre commande', 'it': 'Il tuo ordine', 'es': 'Tu pedido',
            'pl': 'Twoje zamówienie', 'ru': 'Ваш заказ', 'ja': 'ご注文内容', 'zh': '您的订单',
        }
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                title = soup.select_one('#basket-title.toc-title')
                self.assertEqual(title.get_text(), headings[lang])
                self.assertEqual(soup.select_one('.shop-sidebar')['aria-labelledby'], title['id'])
                self.assertEqual(json.loads(soup.select_one('#shop-config').string)['text']['basket'], headings[lang])

    def test_only_basket_items_scroll_in_the_floating_panel(self):
        rules = list(css_rules(ROOT / 'shop.css'))
        panel = next(props for selector, props in rules if selector == '.shop-basket')
        items = next(props for selector, props in rules if selector == '.shop-basket-items')
        fixed = dict(rules)['.shop-basket > :not(.shop-basket-items)']
        self.assertEqual(panel['display'], 'flex')
        self.assertEqual(panel['flex-direction'], 'column')
        self.assertEqual(panel['overflow'], 'hidden')
        self.assertEqual(panel['max-height'], 'calc(100dvh - var(--navbar-height) - 60px)')
        self.assertNotIn('overflow-y', panel)
        self.assertEqual(fixed['flex-shrink'], '0')
        self.assertEqual(items['flex'], '0 1 auto')
        self.assertEqual(items['min-height'], '0')
        self.assertEqual(items['overflow-y'], 'auto')
        self.assertEqual(items['overscroll-behavior'], 'contain')
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                basket = soup.select_one('#basket')
                item_list = basket.select_one(':scope > #basket-items.shop-basket-items')
                self.assertIsNotNone(item_list)
                stationary = soup.select('.shop-basket > :not(.shop-basket-items)')
                self.assertNotIn(item_list, stationary)
                for selector in ('.shop-section-heading', '#basket-empty', '.shop-totals',
                                 '#basket-quote-notice', 'p.shop-muted:not([id])', 'a.shop-button'):
                    node = basket.select_one(selector)
                    self.assertIn(node, stationary, selector)
                    self.assertNotIn(item_list, node.parents)

    def test_sticky_basket_is_bounded_by_the_content_before_the_footer(self):
        rules = list(css_rules(ROOT / 'shop.css'))
        panel = next(props for selector, props in rules if selector == '.shop-basket')
        sidebar = next(props for selector, props in rules if selector == '.shop-sidebar')
        blog_rules = dict(css_rules(ROOT / 'blog.css'))
        self.assertEqual(panel['position'], 'sticky')
        self.assertEqual(sidebar['grid-column'], '2')
        self.assertEqual(sidebar['grid-row'], '1 / 3')
        self.assertEqual(sidebar['align-self'], 'stretch')
        self.assertEqual(sidebar['padding-top'], blog_rules['.toc-wrapper']['top'])
        # The shop override must not change the blog's own table of contents.
        self.assertEqual(blog_rules['.toc-wrapper']['position'], 'fixed')
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                layout = soup.select_one('main.blog-wrapper > .container > .shop-layout')
                rail = layout.select_one(':scope > .shop-sidebar')
                self.assertTrue(rail.select_one(':scope > #basket.toc-wrapper.shop-basket'))
                self.assertTrue(layout.select_one(':scope > #catalog'))
                self.assertTrue(layout.select_one(':scope > #order'))
                self.assertIsNone(layout.find('footer'))
                self.assertIs(soup.main.find_next_sibling('footer'), soup.footer)
        # No intermediate scroll container may capture the sticky positioning.
        ancestors = [rail, *rail.parents]
        for path in ('main.css', 'blog.css', 'shop.css'):
            for selector, declarations in css_rules(ROOT / path):
                overflow = {prop: value for prop, value in declarations.items()
                            if prop in ('overflow', 'overflow-x', 'overflow-y')}
                if not overflow or '::' in selector:
                    continue
                matches = soup.select(selector)
                if any(any(node is ancestor for node in matches) for ancestor in ancestors):
                    self.assertTrue(all(value in ('visible', 'clip') for value in overflow.values()),
                                    f'{path}: {selector} traps the sticky basket')

    def test_inline_mobile_basket_uses_page_scrolling(self):
        rules = dict(css_rules(ROOT / 'shop.css'))
        # The last matching rules are the existing mobile breakpoint overrides.
        panel = rules['.shop-basket']
        self.assertEqual(panel['position'], 'static')
        self.assertEqual(panel['display'], 'block')
        self.assertEqual(panel['max-height'], 'none')
        self.assertEqual(panel['overflow'], 'visible')
        self.assertEqual(rules['.shop-sidebar']['padding-top'], '0')
        self.assertEqual(rules['.shop-basket-items']['overflow'], 'visible')
        self.assertEqual(rules['.shop-basket-items']['overscroll-behavior'], 'auto')

    def test_basket_rerender_preserves_the_item_list_scroll_position(self):
        source = (ROOT / 'shop.js').read_text()
        render = source.split('function render() {', 1)[1].split('function update(', 1)[0]
        capture = render.index('const basketScrollTop = basketList.scrollTop;')
        clear = render.index('basketList.replaceChildren();')
        populate = render.index('basketList.append(row);')
        restore = render.index('basketList.scrollTop = basketScrollTop;')
        focus = render.index('if (focusKey)')
        self.assertLess(capture, clear)
        self.assertLess(clear, populate)
        self.assertLess(populate, restore)
        self.assertLess(restore, focus)
        self.assertIn('focus({ preventScroll: true })', render)

    def test_footer_has_updated_copyright_without_version_badge_on_any_page(self):
        for lang, shop in self.pages():
            pages = [('shop', shop)]
            pages.extend((page, BeautifulSoup((ROOT / lang / f'{page}.html').read_text(), 'html.parser'))
                         for page in ('index', 'blog'))
            for name, soup in pages:
                with self.subTest(lang=lang, page=name):
                    self.assertIsNotNone(soup.footer)
                    self.assertEqual(soup.footer.select_one('.c-year').get_text(), '© 2026')
                    self.assertFalse(soup.footer.select('.version'))
                    self.assertNotIn('V.2.0', soup.footer.get_text())
                    self.assertTrue(soup.footer.select_one('.copyright-bar .barcode'))

    def test_navigation_and_original_article_anchors_remain(self):
        for lang in self.catalog['languages']:
            for page in ('index', 'blog'):
                soup = BeautifulSoup((ROOT / lang / f'{page}.html').read_text(), 'html.parser')
                self.assertTrue(soup.select(f'a[href="/{lang}/shop"]'))
                if page == 'blog':
                    self.assertTrue(soup.select_one('#post-1-title'))
                    link = soup.select_one('#article-1 .blog-shop-link.link-ext')
                    self.assertIsNotNone(link)
                    self.assertFalse(link.select('span'))  # The shared link style supplies its arrow.
                    self.assertFalse(soup.select_one('#article-1 table'))
                    self.assertEqual(len(soup.select('.blog-card')), 8)

    def test_shop_reuses_blog_header_footer_and_language_navigation(self):
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                blog = BeautifulSoup((ROOT / lang / 'blog.html').read_text(), 'html.parser')
                nav_items = lambda page: [(a['href'], a.get_text()) for a in page.select('#navLinks > li > a')]
                self.assertEqual(nav_items(soup), nav_items(blog))
                self.assertEqual(soup.select_one('#navLinks > li > a.active-link')['href'], f'/{lang}/shop')
                self.assertFalse(soup.select('.shop-header, .shop-navigation, .shop-basket-link, .navbar [data-basket-count]'))
                self.assertEqual(soup.footer.get_text(' ', strip=True), blog.footer.get_text(' ', strip=True))
                for selector in ('.lang-menu a', '.mobile-langchooser-list a'):
                    self.assertEqual([a['href'] for a in soup.select(selector)],
                                     [f'/{code}/shop' for code in self.catalog['languages']])
                for link in soup.select('.mobile-menu-list a'):
                    self.assertFalse(link['href'].startswith('#post-'))
                for trigger in soup.select('button[aria-controls]'):
                    self.assertEqual(trigger['aria-expanded'], 'false')
                    self.assertTrue(soup.find(id=trigger['aria-controls']).has_attr('hidden'))

    def test_shop_reuses_blog_background_panels_and_sidebar(self):
        for _, soup in self.pages():
            self.assertIn('bg-loaded', soup.body['class'])
            self.assertTrue(soup.select_one('.hero-visual-mobile.loaded'))
            styles = [link['href'].split('?')[0] for link in soup.select('link[rel=stylesheet]')]
            self.assertEqual(styles[-3:], ['/main.css', '/blog.css', '/shop.css'])
            self.assertTrue(soup.select_one('.blog-wrapper > .container > .blog-layout.shop-layout'))
            self.assertTrue(soup.select_one('#catalog.blog-content'))
            self.assertTrue(soup.select_one('.blog-sidebar > #basket.toc-wrapper'))
            self.assertTrue(soup.select_one('#basket-title.toc-title'))
            self.assertFalse(soup.select_one('.shop-sidebar.view-desktop'))  # Basket stays available on mobile.
            self.assertEqual([node.get('id') or 'basket-sidebar' for node in soup.select_one('.shop-layout').find_all(recursive=False)],
                             ['catalog', 'basket-sidebar', 'order'])
            self.assertEqual(len(soup.select('.shop-product.blog-card')), len(self.catalog['products']))
            self.assertEqual(len(soup.select('.shop-photo .tech-frame')), self.photo_count)
            self.assertTrue(soup.select_one('#order.section'))

    def test_rebuild_is_deterministic(self):
        original = {p: p.read_bytes() for p in self.output.glob('*/shop.html')}
        with contextlib.redirect_stdout(io.StringIO()):
            build_shop(output_root=self.output)
        self.assertEqual(original, {p: p.read_bytes() for p in original})

    def test_camshaft_wizard_replaces_two_old_cards_with_six_description_paragraphs(self):
        wizard = self.catalog['products'][0]
        self.assertEqual(wizard['id'], 'skoda-ohv-camshaft')
        self.assertEqual(wizard['translations']['cs']['name'], 'Vačková hřídel Škoda OHV')
        for lang, soup in self.pages():
            card = soup.select_one('.shop-wizard-product')
            self.assertEqual(card['id'], wizard['id'])
            self.assertFalse(soup.select('#camshaft-regrind, #camshaft-new'))
            sections = card.find_all(recursive=False)
            self.assertEqual([node.name for node in sections], ['h3', 'figure', 'div', 'form'])
            self.assertEqual([node.get_text() for node in card.select('.shop-description')],
                             wizard['translations'][lang]['description'].split('\n\n'))
            self.assertEqual(len(card.select('.shop-description')), 6)
            self.assertFalse(card.select('[data-quantity], [data-change], .shop-prices'))
            self.assertFalse(card.select('form form, form.terminal-form'))
            self.assertTrue(card.select_one('form[data-wizard][novalidate] > button.btn-submit[type=submit]'))

    def test_skoda_ohv_gallery_stacks_all_four_supplied_photos_with_individual_zoom(self):
        product = self.catalog['products'][0]
        images = product['images']
        expected_paths = [f'/assets/desktop/skoda-ohv-{index}.jpeg' for index in range(1, 5)]
        self.assertEqual([image['src'] for image in images], expected_paths)
        self.assertEqual(product['image'], expected_paths[0])
        self.assertEqual([(image['width'], image['height']) for image in images],
                         [(4000, 2252), (4000, 2252), (2252, 4000), (2252, 4000)])
        for path in expected_paths:
            data = (ROOT / path.lstrip('/')).read_bytes()
            self.assertTrue(data.startswith(b'\xff\xd8'))
            self.assertTrue(data.endswith(b'\xff\xd9'))
        for lang, soup in self.pages():
            card = soup.find(id=product['id'])
            gallery = card.select_one(':scope > figure.shop-photo.shop-photo-gallery')
            self.assertIsNotNone(gallery)
            self.assertEqual(len(soup.select('.shop-photo-gallery')), 1)
            links = gallery.select(':scope > a.shop-photo-link')
            self.assertEqual(len(links), 4)
            self.assertEqual([link['href'] for link in links], expected_paths)
            self.assertFalse(gallery.select('figcaption, .shop-description, form'))
            for index, (link, image) in enumerate(zip(links, images)):
                photo = link.select_one(':scope > .tech-frame > img')
                self.assertEqual(photo['src'], image['src'])
                self.assertEqual(photo['alt'], image['alt'][lang])
                self.assertIn(photo['alt'], link['aria-label'])
                self.assertEqual(link['aria-haspopup'], 'dialog')
                self.assertEqual((int(photo['width']), int(photo['height'])), (image['width'], image['height']))
                self.assertEqual(photo['loading'], 'eager' if index == 0 else 'lazy')
                self.assertEqual(photo['decoding'], 'async')
                self.assertFalse(photo.has_attr('data-placeholder'))
        rules = dict(css_rules(ROOT / 'shop.css'))
        self.assertEqual(rules['.shop-photo-gallery'], {
            'display': 'grid', 'grid-template-columns': 'minmax(0, 1fr)', 'gap': '18px',
        })

    def test_gallery_rejects_missing_images_dimensions_and_translations(self):
        for mutate in (
            lambda p: p.update(images=[]),
            lambda p: p.update(images=None),
            lambda p: p.update(images=['not-an-image-record']),
            lambda p: p['images'][1].update(src='/assets/desktop/missing-gallery-image.jpeg'),
            lambda p: p['images'][1].update(src='/assets/desktop/../desktop/skoda-ohv-2.jpeg'),
            lambda p: p['images'][1].update(width=0),
            lambda p: p['images'][1].update(height=True),
            lambda p: p['images'][1]['alt'].pop('en'),
            lambda p: p['images'][1]['alt'].update(cs=' '),
            lambda p: p.update(image=p['images'][1]['src']),
        ):
            invalid = json.loads(json.dumps(self.catalog))
            mutate(invalid['products'][0])
            with patch('build_shop.json.loads', return_value=invalid), self.assertRaises(ValueError):
                load_catalog()

    def test_wizard_profiles_match_supplied_csv_specs_descriptions_and_prices(self):
        wizard = self.catalog['products'][0]['wizard']
        with (ROOT / wizard['source']).open(newline='') as source:
            rows = list(csv.DictReader(source, delimiter=';'))
        self.assertEqual(len(rows), 6)
        for row, profile in zip(rows, wizard['profiles']):
            self.assertEqual(profile['duration'], row['duration'])
            self.assertEqual(profile['lift'], row['lift'])
            self.assertEqual(profile['price'], int(row['price'].replace(' Kč', '').replace(' ', '')))
            self.assertEqual(profile['translations']['cs'], row['description'])
            self.assertEqual(profile['manufacture'], 'new' if row['manufacture'] == 'výroba' else 'regrind')
        for lang, soup in self.pages():
            config = json.loads(soup.select_one('#shop-config').string)
            options = soup.select('.shop-profile-option')
            self.assertEqual(len(options), 6)
            radios = soup.select('input[type=radio][name=profile]')
            self.assertEqual(len(radios), 6)
            self.assertEqual(len({radio['name'] for radio in radios}), 1)
            for option, profile, client in zip(options, wizard['profiles'], config['products'][0]['wizard']['profiles']):
                self.assertEqual(option.input['value'], profile['id'])
                self.assertTrue(option.input.has_attr('required'))
                self.assertFalse(option.input.has_attr('checked'))
                self.assertTrue(soup.find(id=option.input['data-warning-id']))
                for value in (profile['duration'], profile['lift'], money(profile['price'], lang), profile['translations'][lang]):
                    self.assertIn(value, option.get_text())
                self.assertEqual(client['price'], profile['price'])
                self.assertEqual(client['description'], profile['translations'][lang])
                self.assertNotIn('translations', client)

    def test_wizard_table_keeps_operation_and_description_in_first_column_with_rowspanned_specs(self):
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                table = soup.select_one('form[data-wizard] > fieldset > table.shop-profile-table')
                self.assertIsNotNone(table)
                text = json.loads(soup.select_one('#shop-config').string)['text']
                self.assertEqual(table['aria-label'], text['configure'])
                headings = table.select('thead > tr > th[scope=col]')
                self.assertEqual(len(headings), 4)
                self.assertEqual([cell.get_text() for cell in headings],
                                 [text[key] for key in ('profileHeading', 'camDuration', 'camLift', 'price')])
                self.assertIn('shop-profile-price', headings[-1]['class'])
                self.assertEqual([col['class'] for col in table.select('colgroup > col')],
                                 [['shop-profile-operation-column'], ['shop-profile-spec-column'],
                                  ['shop-profile-spec-column'], ['shop-profile-price-column']])
                options = table.select(':scope > tbody.shop-profile-option')
                self.assertEqual(len(options), 6)
                accessible_names = []
                for option, profile in zip(options, self.catalog['products'][0]['wizard']['profiles']):
                    rows = option.find_all('tr', recursive=False)
                    self.assertEqual(len(rows), 2)
                    cells = rows[0].find_all('td', recursive=False)
                    self.assertEqual(len(cells), 4)
                    radio = cells[0].select_one('input[type=radio][name=profile]')
                    self.assertIsNotNone(radio)
                    self.assertEqual(radio['value'], profile['id'])
                    self.assertEqual(cells[0].select_one('.shop-profile-method').get_text(),
                                     text['manufactureNew' if profile['manufacture'] == 'new' else 'manufactureRegrind'])
                    self.assertFalse(cells[0].has_attr('rowspan'))
                    self.assertEqual([cell['rowspan'] for cell in cells[1:]], ['2', '2', '2'])
                    self.assertEqual([cell.get_text() for cell in cells[1:]],
                                     [profile['duration'], profile['lift'], money(profile['price'], lang)])
                    self.assertIn('shop-profile-price', cells[-1]['class'])
                    self.assertTrue(all('shop-profile-price' not in cell.get('class', []) for cell in cells[:-1]))
                    description_cells = rows[1].find_all('td', recursive=False)
                    self.assertEqual(len(description_cells), 1)
                    self.assertFalse(description_cells[0].has_attr('colspan'))
                    self.assertEqual(description_cells[0].get_text(), profile['translations'][lang])
                    # Native labels keep every value and the full description clickable.
                    labels = option.select('label')
                    self.assertEqual(len(labels), 5)
                    self.assertTrue(all(label['for'] == radio['id'] for label in labels))
                    named_by = [soup.find(id=ref) for ref in radio['aria-labelledby'].split()]
                    self.assertEqual(len(named_by), 8)
                    self.assertTrue(all(node is not None for node in named_by))
                    accessible_names.append(' '.join(node.get_text() for node in named_by))
                    described_by = radio['aria-describedby'].split()
                    self.assertEqual(soup.find(id=described_by[0]).get_text(), profile['translations'][lang])
                    self.assertEqual(described_by[1], radio['data-warning-id'])
                self.assertEqual(len(set(accessible_names)), 6)
                self.assertFalse(table.select('.shop-profile-content, .shop-profile-stats'))

    def test_wizard_table_is_compact_and_wraps_without_stacking_columns(self):
        all_rules = list(css_rules(ROOT / 'shop.css'))
        rules = dict(all_rules)
        self.assertEqual(rules['.shop-profile-table']['width'], '100%')
        self.assertEqual(rules['.shop-profile-table']['table-layout'], 'fixed')
        self.assertEqual(rules['.shop-profile-table']['border-collapse'], 'collapse')
        self.assertEqual(rules['.shop-profile-option label']['padding'], '.5rem')
        self.assertEqual(rules['.shop-profile-option label']['overflow-wrap'], 'anywhere')
        self.assertEqual(rules['.shop-profile-option .shop-profile-description']['padding-block'], '0 .5rem')
        self.assertEqual(rules['.shop-profile-option .shop-profile-radio-label']['min-height'], '2.75rem')
        self.assertEqual(rules['.shop-profile-option .shop-profile-radio-label']['grid-template-columns'], '18px minmax(0, 1fr)')
        self.assertEqual(rules['.shop-profile-option td']['vertical-align'], 'middle')
        self.assertEqual(rules['.shop-profile-option td']['text-align'], 'left')
        self.assertEqual(rules['.shop-profile-table th']['text-align'], 'left')
        self.assertEqual(rules['.shop-profile-table .shop-profile-price']['text-align'], 'right')
        for selector, expected in {
            '.shop-profile-operation-column': ['44%', '40%'],
            '.shop-profile-spec-column': ['20%'],
            '.shop-profile-price-column': ['16%', '20%'],
        }.items():
            self.assertEqual([declarations['width'] for name, declarations in all_rules if name == selector], expected)
        self.assertNotIn('font-size', rules['.shop-profile-option label'])
        self.assertFalse(any('.shop-profile-stats' in selector for selector in rules))
        for selector in ('.shop-profile-table', '.shop-profile-option td'):
            self.assertNotIn('grid-template-columns', rules[selector])

    def test_wizard_uses_required_main_form_controls_and_conditional_bearing_select(self):
        for lang, soup in self.pages():
            form = soup.select_one('form[data-wizard]')
            fields = form.select(':scope > .form-row > .form-group > input.validate-me')
            self.assertEqual([field['name'] for field in fields], ['engineType', 'bore', 'stroke', 'rockerRatio', 'exhaustValve', 'intakeValve'])
            self.assertEqual(len(form.select('input[name=bore]')), 1)
            for field in fields:
                self.assertTrue(field.has_attr('required'))
                self.assertTrue(form.find('label', attrs={'for': field['id']}))
                self.assertIn('warning-msg', field.find_next_sibling()['class'])
                if field['name'] == 'engineType':
                    self.assertEqual(field['type'], 'text')
                    self.assertEqual(field['maxlength'], '120')
                else:
                    self.assertEqual(field['type'], 'number')
                    self.assertEqual(field['step'], 'any')
                    self.assertEqual(field['min'], '0')
                    self.assertTrue(field.has_attr('data-positive'))
                    self.assertEqual(field['inputmode'], 'decimal')
            bearing = form.select_one('.shop-variant > select.custom-select[data-bearing]')
            self.assertTrue(bearing.has_attr('disabled'))
            self.assertTrue(form.select_one('[data-bearing-fields][hidden]'))
            self.assertEqual([option['value'] for option in bearing.select('option')], ['', 'small', 'large'])
            self.assertIn('39-38,5-30', bearing.get_text())
            self.assertIn('40,5-40-30', bearing.get_text())
            self.assertFalse(bearing.has_attr('data-variant'))
            self.assertTrue(form.find(id=bearing['data-warning-id']))
            main = BeautifulSoup((ROOT / lang / 'index.html').read_text(), 'html.parser')
            self.assertFalse(form.select('.mandatory-note, [id$="-profile-title"]'))
            self.assertEqual(form.find(recursive=False).name, 'h4')
            config = json.loads(soup.select_one('#shop-config').string)
            self.assertEqual(form.find(id=form.fieldset['aria-labelledby']).get_text(), config['text']['inquiryHeading'])
            self.assertTrue(form.find(id=form.fieldset['aria-describedby']))
            self.assertNotIn('Ø', form.get_text())
            if lang == 'cs':
                labels = [form.find('label', attrs={'for': field['id']}).get_text() for field in fields]
                self.assertEqual(labels, ['Typ motoru *', 'Vrtání (mm) *', 'Zdvih (mm) *',
                                         'Převodový poměr vahadla *', 'Průměr talířku V ventilu (mm) *',
                                         'Průměr talířku S ventilu (mm) *'])
                self.assertNotIn('* povinná pole', form.get_text())
                self.assertNotIn('Provedení', form.get_text())
            self.assertEqual(form.select_one('[name=engineType] + .warning-msg').get_text(),
                             main.select_one('[name=fullname] + .warning-msg').get_text())

    def test_inquiry_heading_precedes_table_and_reuses_engine_heading_style(self):
        expected = {
            'cs': 'Poptávka', 'en': 'Enquiry', 'de': 'Anfrage', 'fr': 'Demande',
            'it': 'Richiesta', 'es': 'Solicitud', 'pl': 'Zapytanie',
            'ru': 'Запрос', 'ja': 'お問い合わせ', 'zh': '询价',
        }
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                form = soup.select_one('form[data-wizard]')
                text = json.loads(soup.select_one('#shop-config').string)['text']
                headings = form.select(':scope > h4.form-section-title')
                self.assertEqual([heading.get_text() for heading in headings],
                                 [expected[lang], text['engineHeading']])
                self.assertEqual(headings[0]['class'], headings[1]['class'])
                self.assertIs(headings[0], form.find(recursive=False))
                self.assertIs(headings[0].find_next_sibling(), form.fieldset)
                self.assertEqual(form.fieldset['aria-labelledby'], headings[0]['id'])
                self.assertTrue(form.fieldset.select_one('table.shop-profile-table'))
                self.assertFalse(form.select('.mandatory-note'))

    def test_camshaft_operation_labels_are_used_in_options_and_client_config(self):
        expected = {
            'cs': ('Úkon', 'Výroba'), 'en': ('Operation', 'Manufacture'),
            'de': ('Bearbeitung', 'Fertigung'), 'fr': ('Opération', 'Fabrication'),
            'it': ('Lavorazione', 'Produzione'), 'es': ('Operación', 'Fabricación'),
            'pl': ('Operacja', 'Produkcja'), 'ru': ('Операция', 'Изготовление'),
            'ja': ('作業', '製作'), 'zh': ('工序', '制造'),
        }
        for lang, soup in self.pages():
            config = json.loads(soup.select_one('#shop-config').string)
            operation, manufacture = expected[lang]
            self.assertEqual(config['text']['profileHeading'], operation)
            self.assertEqual(config['text']['manufactureNew'], manufacture)
            for option in soup.select('.shop-profile-option'):
                label = manufacture if option.input['value'].startswith('new-') else config['text']['manufactureRegrind']
                self.assertEqual(option.select_one('.shop-profile-method').get_text(), label)

    def test_invalid_wizard_profiles_and_fields_fail_before_rendering(self):
        for mutate in (
            lambda w: w['profiles'][0].update(price=0),
            lambda w: w['profiles'][0].update(manufacture='unknown'),
            lambda w: w['profiles'][0]['translations'].pop('cs'),
            lambda w: w['profiles'].append(w['profiles'][0]),
            lambda w: w['fields'][0].update(type='email'),
            lambda w: w['fields'][0].update(maxLength=0),
        ):
            invalid = json.loads(json.dumps(self.catalog))
            mutate(invalid['products'][0]['wizard'])
            with patch('build_shop.json.loads', return_value=invalid), self.assertRaises(ValueError):
                load_catalog()

    def test_invalid_catalog_fails_before_rendering(self):
        invalid = json.loads(json.dumps(self.catalog))
        invalid['products'][0]['price'] = -1
        with patch('build_shop.json.loads', return_value=invalid):
            with self.assertRaises(ValueError):
                load_catalog()

    def test_missing_placeholder_fails_before_rendering(self):
        invalid = json.loads(json.dumps(self.catalog))
        invalid['placeholderImage'] = '/assets/desktop/nonexistent-photo.webp'
        with patch('build_shop.json.loads', return_value=invalid):
            with self.assertRaises(ValueError):
                load_catalog()


if __name__ == '__main__':
    unittest.main()
