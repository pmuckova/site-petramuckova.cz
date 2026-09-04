"""Render the static catalogue; edit shop/catalog.json, not generated shop.html.

Run with the project's .venv: .venv/bin/python build_shop.py
"""

import argparse
import hashlib
import html
import json
import re
from pathlib import Path
from string import Template

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
BASE_URL = 'https://www.petramuckova.cz'


def escape(value):
    return html.escape(str(value), quote=True)


def validate_image(image, label, root):
    if (not isinstance(image, str) or not image.startswith('/assets/')
            or '..' in image.split('/') or not (root / image.lstrip('/')).is_file()):
        raise ValueError(f'Missing or unsafe image: {label}')


def load_catalog(root=ROOT):
    data = json.loads((root / 'shop/catalog.json').read_text(encoding='utf-8'))
    validate_image(data.get('placeholderImage'), 'catalogue placeholder', root)
    ids = set()
    for product in data['products']:
        product_id = product['id']
        if not re.fullmatch(r'[a-z0-9-]+', product_id) or product_id in ids:
            raise ValueError(f'Invalid or duplicate product ID: {product_id}')
        ids.add(product_id)
        if product['priceType'] not in ('fixed', 'from', 'quote'):
            raise ValueError(f'Invalid price type: {product_id}')
        price = product['price']
        if product['priceType'] == 'quote':
            if price is not None:
                raise ValueError(f'Quote-only item must have a null price: {product_id}')
        elif type(price) is not int or price <= 0:
            raise ValueError(f'Price must be positive whole CZK: {product_id}')
        variant_ids = [variant['id'] for variant in product['variants']]
        if len(set(variant_ids)) != len(variant_ids) or any(
            not re.fullmatch(r'[a-z0-9-]+', variant_id) for variant_id in variant_ids
        ):
            raise ValueError(f'Invalid variants: {product_id}')
        image = product.get('image')
        if image:
            validate_image(image, product_id, root)
        for lang in data['languages']:
            if not product['translations'].get(lang, {}).get('name'):
                raise ValueError(f'Missing {lang} name: {product_id}')
    return data


def money(value, lang):
    return f'{value:,}'.replace(',', '\u00a0') + (' Kč' if lang == 'cs' else ' CZK')


