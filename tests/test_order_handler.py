"""Real PHP validation + multipart HTTP requests, with SMTP replaced by a local recorder.

No production endpoint, SMTP connection, credentials or actual email is used.
PHP_BIN can specify PHP 7.4+ with fileinfo, mbstring, session and JSON extensions.
"""
import copy
import hashlib
import http.cookiejar
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from bs4 import BeautifulSoup

from build_shop import client_products, load_catalog

ROOT = Path(__file__).resolve().parents[1]
PHP = os.environ.get('PHP_BIN') or shutil.which('php') or '/opt/homebrew/opt/php@8.3/bin/php'
CATALOG = load_catalog()
PRODUCTS = client_products(CATALOG, 'cs')
VERSION = hashlib.sha256(json.dumps(PRODUCTS, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def order_post(items=None, **values):
    return {'fullName': 'Test Customer', 'company': 'Test Company', 'email': 'customer@example.test',
            'phone': '+420 604 123 456', 'street': 'Test Street 1', 'city': 'Test City', 'postcode': '123 45',
            'country': 'Test Country', 'notes': 'Test order only', 'deliveryMethod': 'postal', 'bot-field': '',
            'locale': 'cs', 'catalogVersion': VERSION, 'requestId': uuid.uuid4().hex,
            'items': json.dumps(items if items is not None else [{'id': 'ignition-coil', 'variant': 'contactless', 'quantity': 2}]), **values}


def camshaft(product_id='skoda-ohv-camshaft', profile=2):
    product = next(product for product in PRODUCTS if product['id'] == product_id)
    return {'id': product_id, 'variant': '', 'quantity': 1, 'lineId': uuid.uuid4().hex, 'configuration': {
        'profile': product['wizard']['profiles'][profile]['id'],
        'bearing': 'small' if product['wizard']['bearings'] and profile >= 2 else '',
        'values': {field['id']: 'Test Engine' if field['type'] == 'text' else '1.5' for field in product['wizard']['fields']}}}


@unittest.skipUnless(Path(PHP).is_file(), 'PHP CLI is required for order endpoint tests')
class OrderValidationTests(unittest.TestCase):
    def validate(self, post):
        code = """
require 'backend/order_mail.php';
$catalog = require 'backend/order_catalog.php';
try {
    $post = json_decode(stream_get_contents(STDIN), true, 32, JSON_THROW_ON_ERROR);
    $order = order_validate($post, $catalog);
    $localized = $catalog['locales'][$order['locale']];
    $customerOrder = order_validate($post, array_replace($catalog, $localized));
    $customer = order_email($customerOrder, $localized['text'], $post['requestId'],
        array_replace($localized['email'], ['lang' => $order['locale'], 'sourceLanguage' => '',
            'footer' => ORDER_COMPANY_FOOTER]));
    echo json_encode(['order' => $order, 'email' => order_email($order, $catalog['text'], $post['requestId']),
        'customer' => $customer], JSON_THROW_ON_ERROR);
} catch (OrderInputError $error) { echo json_encode(['error' => $error->errorCode]); }
"""
        result = subprocess.run([PHP, '-d', 'display_errors=stderr', '-r', code], input=json.dumps(post),
                                text=True, capture_output=True, cwd=ROOT, check=True)
        self.assertEqual(result.stderr, '')
        return json.loads(result.stdout)

    def test_server_prices_and_escaped_html(self):
        post = order_post([{'id': 'ignition-coil', 'variant': 'contactless', 'quantity': 2,
                            'price': 1, 'priceType': 'quote', 'name': 'FAKE PRODUCT'}],
                          fullName='Test <Customer> & Co', notes='<img src=x onerror=alert(1)>\nSecond line')
        result = self.validate(post)
        self.assertEqual(result['order']['subtotal'], 2200)
        html = result['email']['html']
        self.assertIn('Test &lt;Customer&gt; &amp; Co', html)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;<br', html)
        self.assertNotIn('<img', html)
        self.assertNotIn('FAKE PRODUCT', html)
        self.assertIn('2 200 Kč', html)
        self.assertIn('Zapalovací cívka / Pro bezkontaktní zapalování', html)
        self.assertIn('Test Street 1', result['email']['text'])
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;<br', result['customer']['html'])
        self.assertNotIn('<img', result['customer']['html'])
        self.assertNotIn('FAKE PRODUCT', result['customer']['html'])
        for recipient in ('email', 'customer'):
            for format in ('html', 'text'):
                self.assertIn('ID objednávky: ' + post['requestId'], result[recipient][format])
                self.assertNotIn('Reference:', result[recipient][format])

    def test_customer_recap_in_every_form_language_with_next_step_and_configurations(self):
        copy = json.loads((ROOT / 'shop/order-email-translations.json').read_text())
        translations = json.loads((ROOT / 'shop/translations.json').read_text())
        rows = [camshaft(), {'id': 'head-gasket', 'variant': 'custom', 'quantity': 1,
                            'parameters': {'spacing': '88-88-88', 'thickness': '1.5'}}]
        for lang in CATALOG['languages']:
            with self.subTest(locale=lang):
                post = order_post(rows, locale=lang)
                result = self.validate(post)
                recap = result['customer']
                for key in ('title', 'nextStep', 'intro', 'closing'):
                    self.assertIn(copy[lang][key], recap['text'])
                    self.assertIn(copy[lang][key], recap['html'])
                self.assertEqual(recap['subject'], copy[lang]['subject'])
                self.assertIn(f'<html lang="{lang}">', recap['html'])
                for text in (post['requestId'], 'Test Customer', 'Test Company', 'Test Street 1',
                             '123 45 Test City', 'Test Country', 'customer@example.test', '+420 604 123 456',
                             'Test order only', '88-88-88', '1.5', 'Test Engine',
                             translations[lang]['quote'], translations[lang]['quoteNotice']):
                    self.assertIn(text, recap['text'])
                localized = client_products(CATALOG, lang)
                self.assertIn(localized[0]['name'], recap['text'])
                self.assertIn(localized[0]['wizard']['profiles'][2]['description'], recap['text'])
                self.assertIn('Nová objednávka z webu', result['email']['text'])
                self.assertIn(' Kč' if lang == 'cs' else ' CZK', recap['text'])
                self.assertNotIn(translations[lang]['deliveryNotice'], recap['text'])
                self.assertNotIn(translations[lang]['deliveryNotice'], recap['html'])
                blocks = BeautifulSoup(recap['html'], 'html.parser').body.find_all(recursive=False)
                self.assertEqual([block.name for block in blocks[:3]], ['p', 'p', 'h1'])
                self.assertEqual(blocks[0].get_text(), copy[lang]['intro'])
                self.assertEqual(blocks[1].strong.get_text(), copy[lang]['nextStep'])
                self.assertIsNone(blocks[1].get('style'))  # Normal paragraph, not a warning box.
                self.assertTrue(recap['text'].startswith(copy[lang]['intro'] + '\n\n' + copy[lang]['nextStep'] + '\n\n'))
                footer = 'Petra Mücková s.r.o.\nIČ: 25393928\nFučíkova 1311, 742 58 Příbor\ninfo@petramuckova.cz\n+420 604 487 263'
                self.assertEqual(blocks[-1].get_text('\n', strip=True), footer)
                self.assertEqual(blocks[-2].get_text(), copy[lang]['closing'])
                self.assertIn('margin-top:24px', blocks[-2]['style'])
                self.assertTrue(recap['text'].endswith(footer))
                self.assertNotIn('IČ: 25393928', result['email']['text'])

    def test_customer_czech_copy_matches_requested_text_without_old_warning(self):
        recap = self.validate(order_post())['customer']
        for format in ('html', 'text'):
            self.assertIn('Děkujeme za Vaši objednávku.', recap[format])
            self.assertIn('Nyní prosím vyčkejte na naši odpověď, ve které si s Vámi objednávku potvrdíme a ověříme dostupnost zboží, zvolenou dopravu a konečnou cenu.', recap[format])
            self.assertIn('Potřebujete něco doplnit nebo změnit? Odpovězte na tento e-mail a uveďte referenci objednávky.', recap[format])
            self.assertNotIn('Toto je automatická rekapitulace', recap[format])
            self.assertNotIn('Níže zasíláme její rekapitulaci.', recap[format])
        self.assertNotIn('border-left:', recap['html'])

    def test_business_email_omits_delivery_and_nonbinding_notices_without_empty_paragraphs(self):
        text = json.loads((ROOT / 'shop/translations.json').read_text())['cs']
        for quoted in (False, True):
            post = order_post([{'id': 'copper-rings', 'variant': '', 'quantity': 1}] if quoted else None)
            result = self.validate(post)
            for format in ('html', 'text'):
                with self.subTest(quoted=quoted, format=format):
                    self.assertNotIn(text['deliveryNotice'], result['email'][format])
                    self.assertNotIn(text['confirmation'], result['email'][format])
                    self.assertEqual(text['quoteNotice'] in result['email'][format], quoted)
                    self.assertNotIn(text['deliveryNotice'], result['customer'][format])
                    self.assertIn('Nyní prosím vyčkejte na naši odpověď', result['customer'][format])
            self.assertNotIn('<p></p>', result['email']['html'])
            self.assertNotIn('<p style="font-size:13px;color:#666"></p>', result['email']['html'])

    def test_every_product_option_and_camshaft_profile(self):
        for product in PRODUCTS:
            if product.get('kind') == 'wizard':
                rows = [camshaft(product['id'], index) for index, _ in enumerate(product['wizard']['profiles'])]
            else:
                rows = [{'id': product['id'], 'quantity': 1, 'variant': variant.get('id', ''),
                         'parameters': {field['id']: '88-88-88' if field.get('type') == 'text' else '1.5'
                                        if field.get('type') == 'decimal' else '5000' for field in variant.get('fields', [])}}
                        for variant in product['variants'] or [{}]]
            for row in rows:
                with self.subTest(product=product['id'], option=row.get('variant') or row.get('configuration')):
                    result = self.validate(order_post([row]))
                    self.assertIn('order', result)
                    self.assertIn(product['name'], result['email']['text'])

    def test_nonfixed_items_are_excluded_and_custom_fields_are_preserved(self):
        result = self.validate(order_post([
            {'id': 'copper-rings', 'variant': '', 'quantity': 3},
            {'id': 'distributor-overhaul', 'variant': '', 'quantity': 2},
            {'id': 'head-gasket', 'variant': 'custom', 'quantity': 1, 'parameters': {'spacing': '88-88-88', 'thickness': '1,5'}},
            {'id': 'distributor-rotor', 'variant': 'custom', 'quantity': 1, 'parameters': {'min-rpm': '4800', 'max-rpm': '5100'}},
        ]))
        self.assertEqual(result['order']['subtotal'], 0)
        self.assertTrue(result['order']['quoted'])
        for text in ('Od 120 Kč', 'Cca 3 200 Kč', 'Cena na dotaz', '88-88-88', '1.5', '4800', '5100'):
            self.assertIn(text, result['email']['text'])

    def test_invalid_contacts_and_stale_catalog(self):
        for key in ('fullName', 'email', 'street', 'city', 'postcode', 'country'):
            with self.subTest(key=key):
                self.assertEqual(self.validate(order_post(**{key: ''}))['error'], 'invalid_order')
        for values in ({'email': 'invalid'}, {'email': 'x@example.test\r\nBcc:x@example.test'},
                       {'fullName': ['nested']}, {'fullName': 'x' * 121}, {'phone': 'abc'}, {'phone': '+' * 60},
                       {'deliveryMethod': 'pickup'}, {'locale': 'unknown'}, {'notes': 'x' * 1501}):
            self.assertEqual(self.validate(order_post(**values))['error'], 'invalid_order')
        self.assertEqual(self.validate(order_post(catalogVersion='old'))['error'], 'catalog_changed')
        self.assertIn('order', self.validate(order_post(company='', phone='', notes='')))

    def test_invalid_products_quantities_and_duplicate_limits(self):
        for items in ([], [{'id': 'unknown', 'quantity': 1}], [{'id': 'ignition-coil', 'variant': 'unknown', 'quantity': 1}],
                      [{'id': 'resonance-exhaust', 'quantity': q} for q in (0, 1.5)],
                      [{'id': 'resonance-exhaust', 'quantity': 9999}] * 2):
            self.assertEqual(self.validate(order_post(items))['error'], 'invalid_order')
        for quantity in (True, '1', 0, -1, 1.5, 10000):
            self.assertEqual(self.validate(order_post([{'id': 'resonance-exhaust', 'quantity': quantity}]))['error'], 'invalid_order')
        self.assertIn('order', self.validate(order_post([{'id': 'resonance-exhaust', 'quantity': 9999}])))
        for raw in ('null', '{}', '{broken', '[]'):
            post = order_post(); post['items'] = raw
            self.assertEqual(self.validate(post)['error'], 'invalid_order')

    def test_wizard_requirements_and_duplicate_ids(self):
        valid = camshaft()
        for change in ('profile', 'bearing', 'values'):
            invalid = copy.deepcopy(valid)
            invalid['configuration'].pop(change)
            self.assertEqual(self.validate(order_post([invalid]))['error'], 'invalid_order')
        for key in valid['configuration']['values']:
            invalid = copy.deepcopy(valid)
            invalid['configuration']['values'][key] = ''
            self.assertEqual(self.validate(order_post([invalid]))['error'], 'invalid_order')
        self.assertEqual(self.validate(order_post([valid, valid]))['error'], 'invalid_order')
        invalid = copy.deepcopy(valid); invalid['quantity'] = 2
        self.assertEqual(self.validate(order_post([invalid]))['error'], 'invalid_order')
        taz = camshaft('taz-camshaft')
        self.assertIn('order', self.validate(order_post([taz])))
        taz['configuration']['bearing'] = 'small'
        self.assertEqual(self.validate(order_post([taz]))['error'], 'invalid_order')

    def test_custom_parameter_validation(self):
        for thickness in ('0', '-1', 'Infinity', 'NaN', '1e999', '0x10', '1,2,3', [], ''):
            row = {'id': 'head-gasket', 'variant': 'custom', 'quantity': 1, 'parameters': {'spacing': '88-88-88', 'thickness': thickness}}
            self.assertEqual(self.validate(order_post([row]))['error'], 'invalid_order')
        for parameters in ({}, {'min-rpm': '1.5', 'max-rpm': '5100'}, {'min-rpm': '5200', 'max-rpm': '5100'}):
            row = {'id': 'distributor-rotor', 'variant': 'custom', 'quantity': 1, 'parameters': parameters}
            self.assertEqual(self.validate(order_post([row]))['error'], 'invalid_order')


@unittest.skipUnless(Path(PHP).is_file(), 'PHP CLI is required for order endpoint tests')
class OrderEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='muckova-order-http-')
        cls.root = Path(cls.temporary.name)
        cls.backend = cls.root / 'backend'; cls.backend.mkdir()
        for name in ('order_form_handler.php', 'order_mail.php', 'order_catalog.php'):
            shutil.copy2(ROOT / 'backend' / name, cls.backend / name)
        shutil.copytree(ROOT / 'tests/fixtures/phpmailer', cls.backend / 'lib/PHPMailer/src')
        cls.mail = cls.root / 'mail'; cls.mail.mkdir()
        cls.uploads = cls.root / 'uploads'; cls.uploads.mkdir()
        cls.sessions = cls.root / 'sessions'; cls.sessions.mkdir()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        cls.url = f'http://127.0.0.1:{port}/backend/order_form_handler.php'
        environment = {**os.environ, 'PETRAMUCKOVA_CZ_SMTP_PASSWORD': 'fake-test-password', 'ORDER_TEST_MAIL_DIRECTORY': str(cls.mail)}
        cls.log = (cls.root / 'server.log').open('w+')
        cls.server = subprocess.Popen([PHP, '-d', f'sys_temp_dir={cls.uploads}', '-d', f'upload_tmp_dir={cls.uploads}',
                                       '-d', f'session.save_path={cls.sessions}', '-d', 'upload_max_filesize=16M',
                                       '-d', 'post_max_size=16M', '-S', f'127.0.0.1:{port}', '-t', str(cls.root)],
                                      env=environment, stdout=cls.log, stderr=cls.log)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.url, timeout=1).close(); break
            except OSError:
                if cls.server.poll() is not None: raise RuntimeError('PHP test server failed to start')
                time.sleep(0.05)
        else: raise RuntimeError('PHP test server did not become ready')

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate(); cls.server.wait(timeout=5)
        cls.log.close(); cls.temporary.cleanup()

    def setUp(self):
        for path in self.mail.iterdir(): path.unlink()
        for directory in self.uploads.glob('muckova-orders-*'): shutil.rmtree(directory)
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        with self.client.open(self.url) as response:
            self.assertIn('HttpOnly', response.headers['Set-Cookie'])
            self.assertIn('SameSite=Strict', response.headers['Set-Cookie'])
            self.token = json.load(response)['token']

    def send(self, post=None, attachments=(), **headers):
        post = order_post() if post is None else dict(post)
        post.setdefault('csrfToken', self.token)
        boundary = uuid.uuid4().hex
        pieces = []
        for key, value in post.items():
            pieces.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        for filename, data, mime in attachments:
            pieces.append(f'--{boundary}\r\nContent-Disposition: form-data; name="attachment[]"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode() + data + b'\r\n')
        pieces.append(f'--{boundary}--\r\n'.encode())
        request = urllib.request.Request(self.url, data=b''.join(pieces), headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}', **headers})
        try: response = self.client.open(request, timeout=10)
        except urllib.error.HTTPError as error: response = error
        with response:
            self.assertEqual(response.headers.get_content_type(), 'application/json')
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            return response.status, json.load(response)

    def messages(self, kind=None):
        messages = [json.loads(path.read_text()) for path in self.mail.glob('*.json')]
        return messages if kind is None else [message for message in messages
            if message['messageId'].startswith('<order-recap-') == (kind == 'customer')]

    def test_real_post_multipart_and_reply_to(self):
        code, body = self.send(attachments=[('instructions.txt', b'Test attachment', 'text/plain')])
        self.assertEqual(code, 200); self.assertEqual(body['status'], 'success')
        self.assertEqual(body['customerEmail'], 'sent')
        self.assertEqual(len(self.messages()), 2)
        message, = self.messages('business')
        self.assertEqual(message['from'][0], 'info@petramuckova.cz')
        self.assertEqual(message['to'][0], 'info@petramuckova.cz')
        self.assertEqual(message['replyTo'][0], 'customer@example.test')
        self.assertEqual(message['attachments'], [{'name': 'instructions.txt', 'mime': 'text/plain', 'size': 15}])
        self.assertIn('2 200 Kč', message['html'])
        self.assertIn('Test Customer', message['text'])
        customer, = self.messages('customer')
        self.assertEqual(customer['from'][0], 'info@petramuckova.cz')
        self.assertEqual(customer['to'], ['customer@example.test', 'Test Customer'])
        self.assertEqual(customer['replyTo'], ['info@petramuckova.cz', 'Petra Mücková'])
        self.assertEqual(customer['attachments'], [])
        self.assertNotEqual(customer['messageId'], message['messageId'])
        self.assertIn(body['reference'], customer['messageId'])
        self.assertIn('2 200 Kč', customer['html'])
        self.assertIn('<p><strong>Nyní prosím vyčkejte na naši odpověď', customer['html'])
        self.assertIn('Fučíkova 1311, 742 58 Příbor', customer['text'])
        self.assertEqual(customer['headers'], {'Auto-Submitted': 'auto-generated', 'X-Auto-Response-Suppress': 'All'})
        self.assertFalse(list(self.uploads.glob('php*')))
        for session in self.sessions.glob('*'):
            self.assertNotIn('customer@example.test', session.read_text())

    def test_retries_are_idempotent_and_changed_payload_is_rejected(self):
        post = order_post()
        self.assertEqual(self.send(post)[0], 200)
        self.assertEqual(self.send(post)[0], 200)
        self.assertEqual(len(self.messages()), 2)
        post['notes'] = 'Different order'
        self.assertEqual(self.send(post)[0], 400)
        self.assertEqual(len(self.messages()), 2)

    def test_csrf_origin_honeypot_and_methods(self):
        self.assertEqual(self.send(order_post(csrfToken='wrong'))[0], 403)
        self.assertEqual(self.send(Origin='https://example.invalid')[0], 403)
        self.assertEqual(self.send(order_post(**{'bot-field': 'bot'}))[0], 400)
        request = urllib.request.Request(self.url, method='PUT')
        with self.assertRaises(urllib.error.HTTPError) as failure: self.client.open(request)
        self.assertEqual(failure.exception.code, 405)
        failure.exception.close()
        self.assertEqual(self.messages(), [])

    def test_attachments_are_optional_and_mime_is_not_trusted(self):
        self.assertEqual(self.send()[0], 200)
        for name, data, mime in [('image.jpg', b'Not an image', 'image/jpeg'), ('script.php', b'<?php echo 1;', 'text/plain'),
                                  ('empty.txt', b'', 'text/plain')]:
            self.assertEqual(self.send(attachments=[(name, data, mime)])[1]['code'], 'invalid_attachment')
        self.assertEqual(len(self.messages()), 2)

    def test_three_files_and_combined_size_limit(self):
        attachments = [(f'file{i}.txt', b'Test file', 'text/plain') for i in range(3)]
        self.assertEqual(self.send(attachments=attachments)[0], 200)
        self.assertEqual(self.send(attachments=attachments + attachments[:1])[1]['code'], 'invalid_attachment')
        self.assertEqual(self.send(attachments=[('a.txt', b'a' * (5 * 1024 * 1024), 'text/plain'),
                                               ('b.txt', b'b' * (4 * 1024 * 1024), 'text/plain')])[0], 413)
        self.assertEqual(len(self.messages()), 2)

    def test_smtp_failure_is_generic_and_can_be_retried(self):
        (self.mail / 'fail').touch()
        post = order_post()
        self.assertEqual(self.send(post), (503, {'status': 'error', 'code': 'send_failed'}))
        self.assertEqual(self.messages(), [])
        (self.mail / 'fail').unlink()
        self.assertEqual(self.send(post)[0], 200)
        self.assertEqual(len(self.messages()), 2)

    def test_customer_failure_accepts_order_and_retries_only_missing_recap(self):
        marker = self.mail / 'fail-customer'; marker.touch()
        post = order_post()
        files = [('instructions.txt', b'Test attachment', 'text/plain')]
        expected = (200, {'status': 'success', 'reference': post['requestId'], 'customerEmail': 'failed'})
        self.assertEqual(self.send(post, attachments=files), expected)
        self.assertEqual(self.send(post, attachments=files), expected)
        self.assertEqual(len(self.messages('business')), 1)
        self.assertEqual(self.messages('customer'), [])
        self.assertEqual(self.send({**post, 'email': 'different@example.test'}, attachments=files)[0], 400)
        marker.unlink()
        self.assertEqual(self.send(post, attachments=files)[1]['customerEmail'], 'sent')
        self.assertEqual(self.send(post, attachments=files)[1]['customerEmail'], 'sent')
        self.assertEqual(len(self.messages('business')), 1)
        customer, = self.messages('customer')
        self.assertEqual(customer['attachments'], [])

    def test_customer_failure_retries_are_rate_limited_without_rejecting_received_order(self):
        (self.mail / 'fail-customer').touch()
        post = order_post()
        for _ in range(6):
            self.assertEqual(self.send(post)[1]['customerEmail'], 'failed')
        self.assertEqual(len(self.messages('business')), 1)
        self.assertEqual(self.messages('customer'), [])
        # One business send and five customer attempts; the sixth request is throttled.
        self.assertEqual(len((self.mail / 'attempts').read_text().splitlines()), 6)

    def test_pending_recap_with_changed_catalog_does_not_resend_or_reject_received_order(self):
        (self.mail / 'fail-customer').touch()
        post = order_post()
        self.assertEqual(self.send(post)[1]['customerEmail'], 'failed')
        catalog_path = self.backend / 'order_catalog.php'
        original = catalog_path.read_text()
        try:
            catalog_path.write_text(original.replace(VERSION, '0' * 64))
            self.assertEqual(self.send(post), (200, {'status': 'success', 'reference': post['requestId'], 'customerEmail': 'failed'}))
            self.assertEqual(len(self.messages()), 1)
        finally:
            catalog_path.write_text(original)

    def test_english_customer_gets_localized_recap_but_business_mail_stays_czech(self):
        self.assertEqual(self.send(order_post(locale='en'))[1]['customerEmail'], 'sent')
        customer, = self.messages('customer')
        business, = self.messages('business')
        self.assertIn('Ignition coil', customer['html'])
        self.assertIn('Please now wait for our reply, in which we will confirm your order with you', customer['text'])
        self.assertIn('2 200 CZK', customer['text'])
        self.assertIn('Zapalovací cívka', business['html'])

    def test_rate_limit_applies_but_a_successful_retry_does_not_send_twice(self):
        posts = [order_post() for _ in range(6)]
        for post in posts[:5]: self.assertEqual(self.send(post)[0], 200)
        self.assertEqual(self.send(posts[5]), (429, {'status': 'error', 'code': 'rate_limited'}))
        self.assertEqual(self.send(posts[0])[0], 200)
        self.assertEqual(len(self.messages()), 10)

    def test_invalid_and_stale_orders_are_not_sent(self):
        self.assertEqual(self.send(order_post(email='not-an-email'))[0], 400)
        self.assertEqual(self.send(order_post(catalogVersion='outdated'))[0], 409)
        self.assertEqual(self.messages(), [])


if __name__ == '__main__':
    unittest.main()
