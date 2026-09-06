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

from build_shop import ROOT, build_order_catalog, build_shop, load_catalog, money, product_card, standard_options


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
        cls.photo_count = sum(len(product.get('images', [])) or 1
                              for product in cls.catalog['products'] if product.get('image'))
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
                self.assertEqual(len(soup.select('.shop-product')), len(self.catalog['products']))
                self.assertEqual(len(soup.select('h1')), 1)
                self.assertNotIn('TAZ', soup.h1.text)
                self.assertTrue(soup.select_one('#catalog-title.shop-sr-only'))
                self.assertFalse(soup.select('#catalog > .shop-section-heading'))
                self.assertFalse(soup.select('.shop-intro, .shop-product-code'))

    def test_customer_email_copy_must_be_complete_in_every_language(self):
        translations = json.loads((ROOT / 'shop/translations.json').read_text())
        original = json.loads((ROOT / 'shop/order-email-translations.json').read_text())
        for change in ('language', 'key', 'empty'):
            copy = json.loads(json.dumps(original))
            if change == 'language': del copy['fr']
            elif change == 'key': del copy['fr']['nextStep']
            else: copy['fr']['nextStep'] = ''
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'Incomplete order email'):
                build_order_catalog(self.catalog, translations, copy, self.output)

    def test_frontend_only_build_matches_pages_without_touching_backend(self):
        with tempfile.TemporaryDirectory(prefix='muckova-frontend-build-') as directory:
            target = Path(directory)
            with patch('build_shop.build_order_catalog', side_effect=AssertionError('Backend generation is disabled')), contextlib.redirect_stdout(io.StringIO()):
                build_shop(languages=['cs'], output_root=target, include_backend=False)
                self.assertFalse((target / 'backend').exists())
                self.assertEqual((target / 'cs/shop.html').read_bytes(), (self.output / 'cs/shop.html').read_bytes())
                backend = target / 'backend/order_catalog.php'
                backend.parent.mkdir()
                backend.write_text('private backend catalogue', encoding='utf-8')
                build_shop(languages=['cs'], output_root=target, include_backend=False)
                self.assertEqual(backend.read_text(encoding='utf-8'), 'private backend catalogue')

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
                    self.assertEqual(product.find(recursive=False).name, 'header')
                    self.assertEqual(product['aria-labelledby'], product.h3['id'])
                    for button in product.select('.shop-quantity button'):
                        self.assertTrue(button.get('aria-label'))
                    for image in product.select('img'):
                        self.assertTrue(image.get('alt'))
                        self.assertTrue((ROOT / image['src'].lstrip('/')).is_file())

    def test_quantity_controls_allow_9999_and_share_the_runtime_limit(self):
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                fields = soup.select('.shop-product input[data-order-quantity]')
                self.assertEqual(len(fields), sum(p.get('kind') != 'wizard' for p in self.catalog['products']))
                for field in fields:
                    self.assertEqual(field['type'], 'number')
                    self.assertEqual(field['min'], '1')
                    self.assertEqual(field['max'], '9999')
                    self.assertEqual(field['step'], '1')
                    self.assertEqual(field['inputmode'], 'numeric')
                    spinner = field.parent
                    self.assertIn('shop-quantity', spinner['class'])
                    self.assertEqual(spinner['role'], 'group')
                    self.assertEqual(spinner['aria-labelledby'], 'label-' + field['id'])
                    buttons = spinner.select('button[type=button][data-order-change][disabled]')
                    self.assertEqual([button['data-order-change'] for button in buttons], ['-1', '1'])
                    self.assertTrue(all(button['aria-controls'] == field['id'] for button in buttons))
                    self.assertEqual(spinner.find_next_sibling('span')['id'], field['data-warning-id'])
        source = (ROOT / 'shop.js').read_text()
        self.assertIn('const MAX_QUANTITY = 9999;', source)
        self.assertIn('control.max = String(MAX_QUANTITY)', source)
        self.assertIn('value >= MAX_QUANTITY', source)
        self.assertIn('value > MAX_QUANTITY', source)
        self.assertIn('initBasketQuantitySelection(basketList);', source)

    def test_product_headings_reuse_blog_titles_instead_of_the_team_name_underline(self):
        blog_rules = list(css_rules(ROOT / 'blog.css'))
        shop_rules = dict(css_rules(ROOT / 'shop.css'))
        product_heading = shop_rules['.shop-product-title']
        self.assertEqual(product_heading['max-width'], '100%')
        for prop in ('font-size', 'font-family', 'border', 'border-bottom', 'text-align', 'text-transform'):
            self.assertNotIn(prop, product_heading)
        shared = [props for selector, props in blog_rules if selector == '.article-header h1, .article-header .article-title']
        self.assertEqual([props['font-size'] for props in shared], ['2.2rem', '1.6rem'])
        for lang, soup in self.pages():
            self.assertEqual(len(soup.select('.shop-product > .article-header > h3.article-title.shop-product-title')),
                             len(self.catalog['products']))

    def test_product_tags_leads_and_bullets_use_the_blog_components_in_every_locale(self):
        for lang, soup in self.pages():
            text = json.loads(soup.select_one('#shop-config').string)['text']
            for product in self.catalog['products']:
                card = soup.find(id=product['id'])
                header = card.select_one(':scope > header.article-header')
                key = 'tag' + product['category'][0].upper() + product['category'][1:]
                self.assertEqual([tag.text for tag in header.select('.meta-tags > .sys-tag')],
                                 [text[key], *product['tags']])
                paragraphs = [p for p in product['translations'][lang]['description'].split('\n\n') if p.strip()]
                self.assertEqual([node.text for node in header.select('.lead')], paragraphs[:1])
                self.assertTrue(card.select_one(':scope > .tech-divider'))
                self.assertFalse(card.select('form .article-body, .article-body form, .tech-table'))
                for item in card.select('li.shop-description'):
                    self.assertIn('tech-list', item.parent['class'])

    def test_product_tags_are_valid_presentation_metadata_only(self):
        from build_shop import client_products, order_catalog_version
        copy = json.loads(json.dumps(self.catalog))
        for product in copy['products']:
            product['category'] = 'fuel'
            product['tags'] = ['Different presentation']
        self.assertEqual(client_products(copy, 'cs'), client_products(self.catalog, 'cs'))
        self.assertEqual(order_catalog_version(copy), order_catalog_version(self.catalog))
        for change in ({'category': 'unknown'}, {'tags': 'not-a-list'}, {'tags': []}, {'tags': [' ']}):
            copy = json.loads(json.dumps(self.catalog))
            copy['products'][0].update(change)
            with patch('build_shop.json.loads', return_value=copy), self.assertRaisesRegex(ValueError, 'presentation tags'):
                load_catalog()

    def test_standard_products_reuse_the_photo_led_layout_and_expanding_order_table(self):
        for lang, soup in self.pages():
            for product in self.catalog['products']:
                if product.get('kind') == 'wizard':
                    continue
                with self.subTest(lang=lang, product=product['id']):
                    card = soup.find(id=product['id'])
                    self.assertIn('shop-wizard-product', card['class'])
                    paragraphs = [p for p in product['translations'][lang]['description'].split('\n\n') if p.strip()]
                    has_content = bool(product.get('image') or len(paragraphs) > 1 or product['id'] == 'exhaust-headers')
                    self.assertEqual([node.name for node in card.find_all(recursive=False)],
                                     ['header', 'hr', *(['div'] if has_content else []), 'form'])
                    self.assertFalse(card.select('.shop-prices, .shop-product-order, [data-change], [data-quantity]'))
                    self.assertEqual([node.get_text() for node in card.select('.shop-description')],
                                     [paragraph for paragraph in product['translations'][lang]['description'].split('\n\n') if paragraph.strip()])
                    form = card.select_one('form[data-order-product][novalidate]')
                    options = standard_options(product, lang)
                    radios = form.select('input[type=radio][name=option]')
                    self.assertEqual([radio['value'] for radio in radios], [option['id'] for option in options])
                    self.assertTrue(all(not radio.has_attr('required') and 'validate-me' not in radio.get('class', []) for radio in radios))
                    self.assertEqual(len(form.select('thead th')), 2)
                    text = json.loads(soup.select_one('#shop-config').string)['text']
                    self.assertEqual(form.select_one('thead th').get_text(), text['variant'])
                    fields = form.select_one('tbody[data-profile-fields][hidden]')
                    self.assertTrue(fields.select_one('input[data-order-quantity][required][disabled]'))
                    self.assertTrue(fields.select_one('button[type=submit].btn-submit[disabled]'))
                    for radio in radios:
                        self.assertTrue(all(soup.find(id=ref) is not None for ref in radio['aria-labelledby'].split()))

    def test_all_cards_reuse_blog_padding_and_isolate_the_ordering_table(self):
        rules = dict(css_rules(ROOT / 'shop.css'))
        self.assertNotIn('padding', rules['.shop-product'])
        self.assertNotIn('grid-template-areas', rules['.shop-product'])
        self.assertEqual(rules['.shop-product-body']['margin-bottom'], '30px')
        for _, soup in self.pages():
            self.assertEqual(len(soup.select('.shop-product.shop-wizard-product')), len(self.catalog['products']))
            for form in soup.select('.shop-product form'):
                self.assertIn('shop-product', form.parent['class'])
                self.assertIsNone(form.find_parent(class_='article-body'))

    def test_merged_products_keep_all_options_and_original_prices_in_every_locale(self):
        products = {product['id']: product for product in self.catalog['products']}
        self.assertEqual(len(products), 13)
        self.assertTrue({'connecting-rod-160', 'connecting-rod-156', 'head-gasket-stock',
                         'ignition-coil-contact', 'ignition-coil-contactless', 'distributor-cap',
                         'distributor-contacts', 'distributor-capacitor', 'ignition-wiring'}.isdisjoint(products))
        expected = {
            'exhaust-headers': [('small', 6600), ('large', 6600)],
            'connecting-rod': [('160', 12500), ('156', 11500), ('156-engitec', 12500)],
            'ignition-coil': [('contact', 780), ('contactless', 1100)],
            'distributor-parts': [('cap', 260), ('wiring', 280), ('contacts', 150), ('capacitor', 180)],
            'head-gasket': [('80-5', 620), ('82-0', 620), ('stock', 160), ('custom', None)],
            'cylinder-piston-kit': [('complete', 18000), ('pistons-rings', 10400), ('rings', 1600)],
        }
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                config = json.loads(soup.select_one('#shop-config').string)
                for product_id, prices in expected.items():
                    options = standard_options(products[product_id], lang)
                    self.assertEqual([(option['id'], option['price']) for option in options], prices)
                    for option, variant in zip(options, products[product_id]['variants']):
                        self.assertEqual(option['name'], variant['translations'][lang])
                        self.assertEqual(option['variants'][0]['label'], variant['translations'][lang])
                    client = next(product for product in config['products'] if product['id'] == product_id)
                    self.assertEqual(client['options'], options)
                    self.assertEqual(client.get('legacyItems', []), products[product_id].get('legacyItems', []))
                    self.assertEqual(len(soup.find(id=product_id).select('input[name=option]')), len(prices))
                self.assertFalse(soup.select('#head-gasket select[data-order-variant]'))
                for product_id in ('distributor-parts', 'cylinder-piston-kit', 'carburetor-38-38'):
                    self.assertFalse(soup.find(id=product_id).select_one('img[data-placeholder]'))
                self.assertEqual(products['carburetor-38-38']['price'], 7900)
                self.assertEqual(products['distributor-overhaul']['priceType'], 'approx')
                rings = products['copper-rings']['translations'][lang]
                self.assertNotIn(' - ', rings['name'])
                self.assertEqual(rings['description'], '')
                if lang == 'cs':
                    self.assertEqual(rings['name'], 'Vymezovací Cu kroužky pod válce')
                    self.assertEqual(rings['optionName'], 'Pro motory TAZ')
                    self.assertEqual(rings['optionDescription'], 'Cena dle rozměrů a množství')

    def test_custom_gasket_has_quote_price_and_typed_required_option_fields(self):
        for lang, soup in self.pages():
            config = json.loads(soup.select_one('#shop-config').string)
            product = next(product for product in config['products'] if product['id'] == 'head-gasket')
            option = product['options'][-1]
            self.assertEqual((option['id'], option['price'], option['priceType']), ('custom', None, 'quote'))
            form = soup.select_one('#item-head-gasket')
            self.assertEqual(form.select_one('#head-gasket-option-custom-price').text, config['text']['quote'])
            self.assertEqual(len(soup.select('#head-gasket .shop-description')), 1)
            fields = form.select('[data-order-field]')
            self.assertEqual([field['name'] for field in fields], ['spacing', 'thickness'])
            for field, key in zip(fields, ('gasketSpacing', 'gasketThickness')):
                self.assertTrue(field.has_attr('required') and field.has_attr('disabled'))
                self.assertTrue(field.find_parent('tr').has_attr('hidden'))
                self.assertEqual(field.find_parent('tr')['data-order-field-row'], 'custom')
                self.assertEqual(form.find('label', attrs={'for': field['id']}).text, config['text'][key] + ' *')
            self.assertEqual((fields[0]['type'], fields[0]['maxlength']), ('text', '200'))
            self.assertFalse(fields[0].has_attr('min'))
            self.assertEqual((fields[1]['type'], fields[1]['min'], fields[1]['step']), ('number', '0', 'any'))
            self.assertTrue(fields[1].has_attr('data-positive'))
            self.assertEqual(fields[1].find_next_sibling('span').text, config['text']['positiveNumber'])
            if lang == 'cs':
                self.assertEqual(option['name'], 'Na přání')
                self.assertEqual(config['text']['gasketSpacing'], 'Rozteč (mm)')
                self.assertEqual(config['text']['gasketThickness'], 'Tloušťka (mm)')

    def test_single_option_descriptions_and_revised_product_copy_in_every_locale(self):
        products = {product['id']: product for product in self.catalog['products']}
        for lang, soup in self.pages():
            for product_id in ('copper-rings', 'distributor-overhaul'):
                product = products[product_id]
                option = standard_options(product, lang)[0]
                self.assertEqual(option['name'], product['translations'][lang]['optionName'])
                self.assertEqual(option['description'], product['translations'][lang]['optionDescription'])
                self.assertTrue(option['description'])
                card = soup.find(id=product_id)
                self.assertEqual(card.select_one('.shop-profile-description').text, option['description'])
                self.assertEqual(card.select_one('.shop-profile-price[rowspan]')['rowspan'], '2')
            self.assertEqual(len(soup.select('#carburetor-38-38 .shop-description')), 2)
            self.assertEqual(len(soup.select('#distributor-overhaul .shop-description')), 3)
            self.assertFalse(soup.select('#copper-rings .article-body, #copper-rings .lead'))
            if lang == 'cs':
                self.assertEqual(soup.select_one('#name-distributor-parts').text, 'Rozdělovače – náhradní díly')
                self.assertEqual(soup.select_one('#name-carburetor-38-38').text, 'Dvojitý karburátor 38/38')
                self.assertEqual(soup.select('#carburetor-38-38 .shop-description')[1].text,
                                 'Doporučujeme doladění karburátoru na motorové brzdě (na dotaz).')
                self.assertEqual([p.text for p in soup.select('#distributor-overhaul .shop-description')], [
                    'V ceně nejsou zahrnuty náhradní díly – kontakty, kondenzátor, cívka a jiné.',
                    'Pouze rozdělovače CZ výroby – u čínských nebo polských kopií nemůžeme zaručit správnou funkci.',
                    'Na úpravu dodejte vždy umyté a odmaštěné díly.'])

    def test_invalid_quote_overrides_and_option_field_types_fail_before_rendering(self):
        for mutate in (
            lambda v: v.update(price=620),
            lambda v: v.update(priceType='fixed'),
            lambda v: v.update(priceType='unknown'),
            lambda v: v['fields'][0].update(type='unknown'),
            lambda v: v['fields'][0].update(maxLength=0),
            lambda v: v['fields'][0].update(maxLength=201),
            lambda v: v['fields'][0].update(maxLength=True),
            lambda v: v['fields'][0].update(labelKey='missing'),
            lambda v: v['fields'][0].update(minimumField='thickness'),
            lambda v: v['fields'][1].update(minimumField='spacing'),
            lambda v: v['fields'][1].update(minimumField='missing'),
            lambda v: v['fields'][1].update(minimumField='thickness'),
        ):
            invalid = json.loads(json.dumps(self.catalog))
            gasket = next(product for product in invalid['products'] if product['id'] == 'head-gasket')
            mutate(gasket['variants'][-1])
            with patch('build_shop.json.loads', return_value=invalid), self.assertRaises(ValueError):
                load_catalog()

    def test_invalid_option_groups_prices_and_legacy_mappings_fail_before_rendering(self):
        for mutate in (
            lambda p: p['variants'][0].update(price=0),
            lambda p: p['variants'][0].update(price=True),
            lambda p: p['variants'][0].update(price=900),
            lambda p: p['variants'][2]['translations'].pop('cs'),
            lambda p: p['options'][0].update(variantIds=[]),
            lambda p: p['options'][0].update(variantIds=['80-5', 'stock']),
            lambda p: p['options'][1].update(id='custom'),
            lambda p: p['options'][1]['translations'].pop('cs'),
            lambda p: p['legacyItems'][0].update(targetVariant='missing'),
            lambda p: p['legacyItems'][0].update(id='connecting-rod'),
        ):
            invalid = json.loads(json.dumps(self.catalog))
            gasket = next(product for product in invalid['products'] if product['id'] == 'head-gasket')
            # Keep group validation covered even though the live gaskets now use direct radio options.
            gasket['options'] = [
                {'id': 'custom', 'variantIds': ['80-5', '82-0'],
                 'translations': {lang: {'name': 'Custom'} for lang in self.catalog['languages']}},
                {'id': 'stock', 'variantIds': ['stock'],
                 'translations': {lang: {'name': 'Stock'} for lang in self.catalog['languages']}},
                {'id': 'bespoke', 'variantIds': ['custom'],
                 'translations': {lang: {'name': 'Bespoke'} for lang in self.catalog['languages']}},
            ]
            mutate(gasket)
            with patch('build_shop.json.loads', return_value=invalid), self.assertRaises(ValueError):
                load_catalog()

    def test_product_sections_keep_spacing_without_separator_lines(self):
        rules = dict(css_rules(ROOT / 'shop.css'))
        self.assertEqual(rules['.shop-prices, .shop-product-order'], {'padding-top': '19px'})
        self.assertNotRegex((ROOT / 'shop.css').read_text(),
                            r'\.shop-(?:prices|product-order)::(?:before|after)')
        for selector in ('.shop-prices', '.shop-product-order'):
            self.assertNotIn('width', rules[selector])
            self.assertNotIn('border-top', rules[selector])

    def test_add_buttons_match_field_height_without_changing_the_final_order_button(self):
        rules = dict(css_rules(ROOT / 'shop.css'))
        button = rules['.shop-profile-submit .btn-submit']
        self.assertEqual(button['height'], '42px')
        self.assertEqual(button['padding'], '0')
        self.assertEqual(button['box-shadow'], 'none')
        self.assertEqual(rules['.shop-profile-submit .btn-submit:hover']['box-shadow'], 'none')
        self.assertEqual(rules['.shop-profile-submit .btn-submit:hover']['transform'], 'none')
        self.assertEqual(rules['.shop-button:hover, .shop-profile-submit .btn-submit:hover']['background'], '#ff6666')
        for _, soup in self.pages():
            self.assertEqual(len(soup.select('.shop-profile-submit .btn-submit')), len(self.catalog['products']))
            self.assertNotIn(soup.select_one('#order-prepare'), soup.select('.shop-profile-submit .btn-submit'))

    def test_rotor_parameters_are_required_only_in_the_custom_option_and_copy_is_concise(self):
        for lang, soup in self.pages():
            config = json.loads(soup.select_one('#shop-config').string)
            rotor = next(product for product in config['products'] if product['id'] == 'distributor-rotor')
            self.assertEqual([option['id'] for option in rotor['options']], ['4800-5100', 'custom', 'original'])
            self.assertEqual(rotor['options'][2]['description'], '')
            form = soup.select_one('#item-distributor-rotor')
            original = form.select_one('input[value="original"]')
            self.assertFalse(original.has_attr('aria-describedby'))
            self.assertFalse(original.find_parent('tbody').select('.shop-profile-description'))
            self.assertEqual(len(form.select('input[name=option]')), 3)
            self.assertEqual(len(form.select('[data-order-field]')), 2)
            self.assertEqual([field['data-order-field'] for field in form.select('[data-order-field]')], ['min-rpm', 'max-rpm'])
            for field, key in zip(form.select('[data-order-field]'), ('minRpm', 'maxRpm')):
                self.assertEqual((field['type'], field['min'], field['step']), ('number', '1', '1'))
                self.assertTrue(field.has_attr('required') and field.has_attr('disabled'))
                self.assertEqual(field.find_parent('tr')['data-order-field-row'], 'custom')
                self.assertTrue(field.find_parent('tr').has_attr('hidden'))
                self.assertEqual(form.find('label', attrs={'for': field['id']}).text, config['text'][key] + ' *')
                self.assertEqual(field.find_next_sibling('span').text, config['text']['rpmWarning'])
            self.assertEqual(form.select_one('[data-order-field="max-rpm"]')['data-minimum-field'], 'min-rpm')
            for product_id in ('exhaust-headers', 'connecting-rod', 'ignition-coil', 'distributor-rotor'):
                self.assertFalse(soup.find(id=product_id).select('.shop-description'))
            for product_id in ('connecting-rod', 'ignition-coil', 'distributor-rotor'):
                self.assertIn('shop-no-description', soup.find(id=product_id)['class'])
                self.assertFalse(soup.find(id=product_id).select('.article-header .lead, .article-body p, .article-body .tech-list'))
            resonance = soup.select_one('#resonance-exhaust')
            self.assertEqual(resonance.img['src'], '/assets/desktop/rezonancni-vyfuk-01.jpg')
            self.assertFalse(resonance.select('img[data-placeholder]'))
            if lang == 'cs':
                self.assertEqual([option['name'] for option in rotor['options']],
                                 ['Upravený na 4800-5100 ot/min', 'Upravený na přání', 'Originál Bosch / Facet, EPS'])
                self.assertEqual(resonance.select_one('.shop-profile-method').text, 'TAZ 1,43 – TAZ 1,6')
                self.assertEqual(resonance.select_one('.shop-description').text, 'Rezonanční výfuk montovaný na sériový litinový svod.')

    def test_nested_variants_reuse_main_form_dropdowns_and_remain_scoped_to_their_option(self):
        for lang, soup in self.pages():
            main = BeautifulSoup((ROOT / lang / 'index.html').read_text(), 'html.parser')
            scripts = [script['src'] for script in soup.select('script[src]')]
            choices_js = main.select_one('script[src*="choices.js@"]')['src']
            self.assertLess(scripts.index(choices_js), next(i for i, src in enumerate(scripts) if src.startswith('/shop.js?')))
            for product in self.catalog['products']:
                if product.get('kind') == 'wizard':
                    continue
                card = soup.find(id=product['id'])
                nested = [option for option in standard_options(product, lang) if len(option['variants']) > 1]
                self.assertEqual(len(card.select('select[data-order-variant]')), len(nested))
                for option in nested:
                    row = card.select_one('[data-order-variant-fields="' + option['id'] + '"][hidden]')
                    select = row.select_one('select.custom-select.validate-me[required][disabled]')
                    self.assertEqual(row.find('label', attrs={'for': select['id']})['id'], 'label-' + select['id'])
                    self.assertEqual([value['value'] for value in select.select('option')], ['', *[variant['id'] for variant in option['variants']]])

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
                # The configurator intentionally uses a smaller type scale and
                # shorter controls. The final order form stays fully shared.
                if field.find_parent(class_='shop-wizard-form'):
                    field_overrides = overrides - {'font-size', 'height', 'line-height', 'padding'}
                elif field.find_parent(class_='shop-product'):
                    field_overrides = overrides - {'font-size'}
                else:
                    field_overrides = overrides
                if field_overrides:
                    self.assertNotIn(field, matched, f'{selector} overrides shared field styles: {field_overrides}')

    def test_product_ordering_type_scale_stays_14px_while_copy_inherits_blog_styles(self):
        all_rules = list(css_rules(ROOT / 'shop.css'))
        rules = dict(all_rules)
        product = next(declarations for selector, declarations in all_rules if selector == '.shop-product')
        self.assertEqual(product['--shop-product-font-size'], '.875rem')
        self.assertEqual(product['--shop-product-small-font-size'], '.8125rem')
        self.assertEqual(product['--shop-product-caption-font-size'], '.75rem')
        self.assertEqual(product['font-size'], 'var(--shop-product-font-size)')
        for selector, size in {
            '.shop-prices': 'var(--shop-product-small-font-size)',
            '.shop-profile-label': 'var(--shop-product-caption-font-size)',
            '.shop-product .warning-msg': 'var(--shop-product-caption-font-size)',
            '.shop-product .btn-submit': 'calc(var(--shop-product-font-size) * 1.2)',
        }.items():
            self.assertEqual(rules[selector]['font-size'], size, selector)
        self.assertNotIn('font-size', rules['.shop-description'])
        self.assertNotIn('font-size', rules['.shop-product-title'])
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

    def test_wizard_field_rows_use_the_profile_tables_compact_scale(self):
        rules = dict(css_rules(ROOT / 'shop.css'))
        self.assertEqual(rules['.shop-profile-fields']['background'], '#100909')
        cells = rules['.shop-profile-field > th, .shop-profile-field > td']
        self.assertEqual(cells['padding'], '.45rem .5rem')
        self.assertEqual(cells['vertical-align'], 'top')
        self.assertEqual(rules['.shop-profile-field > th']['box-shadow'], 'inset 3px 0 var(--accent)')

        labels = rules['.shop-profile-field > th label']
        self.assertEqual(labels['font-size'], 'var(--shop-product-small-font-size)')
        self.assertEqual(labels['margin'], '0')
        self.assertEqual(labels['letter-spacing'], '.5px')
        self.assertEqual(rules['.shop-profile-field > td > .form-group']['width'], '100%')
        self.assertEqual(rules['.shop-profile-field > td > .form-group']['min-width'], '0')

        input_selector = next(selector for selector in rules
                              if selector.startswith('.shop-wizard-form input[type="text"]'))
        for prop, value in {
            'font-size': 'var(--shop-product-font-size)',
            'height': '42px',
            'line-height': '42px',
            'padding': '0 12px',
        }.items():
            self.assertEqual(rules[input_selector][prop], value, prop)

        select = rules['.shop-wizard-form select.custom-select']
        self.assertEqual(select['height'], '42px')
        self.assertEqual(select['padding'], '0 12px')
        self.assertEqual(select['font-size'], 'var(--shop-product-font-size)')
        choices = rules['.shop-wizard-form .choices__inner']
        self.assertEqual(choices['min-height'], '42px !important')
        self.assertEqual(choices['max-height'], '42px !important')
        self.assertEqual(choices['padding'], '0 12px !important')

        _, soup = next(self.pages())
        compact_fields = soup.select('.shop-wizard-form input[type="text"], '
                                     '.shop-wizard-form input[type="number"], '
                                     '.shop-wizard-form select.custom-select')
        self.assertTrue(compact_fields)
        self.assertFalse(any(field.find_parent(class_='shop-order') for field in compact_fields))

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
            self.assertEqual(len(soup.select('.shop-photo > .shop-photo-link > .blog-img-frame img.blog-img')), self.photo_count)
            for photo in soup.select('.shop-photo-link'):
                self.assertEqual(photo['href'], photo.img['src'])
                self.assertEqual(photo['aria-haspopup'], 'dialog')
                self.assertTrue(photo['aria-label'].startswith(text['enlargePhoto']))

    def test_photos_are_horizontally_centered_and_reuse_blog_red_corner_frames(self):
        rules = dict(css_rules(ROOT / 'shop.css'))
        self.assertEqual(rules['.shop-photo-link']['cursor'], 'zoom-in')
        self.assertEqual(rules['.shop-photo-link']['width'], 'var(--shop-photo-width)')
        self.assertEqual(rules['.shop-photo-link']['max-width'], '100%')
        self.assertEqual(rules['.shop-photo-link']['margin-inline'], 'auto')
        self.assertNotIn('overflow', rules['.shop-photo-link'])
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                blog = BeautifulSoup((ROOT / lang / 'blog.html').read_text(), 'html.parser')
                self.assertTrue(blog.select_one('.blog-figure .blog-img-frame img.blog-img'))
                self.assertTrue(soup.select('.shop-photo.blog-figure'))
                self.assertFalse(soup.select('.shop-photo .tech-frame'))
                for link in soup.select('.shop-photo > a.shop-photo-link'):
                    frame = link.select_one(':scope > .blog-img-frame')
                    self.assertIsNotNone(frame.img)
                    self.assertNotIn('blog-img-frame', link['class'])
                    self.assertIsNone(frame.find('figcaption'))
                self.assertFalse(soup.select('#shop-lightbox .blog-img-frame'))

    def test_pointer_restored_photo_focus_does_not_remove_the_blog_frame(self):
        blog_rules = dict(css_rules(ROOT / 'blog.css'))
        shop_rules = dict(css_rules(ROOT / 'shop.css'))
        corners = blog_rules['.blog-img-frame::before, .blog-img-frame::after']
        self.assertEqual(corners['border-color'], 'var(--accent)')
        self.assertNotIn('opacity', corners)
        focus_rule = '.shop-page .shop-photo-pointer-focus:focus, .shop-page .shop-photo-pointer-focus :focus'
        self.assertEqual(shop_rules[focus_rule], {'outline': 'none !important'})
        self.assertEqual(shop_rules['.shop-page :focus-visible']['outline'], '2px solid #fff !important')
        self.assertFalse(any('tech-frame' in selector for selector in shop_rules))
        # Pointer focus only suppresses the ring on the link, not the decorative frame.
        _, soup = next(self.pages())
        for link in soup.select('.shop-photo-link'):
            link['class'].append('shop-photo-pointer-focus')
            self.assertTrue(link.select_one('.blog-img-frame img.blog-img'))
        source = (ROOT / 'shop.js').read_text()
        self.assertIn("opener?.focus({ preventScroll: true })", source)
        self.assertIn("link.classList.remove('shop-photo-pointer-focus')", source)

    def test_standard_product_photos_keep_natural_proportions_without_letterboxing_or_cropping(self):
        rules = dict(css_rules(ROOT / 'shop.css'))
        self.assertEqual(rules['.shop-photo .blog-img-frame, .shop-photo-viewport'], {'display': 'block'})
        image = rules['.shop-photo img']
        self.assertEqual(image['display'], 'block')
        self.assertEqual(image['width'], '100%')
        self.assertEqual(image['max-width'], '100%')
        self.assertEqual(image['height'], 'auto')
        for prop in ('position', 'inset', 'object-fit', 'aspect-ratio'):
            self.assertNotIn(prop, image)
        self.assertNotIn('.shop-photo-placeholder img', rules)
        _, soup = next(self.pages())
        photos = soup.select('.shop-photo:not(.shop-photo-gallery) img')
        frames = soup.select('.shop-photo:not(.shop-photo-gallery) .shop-photo-viewport')
        # Fixed gallery frames must not change single-photo products.
        for selector, declarations in css_rules(ROOT / 'shop.css'):
            if '::' in selector or not {'height', 'aspect-ratio', 'object-fit'}.intersection(declarations):
                continue
            for node in soup.select(selector):
                if node in photos or node in frames:
                    self.assertNotIn('aspect-ratio', declarations, selector)
                    self.assertNotIn('object-fit', declarations, selector)
                    if 'height' in declarations:
                        self.assertEqual(declarations['height'], 'auto', selector)

    def test_gallery_photos_use_a_fixed_landscape_crop_without_affecting_enlargement(self):
        rules = dict(css_rules(ROOT / 'shop.css'))
        frame_selector = '.shop-photo-gallery .shop-photo-viewport'
        image_selector = '.shop-photo-gallery .shop-photo-link img'
        self.assertEqual(rules[frame_selector], {'position': 'relative', 'aspect-ratio': '16 / 9'})
        self.assertEqual(rules[image_selector], {
            'position': 'absolute', 'inset': '0', 'width': '100%', 'height': '100%',
            'object-fit': 'cover', 'object-position': 'center',
        })
        gallery_photo_count = sum(len(product['images']) for product in self.catalog['products']
                                  if len(product.get('images', [])) > 1)
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                self.assertEqual(len(soup.select(frame_selector)), gallery_photo_count)
                self.assertEqual(len(soup.select(image_selector)), gallery_photo_count)
                self.assertFalse(soup.select_one('#shop-lightbox').select(image_selector))
                for photo in soup.select(image_selector):
                    # Keep original dimensions and source URLs for the fullscreen viewer.
                    self.assertEqual(photo.find_parent('a')['href'], photo['src'])
                    source = next(image for product in self.catalog['products']
                                  for image in product.get('images', []) if image['src'] == photo['src'])
                    self.assertEqual((int(photo['width']), int(photo['height'])),
                                     (source['width'], source['height']))

    def test_imageless_products_render_no_photo_markup_or_placeholder(self):
        for lang, soup in self.pages():
            self.assertEqual(len(soup.select('.shop-product img')), self.photo_count)
            self.assertFalse(soup.select('[data-placeholder], .shop-photo-placeholder'))
            self.assertNotIn('shop-placeholder.webp', str(soup))
            self.assertFalse(soup.select('.shop-photo figcaption'))
            for product in self.catalog['products']:
                card = soup.find(id=product['id'])
                self.assertEqual('shop-no-photo' in card['class'], not bool(product.get('image')))
                if product.get('image'):
                    photo = card.find('img')
                    self.assertEqual(photo['src'], product['image'])
                    expected_alt = product['images'][0]['alt'][lang] if product.get('images') else product['translations'][lang]['name']
                    self.assertEqual(photo['alt'], expected_alt)
                else:
                    self.assertFalse(card.select('figure, img, .shop-photo-link, .tech-frame, figcaption'))
                    self.assertTrue(card.select_one('form button[type=submit]'))
            self.assertFalse(soup.select('[itemprop=availability]'))

    def test_canonical_and_hreflang_are_clean(self):
        for lang, soup in self.pages():
            self.assertEqual(soup.select_one('link[rel=canonical]')['href'], f'https://www.petramuckova.cz/{lang}/shop')
            self.assertEqual(len(soup.select('link[rel=alternate]')), 11)
            self.assertTrue(all('?' not in link['href'] for link in soup.select('link[rel=alternate]')))

    def test_supplied_standard_product_photos_have_correct_paths_dimensions_and_localized_alt_text(self):
        expected = {
            'exhaust-headers': [('svody-ladene-01.jpeg', 435, 493)],
            'resonance-exhaust': [('rezonancni-vyfuk-01.jpg', 600, 639)],
            'head-gasket': [('tesneni-valce-01.jpeg', 1600, 1200), ('tesneni-valce-02.jpeg', 742, 497)],
            'connecting-rod': [('ojnice-h-kovana-01.jpeg', 4000, 2252)],
            'ignition-coil': [('zapalovaci-civka.jpg', 2252, 4000)],
            'distributor-rotor': [('palec-rozdelovace-omezovac-01.jpeg', 2046, 2048)],
            'distributor-parts': [('rozdelovace-01.jpeg', 1086, 1448)],
            'cylinder-piston-kit': [('sada-valce-02.jpeg', 4000, 2252), ('sada-valce-01.jpeg', 2252, 4000)],
            'carburetor-38-38': [('karburator.jpeg', 3376, 2252)],
            'distributor-overhaul': [('repas-rozdelovac-01.jpeg', 600, 800)],
        }
        for lang, soup in self.pages():
            for product_id, files in expected.items():
                with self.subTest(lang=lang, product=product_id):
                    product = next(product for product in self.catalog['products'] if product['id'] == product_id)
                    card = soup.find(id=product_id)
                    links = card.select('.shop-photo-link')
                    self.assertEqual(len(links), len(files))
                    self.assertEqual(bool(card.select_one('.shop-photo-gallery')), len(files) > 1)
                    self.assertFalse(card.select('img[data-placeholder], figcaption'))
                    for index, (link, (filename, width, height)) in enumerate(zip(links, files)):
                        path = '/assets/desktop/' + filename
                        self.assertEqual(link['href'], path)
                        self.assertEqual(link.img['src'], path)
                        self.assertEqual((int(link.img['width']), int(link.img['height'])), (width, height))
                        preview_width = min(width, product.get('photoMaxWidth', width),
                                            product.get('photoMaxHeight', height) * width / height)
                        self.assertEqual(link['style'], f'--shop-photo-width: {preview_width:g}px')
                        self.assertEqual(link.img['alt'], product['images'][index]['alt'][lang])
                        self.assertEqual(link.img['loading'], 'lazy')
                        self.assertTrue((ROOT / path.lstrip('/')).is_file())

    def test_resonance_photo_matches_manifold_preview_width_without_changing_aspect_ratio(self):
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                manifold = soup.select_one('#exhaust-headers .shop-photo-link')
                resonance = soup.select_one('#resonance-exhaust .shop-photo-link')
                self.assertEqual(resonance['style'], manifold['style'])
                self.assertEqual(resonance['style'], '--shop-photo-width: 435px')
                self.assertEqual((int(resonance.img['width']), int(resonance.img['height'])), (600, 639))
                self.assertEqual(resonance['href'], '/assets/desktop/rezonancni-vyfuk-01.jpg')
                self.assertFalse(soup.select('#resonance-exhaust .shop-photo-gallery'))
        rules = dict(css_rules(ROOT / 'shop.css'))
        self.assertEqual(rules['.shop-photo img']['height'], 'auto')
        self.assertEqual(rules['.shop-photo-link']['max-width'], '100%')

    def test_invalid_single_photo_width_limits_fail_before_rendering(self):
        for width in (0, -1, True, '435', 1.5, None):
            invalid = json.loads(json.dumps(self.catalog))
            next(product for product in invalid['products'] if product['id'] == 'resonance-exhaust')['photoMaxWidth'] = width
            with patch('build_shop.json.loads', return_value=invalid), self.assertRaises(ValueError):
                load_catalog()
        invalid = json.loads(json.dumps(self.catalog))
        invalid['products'][0]['photoMaxWidth'] = 435
        with patch('build_shop.json.loads', return_value=invalid), self.assertRaises(ValueError):
            load_catalog()

    def test_rotated_coil_photo_matches_exhaust_preview_width(self):
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                coil = soup.select_one('#ignition-coil .shop-photo-link')
                for product_id in ('exhaust-headers', 'resonance-exhaust'):
                    self.assertEqual(coil['style'], soup.select_one(f'#{product_id} .shop-photo-link')['style'])
                self.assertEqual(coil['style'], '--shop-photo-width: 435px')
                self.assertEqual(coil['href'], '/assets/desktop/zapalovaci-civka.jpg')
                self.assertEqual(coil.img['src'], coil['href'])
                self.assertEqual((int(coil.img['width']), int(coil.img['height'])), (2252, 4000))
                self.assertFalse(soup.select('#ignition-coil .shop-photo-gallery'))

    def test_three_tall_single_photo_previews_are_capped_without_changing_zoom_images(self):
        compact = {product['id']: product for product in self.catalog['products'] if 'photoMaxHeight' in product}
        self.assertEqual(set(compact), {'distributor-rotor', 'distributor-parts', 'distributor-overhaul'})
        for lang, soup in self.pages():
            for product_id, product in compact.items():
                with self.subTest(lang=lang, product=product_id):
                    self.assertEqual(product['photoMaxHeight'], 360)
                    image = product['images'][0]
                    card = soup.find(id=product_id)
                    self.assertFalse(card.select('.shop-photo-gallery'))
                    link = card.select_one('.shop-photo-link')
                    width = float(link['style'].removeprefix('--shop-photo-width: ').removesuffix('px'))
                    self.assertAlmostEqual(width * image['height'] / image['width'], 360, places=2)
                    self.assertEqual(link['href'], image['src'])
                    self.assertEqual(link.img['src'], image['src'])
                    self.assertEqual((int(link.img['width']), int(link.img['height'])), (image['width'], image['height']))

    def test_invalid_single_photo_height_limits_fail_before_rendering(self):
        for height in (0, -1, True, '360', 1.5, None):
            invalid = json.loads(json.dumps(self.catalog))
            next(product for product in invalid['products'] if product['id'] == 'distributor-rotor')['photoMaxHeight'] = height
            with patch('build_shop.json.loads', return_value=invalid), self.assertRaises(ValueError):
                load_catalog()
        invalid = json.loads(json.dumps(self.catalog))
        invalid['products'][0]['photoMaxHeight'] = 360  # Galleries have their own fixed frame.
        with patch('build_shop.json.loads', return_value=invalid), self.assertRaises(ValueError):
            load_catalog()

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
        expected_price_labels = {
            'en': 'Price / pc.', 'cs': 'Cena / ks', 'de': 'Preis / Stk.',
            'fr': 'Prix / pièce', 'it': 'Prezzo / pz.', 'es': 'Precio / ud.',
            'pl': 'Cena / szt.', 'ru': 'Цена / шт.', 'ja': '価格 / 個', 'zh': '价格 / 件',
        }
        for lang, soup in self.pages():
            self.assertFalse(soup.select('.shop-product details'))
            text = json.loads(soup.select_one('#shop-config').string)['text']
            self.assertNotIn('pricingNote', text)
            self.assertEqual(text['retail'], expected_price_labels[lang])
            for product in self.catalog['products']:
                card = soup.find(id=product['id'])
                self.assertFalse(card.select('.shop-price-row'))
                if product.get('kind') != 'wizard':
                    self.assertEqual(card.select_one('thead .shop-profile-price').get_text(), expected_price_labels[lang])
                    prices = card.select('.shop-profile-option .shop-profile-price')
                    options = standard_options(product, lang)
                    self.assertEqual(len(prices), len(options))
                    for cell, option in zip(prices, options):
                        price = text['quote'] if option['priceType'] == 'quote' else money(option['price'], lang)
                        if option['priceType'] in ('from', 'approx'):
                            price = text[option['priceType']] + ' ' + price
                        self.assertEqual(cell.get_text(strip=True), price)
                self.assertFalse(card.select('.shop-dealer-minimum'))
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
                self.assertEqual([node.name for node in intro.find_all(recursive=False)], ['h2'])
                self.assertTrue(order.select_one(':scope > .contact-intro + form.terminal-form'))
                self.assertEqual(len(order.select('.terminal-form')), 1)
                self.assertFalse(order.select('.blog-card, .shop-order-heading'))
                self.assertIsNone(intro.find_parent('form'))
                self.assertFalse(order.select('form .contact-intro'))

    def test_order_intro_retains_shared_heading_styles(self):
        _, soup = next(self.pages())
        intro_nodes = soup.select('#order > .contact-intro, #order > .contact-intro > h2')
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
                self.assertEqual(soup.select_one('#order-prepare').get_text(), text['prepare'])
                self.assertFalse(soup.select('#order .contact-sub-1'))
                self.assertNotIn(text['confirmation'], soup.select_one('#order').get_text())
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
                    self.assertEqual(text['prepare'], 'Objednat')
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
                self.assertEqual(len(headings), 4)
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
            self.assertIn('SiteForm.initSubmission(form,', source)
            self.assertNotIn('form.reportValidity()', source)
            self.assertNotIn('function validateInput(', source)

    def test_live_order_form_reuses_main_attachment_controls(self):
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                main = BeautifulSoup((ROOT / lang / 'index.html').read_text(), 'html.parser')
                form = soup.select_one('#shop-order-form')
                self.assertEqual(form['action'], '/backend/order_form_handler.php')
                self.assertEqual(form['method'], 'post')
                self.assertEqual(form['enctype'], 'multipart/form-data')
                self.assertEqual(len(form.select('input[type=file][name="attachment[]"]')), 3)
                self.assertEqual(form.select_one('#order-attachments-title').get_text(),
                                 main.select_one('.file-upload-input').find_previous('h4').get_text())
                for attachment in form.select('.file-upload-wrapper'):
                    for selector in ('.file-msg', '.btn-txt'):
                        self.assertEqual(attachment.select_one(selector).get_text(), main.select_one(selector).get_text())
                self.assertTrue(form.select_one('.hidden [name="bot-field"][tabindex="-1"]'))
                self.assertTrue(form.select_one('#order-message.form-message[aria-live="polite"]'))
                self.assertFalse(soup.select('#order-draft, #order-copy, #order-mailto'))
                config = json.loads(soup.select_one('#shop-config').string)
                self.assertRegex(config['catalogVersion'], r'^[a-f0-9]{64}$')
                self.assertIn('orderSent', config['text'])

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
                self.assertIsNone(soup.select_one('.shop-section-heading [data-basket-count]'))
                self.assertEqual(json.loads(soup.select_one('#shop-config').string)['text']['basket'], headings[lang])
        self.assertNotIn('[data-basket-count]', (ROOT / 'shop.js').read_text())

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
                    barcode = soup.footer.select_one('.copyright-bar .barcode')
                    self.assertIsNotNone(barcode)
                    self.assertFalse(barcode.has_attr('title'))

    def test_navigation_keeps_remaining_articles_without_spare_parts_post(self):
        for lang in self.catalog['languages']:
            for page in ('index', 'blog'):
                soup = BeautifulSoup((ROOT / lang / f'{page}.html').read_text(), 'html.parser')
                self.assertTrue(soup.select(f'a[href="/{lang}/shop"]'))
                if page == 'blog':
                    self.assertFalse(soup.select('#article-1, #post-1-title, a[href="#post-1-title"]'))
                    self.assertNotIn(self.catalog['copy'][lang]['title'], soup.get_text())
                    expected = [f'post-{number}-title' for number in range(2, 9)]
                    self.assertEqual([heading['id'] for heading in soup.select('.blog-card h1')], expected)
                    self.assertEqual(len(soup.select('.blog-card')), 7)
                    for selector in ('.toc-nav a', '.mobile-menu-list a[href^="#post-"]'):
                        links = soup.select(selector)
                        self.assertEqual([link['href'] for link in links], [f'#{anchor}' for anchor in expected])
                        self.assertEqual([link.get_text().split('.')[0] for link in links], list(map(str, range(1, 8))))
                    for link in soup.select('a[href^="#post-"]'):
                        self.assertIsNotNone(soup.find(id=link['href'][1:]))

    def test_navigation_has_keyboard_underlines_without_page_specific_focus_rings(self):
        rules = {re.sub(r'\s+', ' ', selector): declarations
                 for selector, declarations in css_rules(ROOT / 'main.css')}
        selectors = ['.navbar a', '.navbar .lang-toggle', 'a.nav-logo-mobile',
                     '.mobile-menu-list a', '.mobile-langchooser-list a']
        focus = rules[', '.join(selector + ':focus' for selector in selectors)]
        keyboard = rules[', '.join(selector + ':focus-visible' for selector in selectors)]
        self.assertEqual(focus['outline'], 'none !important')
        self.assertEqual(keyboard['text-decoration-line'], 'underline !important')
        self.assertEqual(keyboard['text-decoration-color'], 'var(--accent) !important')
        self.assertEqual(keyboard['text-decoration-thickness'], '1px !important')
        self.assertEqual(keyboard['text-underline-offset'], '0.3em')

    def test_shop_reuses_blog_header_footer_and_language_navigation(self):
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                blog = BeautifulSoup((ROOT / lang / 'blog.html').read_text(), 'html.parser')
                self.assertFalse(soup.select('a[href$="/blog#post-1-title"]'))
                article_links = soup.select('.mobile-menu-list a[href*="/blog#post-"]')
                self.assertEqual([link['href'] for link in article_links],
                                 [f'/{lang}/blog#post-{number}-title' for number in range(2, 9)])
                self.assertEqual([link.get_text().split('.')[0] for link in article_links], list(map(str, range(1, 8))))
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
                triggers = soup.select('button[aria-controls="mobile-menu-overlay"], button[aria-controls="mobile-langchooser-overlay"]')
                self.assertEqual(len(triggers), 2)
                for trigger in triggers:
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
            self.assertEqual(len(soup.select('.shop-photo .blog-img-frame')), self.photo_count)
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
        self.assertTrue(wizard['translations']['cs']['description'].startswith(
            'Přebroušení nebo výroba nové hřídele pro Škodu 105-136 / Favorit / Felicie.'))
        self.assertNotIn('pro Škodu 105-136, Favorit nebo Felicie.',
                         wizard['translations']['cs']['description'])
        self.assertIn('vyráběna z plného kusu.', wizard['translations']['cs']['description'])
        self.assertNotIn('vyráběna z jednoho kusu.', wizard['translations']['cs']['description'])
        for lang, soup in self.pages():
            card = soup.find(id=wizard['id'])
            self.assertEqual(card['id'], wizard['id'])
            self.assertEqual(len(soup.select('form[data-wizard]')), 2)
            self.assertFalse(soup.select('#camshaft-regrind, #camshaft-new'))
            sections = card.find_all(recursive=False)
            self.assertEqual([node.name for node in sections], ['header', 'hr', 'div', 'form'])
            self.assertCountEqual([node.get_text() for node in card.select('.shop-description')],
                             wizard['translations'][lang]['description'].split('\n\n'))
            self.assertEqual(len(card.select('.shop-description')), 6)
            self.assertFalse(card.select('[data-quantity], [data-change], .shop-prices'))
            self.assertFalse(card.select('form form, form.terminal-form'))
            self.assertTrue(card.select_one('form[data-wizard][novalidate] button.btn-submit[type=submit]'))

    def test_camshaft_galleries_keep_all_zoomable_photos_for_progressive_enhancement(self):
        products = {product['id']: product for product in self.catalog['products'] if product.get('kind') == 'wizard'}
        expected = {
            'skoda-ohv-camshaft': [f'/assets/desktop/skoda-ohv-{index}.jpeg' for index in range(1, 5)],
            'taz-camshaft': [f'/assets/desktop/taz-{index:02d}.jpeg' for index in range(1, 4)],
        }
        expected_dimensions = {
            'skoda-ohv-camshaft': [(4000, 2252), (4000, 2252), (2252, 4000), (2252, 4000)],
            'taz-camshaft': [(4000, 2252), (4000, 2252), (4000, 2252)],
        }
        self.assertEqual(set(products), set(expected))
        for product_id, expected_paths in expected.items():
            product = products[product_id]
            images = product['images']
            self.assertEqual([image['src'] for image in images], expected_paths)
            self.assertEqual(product['image'], expected_paths[0])
            self.assertEqual([(image['width'], image['height']) for image in images],
                             expected_dimensions[product_id])
            for path in expected_paths:
                data = (ROOT / path.lstrip('/')).read_bytes()
                self.assertTrue(data.startswith(b'\xff\xd8'))
                self.assertTrue(data.endswith(b'\xff\xd9'))
        for lang, soup in self.pages():
            self.assertEqual(len(soup.select('.shop-photo-gallery')),
                             sum(len(product.get('images', [])) > 1 for product in self.catalog['products']))
            for product_id, expected_paths in expected.items():
                product = products[product_id]
                images = product['images']
                card = soup.find(id=product_id)
                gallery = card.select_one(':scope > .article-body > figure.shop-photo.shop-photo-gallery')
                self.assertIsNotNone(gallery)
                links = gallery.select(':scope > a.shop-photo-link')
                self.assertEqual(len(links), len(expected_paths))
                self.assertEqual([link['href'] for link in links], expected_paths)
                self.assertFalse(gallery.select('figcaption, .shop-description, form'))
                for index, (link, image) in enumerate(zip(links, images)):
                    photo = link.select_one(':scope > .blog-img-frame > .shop-photo-viewport > img.blog-img')
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
        self.assertEqual(rules['.shop-photo-thumbnail']['height'], '60px')
        self.assertEqual(rules['.shop-photo-thumbnail img'], {
            'width': '100%', 'height': '100%', 'object-fit': 'cover',
        })

    def test_taz_camshaft_uses_requested_name_and_separate_nitriding_bullet(self):
        product = next(product for product in self.catalog['products'] if product['id'] == 'taz-camshaft')
        self.assertEqual(product['translations']['cs']['name'], 'Vačková hřídel TAZ')
        self.assertEqual(product['translations']['cs']['description'].split('\n\n'), [
            'Přebroušení nebo výroba nové hřídele TAZ.',
            'Nové hřídele jsou vyráběny z plného kusu a jsou přímo určeny pro požární sport.',
            'K přebroušení dodejte čistou hřídel TAZ 1500 a bez opotřebení na vrcholu palců.',
            'Při velkém opotřebení je nutná nitridace – cena na dotaz.',
            'Součástí dodávky jsou montážní instrukce – doporučený stupeň komprese, ventilové vůle, časování.',
        ])
        for lang, soup in self.pages():
            card = soup.find(id=product['id'])
            self.assertEqual(card.select_one(':scope > header > h3').get_text(), product['translations'][lang]['name'])
            self.assertCountEqual([node.get_text() for node in card.select('.shop-description')],
                             product['translations'][lang]['description'].split('\n\n'))
            self.assertEqual(len(card.select('.shop-description')), 5)
            nitriding = card.select_one('[data-description-group="regrind"] > ul.tech-list > li.shop-description')
            self.assertIsNotNone(nitriding)
            self.assertEqual(nitriding.get_text(), product['translations'][lang]['description'].split('\n\n')[3])
            self.assertTrue(card.select_one('form[data-wizard="taz-camshaft"]'))

    def test_camshaft_description_groups_preserve_copy_and_group_the_matching_operations(self):
        expected_groups = {
            'skoda-ohv-camshaft': {'lead': [0], 'regrind': [1, 3], 'new': [2, 4], 'instructions': [5]},
            'taz-camshaft': {'lead': [0], 'regrind': [2, 3], 'new': [1], 'instructions': [4]},
        }
        for lang, soup in self.pages():
            for product in self.catalog['products']:
                if product['id'] not in expected_groups:
                    continue
                paragraphs = product['translations'][lang]['description'].split('\n\n')
                card = soup.find(id=product['id'])
                for kind, indices in expected_groups[product['id']].items():
                    section = card.select_one(f'[data-description-group="{kind}"]')
                    self.assertEqual([node.get_text() for node in section.select('.shop-description')],
                                     [paragraphs[index] for index in indices])
                    if kind in ('regrind', 'new'):
                        self.assertIn('tech-math-block', section['class'])
                        self.assertTrue(section.select_one('h4.equation-display'))
                    elif kind == 'lead':
                        self.assertIn('article-header', section.parent['class'])
                    elif kind == 'instructions':
                        self.assertTrue(section.select_one('ul.tech-list > li.shop-description'))
        layouts = [props for selector, props in css_rules(ROOT / 'shop.css') if selector == '.shop-description-layout']
        self.assertEqual([props['grid-template-columns'] for props in layouts],
                         ['repeat(2, minmax(0, 1fr))', 'minmax(0, 1fr)'])

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
        products = [product for product in self.catalog['products'] if product.get('kind') == 'wizard']
        self.assertEqual({product['id'] for product in products}, {'skoda-ohv-camshaft', 'taz-camshaft'})
        for product in products:
            wizard = product['wizard']
            with (ROOT / wizard['source']).open(newline='') as source:
                rows = list(csv.DictReader(source, delimiter=';'))
            self.assertEqual(len(rows), len(wizard['profiles']))
            for row, profile in zip(rows, wizard['profiles']):
                self.assertEqual(profile['duration'], row['duration'])
                self.assertEqual(profile['lift'], row['lift'])
                self.assertEqual(profile['price'], int(row['price'].replace(' Kč', '').replace(' ', '')))
                self.assertEqual(profile['translations']['cs'], row['description'])
                self.assertEqual(profile['manufacture'], 'new' if row['manufacture'] == 'výroba' else 'regrind')
        for lang, soup in self.pages():
            config = json.loads(soup.select_one('#shop-config').string)
            client_products = {product['id']: product for product in config['products']}
            for product in products:
                wizard = product['wizard']
                card = soup.find(id=product['id'])
                options = card.select('.shop-profile-option')
                self.assertEqual(len(options), len(wizard['profiles']))
                radios = card.select('input[type=radio][name=profile]')
                self.assertEqual(len(radios), len(wizard['profiles']))
                self.assertEqual(len({radio['name'] for radio in radios}), 1)
                clients = client_products[product['id']]['wizard']['profiles']
                for option, profile, client in zip(options, wizard['profiles'], clients):
                    self.assertEqual(option.input['value'], profile['id'])
                    self.assertFalse(option.input.has_attr('required'))
                    self.assertFalse(option.input.has_attr('checked'))
                    self.assertNotIn('validate-me', option.input.get('class', []))
                    self.assertFalse(option.input.has_attr('data-warning-id'))
                    self.assertFalse(card.select('[id$="-profile-warning"]'))
                    for value in (profile['duration'], profile['lift'], money(profile['price'], lang),
                                  profile['translations'][lang]):
                        self.assertIn(value, option.get_text())
                    self.assertEqual(client['price'], profile['price'])
                    self.assertEqual(client['description'], profile['translations'][lang])
                    self.assertNotIn('translations', client)

    def test_wizard_table_keeps_operation_and_description_in_first_column_with_rowspanned_specs(self):
        for lang, soup in self.pages():
            text = json.loads(soup.select_one('#shop-config').string)['text']
            for product in (product for product in self.catalog['products'] if product.get('kind') == 'wizard'):
              with self.subTest(lang=lang, product=product['id']):
                table = soup.select_one(f'#{product["id"]} form[data-wizard] > fieldset > table.shop-profile-table')
                self.assertIsNotNone(table)
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
                self.assertEqual(len(options), len(product['wizard']['profiles']))
                accessible_names = []
                for option, profile in zip(options, product['wizard']['profiles']):
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
                    self.assertEqual(len(described_by), 1)
                self.assertEqual(len(set(accessible_names)), len(product['wizard']['profiles']))
                self.assertFalse(table.select('.shop-profile-content, .shop-profile-stats'))

    def test_wizard_table_is_compact_and_wraps_without_stacking_columns(self):
        all_rules = list(css_rules(ROOT / 'shop.css'))
        rules = dict(all_rules)
        self.assertEqual(rules['.shop-profile-table']['width'], '100%')
        self.assertEqual(rules['.shop-profile-table']['table-layout'], 'fixed')
        self.assertEqual(rules['.shop-profile-table']['border-collapse'], 'collapse')
        self.assertEqual(rules['.shop-profile-table']['border'], '0')
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
            main = BeautifulSoup((ROOT / lang / 'index.html').read_text(), 'html.parser')
            config = json.loads(soup.select_one('#shop-config').string)
            forms = soup.select('form[data-wizard]')
            self.assertEqual(len(forms), 2)
            self.assertEqual(len({form['id'] for form in forms}), len(forms))
            for form in forms:
                source_product = next(product for product in self.catalog['products']
                                      if product['id'] == form['data-wizard'])
                expected_names = [field['id'] for field in source_product['wizard']['fields']]
                profile_fields = form.select_one('.shop-profile-table > tbody.shop-profile-fields[data-profile-fields][hidden]')
                self.assertIsNotNone(profile_fields)
                fields = profile_fields.select(':scope > tr.shop-engine-field input.validate-me[data-engine-field]')
                self.assertEqual([field['name'] for field in fields], expected_names)
                self.assertEqual(len(form.select('input[name=bore]')), 1)
                for field in fields:
                    self.assertTrue(field.has_attr('required'))
                    self.assertTrue(field.has_attr('disabled'))
                    row = field.find_parent('tr')
                    self.assertEqual(row.find_all(['th', 'td'], recursive=False)[0].name, 'th')
                    self.assertEqual(row.th['scope'], 'row')
                    self.assertEqual(row.td['colspan'], '3')
                    self.assertTrue(row.th.find('label', attrs={'for': field['id']}))
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
                if source_product['wizard']['bearings']:
                    self.assertTrue(bearing.has_attr('disabled'))
                    bearing_row = form.select_one('tbody[data-profile-fields] > tr[data-bearing-fields][hidden]')
                    self.assertIsNotNone(bearing_row)
                    self.assertEqual(bearing_row.th['scope'], 'row')
                    self.assertEqual(bearing_row.td['colspan'], '3')
                    self.assertEqual([option['value'] for option in bearing.select('option')], ['', 'small', 'large'])
                    self.assertIn('39-38,5-30', bearing.get_text())
                    self.assertIn('40,5-40-30', bearing.get_text())
                    self.assertFalse(bearing.has_attr('data-variant'))
                    self.assertTrue(form.find(id=bearing['data-warning-id']))
                else:
                    self.assertIsNone(bearing)
                    self.assertIsNone(form.select_one('[data-bearing-fields]'))
                self.assertFalse(form.select('.mandatory-note, [id$="-profile-title"]'))
                self.assertEqual(form.find(recursive=False).name, 'fieldset')
                self.assertFalse(form.fieldset.has_attr('aria-labelledby'))
                self.assertEqual(form.fieldset.legend.get_text(), config['text']['configure'])
                self.assertIn('shop-sr-only', form.fieldset.legend['class'])
                self.assertFalse(form.fieldset.has_attr('aria-describedby'))
                self.assertIs(profile_fields.parent, form.select_one('.shop-profile-table'))
                self.assertNotIn('Ø', form.get_text())
                if lang == 'cs':
                    labels = [form.find('label', attrs={'for': field['id']}).get_text() for field in fields]
                    expected_labels = {
                        'skoda-ohv-camshaft': [
                            'Typ motoru *', 'Vrtání (mm) *', 'Zdvih (mm) *',
                            'Převodový poměr vahadla *', 'Průměr talířku V ventilu (mm) *',
                            'Průměr talířku S ventilu (mm) *',
                        ],
                        'taz-camshaft': [
                            'Vrtání (mm) *', 'Zdvih (mm) *',
                            'Průměr talířku V ventilu (mm) *', 'Průměr talířku S ventilu (mm) *',
                        ],
                    }
                    self.assertEqual(labels, expected_labels[source_product['id']])
                    self.assertNotIn('* povinná pole', form.get_text())
                    self.assertNotIn('Provedení', form.get_text())
                if 'engineType' in expected_names:
                    self.assertEqual(form.select_one('[name=engineType] + .warning-msg').get_text(),
                                     main.select_one('[name=fullname] + .warning-msg').get_text())
                else:
                    self.assertFalse(form.select('[name=engineType], [name=rockerRatio]'))
                    self.assertEqual(source_product['wizard']['bearings'], [])

    def test_profile_table_starts_form_without_a_visible_inquiry_heading(self):
        for lang, soup in self.pages():
            for form in soup.select('form[data-wizard]'):
              with self.subTest(lang=lang, product=form['data-wizard']):
                text = json.loads(soup.select_one('#shop-config').string)['text']
                headings = form.select(':scope > h4.form-section-title')
                self.assertFalse(headings)
                self.assertIs(form.fieldset, form.find(recursive=False))
                self.assertFalse(form.fieldset.has_attr('aria-labelledby'))
                self.assertEqual(form.fieldset.legend.get_text(), text['configure'])
                self.assertIn('shop-sr-only', form.fieldset.legend['class'])
                self.assertTrue(form.fieldset.select_one('table.shop-profile-table'))
                field_group = form.fieldset.select_one('table > tbody.shop-profile-fields[data-profile-fields][hidden]')
                self.assertIsNotNone(field_group)
                self.assertFalse(form.select('.shop-engine-fields, .form-row'))
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
            for option in soup.select('form[data-wizard] .shop-profile-option'):
                label = manufacture if option.input['value'].startswith('new-') else config['text']['manufactureRegrind']
                self.assertEqual(option.select_one('.shop-profile-method').get_text(), label)

    def test_configurator_button_adds_the_item_to_the_order_in_every_locale(self):
        expected = {
            'cs': 'Přidat do objednávky', 'en': 'Add to order',
            'de': 'Zur Bestellung hinzufügen', 'fr': 'Ajouter à la commande',
            'it': 'Aggiungi all’ordine', 'es': 'Añadir al pedido',
            'pl': 'Dodaj do zamówienia', 'ru': 'Добавить к заказу',
            'ja': '注文に追加', 'zh': '添加到订单',
        }
        for lang, soup in self.pages():
            with self.subTest(lang=lang):
                config = json.loads(soup.select_one('#shop-config').string)
                buttons = soup.select('.shop-product button[type=submit]')
                self.assertEqual(config['text']['addConfigured'], expected[lang])
                self.assertEqual(len(buttons), len(self.catalog['products']))
                self.assertTrue(all(button.get_text() == expected[lang] for button in buttons))

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

    def test_catalog_and_cards_support_null_or_absent_images_without_a_fallback(self):
        self.assertNotIn('placeholderImage', self.catalog)
        page = BeautifulSoup((self.output / 'cs/shop.html').read_text(), 'html.parser')
        text = json.loads(page.select_one('#shop-config').string)['text']
        for missing_key in (False, True):
            catalog = json.loads(json.dumps(self.catalog))
            for product in catalog['products']:
                if missing_key:
                    product.pop('image', None)
                else:
                    product['image'] = None
                product.pop('images', None)
                product.pop('photoMaxHeight', None)
                product.pop('photoMaxWidth', None)
            with patch('build_shop.json.loads', return_value=catalog):
                self.assertEqual(load_catalog(), catalog)
            for product in catalog['products']:
                with self.subTest(product=product['id'], missing_key=missing_key):
                    card = BeautifulSoup(product_card(product, 'cs', text, 0), 'html.parser').article
                    self.assertIn('shop-no-photo', card['class'])
                    self.assertFalse(card.select('figure, img, .shop-photo-link, .tech-frame, figcaption'))
                    paragraphs = [p for p in product['translations']['cs']['description'].split('\n\n') if p.strip()]
                    has_content = len(paragraphs) > 1 or product['id'] == 'exhaust-headers'
                    self.assertEqual([node.name for node in card.find_all(recursive=False)],
                                     ['header', 'hr', *(['div'] if has_content else []), 'form'])
                    self.assertEqual('shop-no-description' in card['class'], not bool(paragraphs))


if __name__ == '__main__':
    unittest.main()