def product_card(product, lang, t, position, placeholder_image):
    text = product['translations'][lang]
    product_id = escape(product['id'])
    name = escape(text['name'])
    description = escape(text['description'])
    if product['priceType'] == 'quote':
        price = t['quote']
    else:
        price = money(product['price'], lang)
        if product['priceType'] == 'from':
            price = t['from'] + ' ' + price
    is_placeholder = not product.get('image')
    image = product.get('image') or placeholder_image
    alt = escape(t['noPhoto']) if is_placeholder else name
    placeholder_attr = ' data-placeholder="true"' if is_placeholder else ''
    photo = f'''<figure class="shop-photo{' shop-photo-placeholder' if is_placeholder else ''}">
      <a class="shop-photo-link" href="{escape(image)}" aria-haspopup="dialog" aria-label="{escape(t['enlargePhoto'])}: {name}">
        <span class="tech-frame">
          <img src="{escape(image)}" alt="{alt}" width="640" height="480" loading="{'eager' if position < 2 else 'lazy'}" decoding="async"{placeholder_attr}>
        </span>
      </a>
    </figure>'''
    variant = ''
    if product['variants']:
        options = ''.join(f'<option value="{escape(v["id"])}">{escape(v["label"])}</option>' for v in product['variants'])
        variant = f'''<div class="form-group shop-variant">
          <label id="label-variant-{product_id}" for="variant-{product_id}">{escape(t['variant'])}</label>
          <select class="custom-select" id="variant-{product_id}" data-variant><option value="">{escape(t['variantChoose'])}</option>{options}</select>
        </div>'''
    dealer = ''
    if product.get('dealerPrice'):
        dealer = f'''<div class="shop-price-row"><dt>{escape(t['dealer'])}</dt><dd>{escape(money(product['dealerPrice'], lang))}</dd></div>
          <div class="shop-price-row shop-dealer-minimum"><dt>{escape(t['dealerMinimum'])}</dt><dd>{product['dealerMinimum']}</dd></div>'''
    article_link = f'<a href="/{lang}/blog#post-2-title">{escape(t["blog"])}: TAZ 1.43 / PS12 ↗</a>' if product['id'] == 'exhaust-headers' else ''
    card = f'''<article class="blog-card shop-product" id="{product_id}" data-product="{product_id}" aria-labelledby="name-{product_id}">
      <h3 class="shop-product-title" id="name-{product_id}">{name}</h3>
      {photo}
      <div class="shop-product-content">
        <div class="shop-product-body">
          <p class="shop-description">{description}</p>
          {article_link}
        </div>
        <dl class="shop-prices">
          <div class="shop-price-row"><dt>{escape(t['retail'])}</dt><dd>{escape(price)}</dd></div>
          {dealer}
        </dl>
        <div class="shop-product-order">
          {variant}
          <label class="shop-quantity-label" for="quantity-{product_id}">{escape(t['quantity'])}<span class="shop-sr-only">: {name}</span></label>
          <div class="shop-quantity" role="group" aria-label="{escape(t['quantity'])}: {name}">
            <button type="button" data-change="-1" aria-label="{escape(t['decrease'])}: {name}" disabled>−</button>
            <input id="quantity-{product_id}" data-quantity type="number" min="0" max="9999" step="1" value="0" inputmode="numeric" disabled>
            <button type="button" data-change="1" aria-label="{escape(t['increase'])}: {name}" disabled>+</button>
          </div>
        </div>
      </div>
    </article>'''
    return '\n'.join(line.rstrip() for line in card.splitlines())


def asset_version(root, filename):
    return hashlib.sha256((root / filename).read_bytes()).hexdigest()[:12]


def main_form_copy(root, lang):
    """Use the main form's translated section title and inline warnings verbatim."""
    page = BeautifulSoup((root / lang / 'index.html').read_text(encoding='utf-8'), 'html.parser')
    form = page.select_one('#inquiryForm')
    return {
        'contactHeading': form.select_one('h4.form-section-title').get_text(strip=True),
        'requiredWarning': form.select_one('[name="fullname"] + .warning-msg').get_text(strip=True),
        'emailWarning': form.select_one('[name="email"] + .warning-msg').get_text(strip=True),
        'phoneWarning': form.select_one('[name="phone"] + .warning-msg').get_text(strip=True),
    }


