import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from build_shop import ROOT, build_shop, load_catalog


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
                self.assertEqual(len(soup.select('.shop-product')), 17)
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
                self.assertEqual(len(fields), len(self.catalog['products']))
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
        for prop in ('font-size', 'color', 'border-bottom', 'padding-bottom', 'display'):
            self.assertEqual(product_heading[prop], shared_heading[prop], prop)
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
                self.assertNotIn(field, matched, f'{selector} overrides shared field styles: {overrides}')

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
            self.assertEqual(len(soup.select('.shop-photo > .shop-photo-link > .tech-frame img')), 17)
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
                for photo in soup.select('.shop-photo'):
                    link = photo.select_one(':scope > a.shop-photo-link')
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
            self.assertEqual(len(soup.select('.shop-product img')), 17)
            self.assertEqual(len(soup.select('img[data-placeholder]')), 14)
            self.assertFalse(soup.select('.shop-photo figcaption'))
            for product in self.catalog['products']:
                photo = soup.find(id=product['id']).find('img')
                self.assertEqual(photo['src'], product['image'] or self.catalog['placeholderImage'])
                self.assertEqual(photo.has_attr('data-placeholder'), not bool(product['image']))
                if photo.has_attr('data-placeholder'):
                    self.assertEqual(photo['alt'], text['noPhoto'])
                else:
                    self.assertEqual(photo['alt'], product['translations'][lang]['name'])
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
                self.assertEqual(len(prices), 3 if product['dealerPrice'] else 1)
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
            self.assertEqual(len(soup.select('.shop-photo .tech-frame')), len(self.catalog['products']))
            self.assertTrue(soup.select_one('#order.section'))

    def test_rebuild_is_deterministic(self):
        original = {p: p.read_bytes() for p in self.output.glob('*/shop.html')}
        with contextlib.redirect_stdout(io.StringIO()):
            build_shop(output_root=self.output)
        self.assertEqual(original, {p: p.read_bytes() for p in original})

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