def site_navigation(root, lang):
    """Reuse the localized blog chrome instead of maintaining a second header."""
    blog = BeautifulSoup((root / lang / 'blog.html').read_text(encoding='utf-8'), 'html.parser')
    mobile = blog.body.find('div', class_='view-mobile', recursive=False)
    desktop = blog.body.find('div', class_='view-desktop', recursive=False)
    footer = blog.body.find('footer', recursive=False)
    mobile_languages = blog.select_one('.copyright-bar > .view-mobile')
    if any(node is None for node in (mobile, desktop, footer, mobile_languages)):
        raise ValueError(f'Missing blog navigation: {lang}')

    for link in desktop.select('#navLinks > li > a'):
        classes = [name for name in link.get('class', []) if name != 'active-link']
        if link.get('href') == f'/{lang}/shop':
            classes.append('active-link')
            link['aria-current'] = 'page'
        if classes:
            link['class'] = classes
        else:
            link.attrs.pop('class', None)
    for link in mobile.select('.mobile-menu-item'):
        href = link.get('href', '')
        if href.startswith('#post-'):
            link['href'] = f'/{lang}/blog{href}'
            link.attrs.pop('data-target', None)
        elif href == f'/{lang}/shop':
            link['aria-current'] = 'page'
            link['class'].append('is-active')

    for menu in (desktop.select_one('.lang-menu'), mobile_languages):
        for link in menu.select('a[href]'):
            code = link['href'].strip('/').split('/')[0]
            link['href'] = f'/{code}/shop'
            link['hreflang'] = code
            link['lang'] = code
            if code == lang:
                link['aria-current'] = 'page'

    # Preserve the blog's appearance while making its menu triggers keyboard-accessible.
    for trigger, overlay, label in (
        (mobile.select_one('.mobile-menu-trigger'), 'mobile-menu-overlay', 'Menu'),
        (mobile_languages.select_one('.copy-right'), 'mobile-langchooser-overlay', 'Language'),
    ):
        trigger.name = 'button'
        trigger['type'] = 'button'
        trigger['aria-label'] = label
        trigger['aria-controls'] = overlay
        trigger['aria-expanded'] = 'false'
        panel = blog.find(id=overlay)
        panel['hidden'] = ''
        panel['role'] = 'dialog'
        panel['aria-modal'] = 'true'
        panel['aria-label'] = label
    desktop.select_one('.lang-toggle')['tabindex'] = '0'
    mobile.select_one('.hero-visual-mobile')['class'].append('loaded')
    return str(mobile) + '\n' + str(desktop), str(footer)


def build_shop(root=ROOT, languages=None, output_root=None):
    data = load_catalog(root)
    translations = json.loads((root / 'shop/translations.json').read_text(encoding='utf-8'))
    template = Template((root / 'shop/page.html').read_text(encoding='utf-8'))
    output_root = output_root or root
    languages = languages or data['languages']
    for lang in languages:
        t = translations[lang]
        if set(t) != set(translations['en']):
            raise ValueError(f'Incomplete UI translation: {lang}')
        copy = data['copy'][lang]
        header, footer = site_navigation(root, lang)
        client_products = [{
            'id': p['id'], 'name': p['translations'][lang]['name'],
            'price': p['price'], 'priceType': p['priceType'], 'variants': p['variants'],
        } for p in data['products']]
        config = json.dumps({'products': client_products, 'currency': data['currency'],
                             'locale': lang, 'email': data['orderEmail'], 'text': t}, ensure_ascii=False)
        config = config.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
        values = {key: escape(value) for key, value in t.items()}
        values.update({key: escape(value) for key, value in main_form_copy(root, lang).items()})
        values.update({
            'lang': lang, 'canonical': f'{BASE_URL}/{lang}/shop',
            'intro': escape(copy['intro']), 'trade': escape(copy['trade']),
            'email_address': escape(data['orderEmail']),
            'alternates': '\n'.join(f'<link rel="alternate" hreflang="{code}" href="{BASE_URL}/{code}/shop">' for code in data['languages'])
                          + f'\n<link rel="alternate" hreflang="x-default" href="{BASE_URL}/cs/shop">',
            'header': header, 'footer': footer,
            'products': '\n'.join(product_card(p, lang, t, i, data['placeholderImage']) for i, p in enumerate(data['products'])),
            'notes_html': ''.join(f'<p>{escape(note)}</p>' for note in copy['notes']),
            'config': config,
            'css_version': asset_version(root, 'shop.css'), 'js_version': asset_version(root, 'shop.js'),
            'blog_css_version': asset_version(root, 'blog.css'),
            'form_js_version': asset_version(root, 'form.js'),
        })
        target = output_root / lang / 'shop.html'
        target.parent.mkdir(parents=True, exist_ok=True)
        rendered = template.substitute(values)
        if not target.exists() or target.read_text(encoding='utf-8') != rendered:
            target.write_text(rendered, encoding='utf-8')
        print(f'Catalogue: {lang}/shop.html ({len(data["products"])} products)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language', action='append', help='Render only this language (repeatable).')
    args = parser.parse_args()
    build_shop(languages=args.language)
