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
        if product.get('kind', 'standard') not in ('standard', 'wizard'):
            raise ValueError(f'Invalid product kind: {product_id}')
        wizard = product.get('kind') == 'wizard'
        if product['priceType'] not in (('configured',) if wizard else ('fixed', 'from', 'approx', 'quote')):
            raise ValueError(f'Invalid price type: {product_id}')
        price = product['price']
        if product['priceType'] in ('quote', 'configured'):
            if price is not None:
                raise ValueError(f'Quote-only or configured item must have a null base price: {product_id}')
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
        if 'images' in product:
            validate_gallery(product, data['languages'], root)
        if wizard:
            validate_wizard(product, data['languages'])
        else:
            for variant in product['variants']:
                variant_price = variant.get('price', price)
                variant_price_type = variant.get('priceType', product['priceType'])
                if (variant_price_type not in ('fixed', 'from', 'approx', 'quote')
                        or (variant_price_type == 'quote' and variant_price is not None)
                        or (variant_price_type != 'quote' and (type(variant_price) is not int or variant_price <= 0))):
                    raise ValueError(f'Invalid variant price: {product_id}')
                if 'translations' in variant and any(not variant['translations'].get(lang) for lang in data['languages']):
                    raise ValueError(f'Missing variant translation: {product_id}')
                if 'descriptions' in variant and any(not variant['descriptions'].get(lang) for lang in data['languages']):
                    raise ValueError(f'Missing variant description: {product_id}')
                fields = variant.get('fields', [])
                field_ids = [field['id'] for field in fields]
                if len(set(field_ids)) != len(field_ids) or any(not re.fullmatch(r'[a-z][a-z0-9-]*', key) for key in field_ids):
                    raise ValueError(f'Invalid option field IDs: {product_id}')
                for field in fields:
                    field_type = field.get('type', 'integer')
                    minimum = next((other for other in fields if other['id'] == field.get('minimumField')), None)
                    if (field.get('labelKey') not in ('minRpm', 'maxRpm', 'gasketSpacing', 'gasketThickness')
                            or field_type not in ('integer', 'decimal', 'text')
                            or (field_type == 'text' and (type(field.get('maxLength')) is not int or not 1 <= field['maxLength'] <= 200))
                            or ('minimumField' in field and (not minimum or minimum is field
                                or field_type == 'text' or minimum.get('type', 'integer') == 'text'))):
                        raise ValueError(f'Invalid option field: {product_id}')
            if 'options' in product:
                option_ids = [option['id'] for option in product['options']]
                covered = [variant for option in product['options'] for variant in option['variantIds']]
                if (not option_ids or len(set(option_ids)) != len(option_ids)
                        or any(not re.fullmatch(r'[a-z0-9-]+', value) for value in option_ids)
                        or sorted(covered) != sorted(variant_ids)):
                    raise ValueError(f'Invalid option groups: {product_id}')
                for option in product['options']:
                    if not option['variantIds'] or any(not option['translations'].get(lang, {}).get('name') for lang in data['languages']):
                        raise ValueError(f'Incomplete option group: {product_id}')
                    prices = {(variant.get('price', price), variant.get('priceType', product['priceType']))
                              for variant in product['variants'] if variant['id'] in option['variantIds']}
                    if len(prices) != 1:
                        raise ValueError(f'Option group must have one displayed price: {product_id}')
        for lang in data['languages']:
            if not product['translations'].get(lang, {}).get('name'):
                raise ValueError(f'Missing {lang} name: {product_id}')
        if 'descriptionGroups' in product:
            groups = product['descriptionGroups']
            if (not isinstance(groups, list) or any(not isinstance(group, dict) for group in groups)
                    or [group.get('kind') for group in groups] != ['lead', 'regrind', 'new', 'instructions']):
                raise ValueError(f'Invalid description groups: {product_id}')
            if any(not isinstance(group.get('paragraphs'), list) or not group['paragraphs'] for group in groups):
                raise ValueError(f'Description groups must contain paragraph indices: {product_id}')
            indices = [index for group in groups for index in group['paragraphs']]
            for lang in data['languages']:
                paragraphs = product['translations'][lang]['description'].split('\n\n')
                if any(type(index) is not int for index in indices) or sorted(indices) != list(range(len(paragraphs))):
                    raise ValueError(f'Description groups must include every paragraph exactly once: {product_id}/{lang}')
    legacy_ids = set()
    for product in data['products']:
        for legacy in product.get('legacyItems', []):
            if (legacy['id'] in ids or legacy['id'] in legacy_ids or legacy['variant'] != ''
                    or legacy['targetVariant'] not in [variant['id'] for variant in product['variants']]):
                raise ValueError(f'Invalid legacy product mapping: {product["id"]}')
            legacy_ids.add(legacy['id'])
    return data


def validate_gallery(product, languages, root):
    images = product['images']
    if not isinstance(images, list) or not images:
        raise ValueError(f'Product gallery must contain images: {product["id"]}')
    for image in images:
        if not isinstance(image, dict):
            raise ValueError('Gallery images must contain a path, dimensions and translated alt text')
        validate_image(image.get('src'), product['id'], root)
        if any(type(image.get(key)) is not int or image[key] <= 0 for key in ('width', 'height')):
            raise ValueError('Gallery image dimensions must be positive integers')
        alt = image.get('alt')
        if not isinstance(alt, dict) or any(not isinstance(alt.get(lang), str) or not alt[lang].strip() for lang in languages):
            raise ValueError('Missing translated gallery image alt text')
    if product.get('image') != images[0]['src']:
        raise ValueError('The primary product image must be the first gallery image')


def validate_wizard(product, languages):
    wizard = product['wizard']
    if product['variants']:
        raise ValueError('Wizard choices must not also be quantity variants')
    for group in ('profiles', 'fields'):
        ids = [item['id'] for item in wizard[group]]
        if not ids or len(ids) != len(set(ids)) or any(
                not re.fullmatch(r'[a-zA-Z0-9-]+', item_id) for item_id in ids):
            raise ValueError(f'Invalid wizard {group}: {product["id"]}')
    bearing_ids = [item['id'] for item in wizard['bearings']]
    if len(bearing_ids) != len(set(bearing_ids)) or any(
            not re.fullmatch(r'[a-zA-Z0-9-]+', item_id) for item_id in bearing_ids):
        raise ValueError(f'Invalid wizard bearings: {product["id"]}')
    for profile in wizard['profiles']:
        if profile['manufacture'] not in ('regrind', 'new'):
            raise ValueError('Invalid manufacturing method')
        if type(profile['price']) is not int or profile['price'] <= 0:
            raise ValueError('Profile price must be positive whole CZK')
        if not profile['duration'] or not profile['lift']:
            raise ValueError('Missing profile specification')
        if any(not profile['translations'].get(lang) for lang in languages):
            raise ValueError('Missing translated profile description')
    for field in wizard['fields']:
        if field['type'] not in ('text', 'number') or type(field['required']) is not bool:
            raise ValueError('Invalid wizard field')
        if field['type'] == 'text' and not 1 <= field['maxLength'] <= 200:
            raise ValueError('Invalid wizard text length')


def money(value, lang):
    return f'{value:,}'.replace(',', '\u00a0') + (' Kč' if lang == 'cs' else ' CZK')


def localized_variants(product, lang):
    return [{key: value for key, value in variant.items() if key not in ('translations', 'descriptions')}
            | {'label': variant.get('translations', {}).get(lang, variant['label'])}
            | ({'description': variant['descriptions'][lang]} if 'descriptions' in variant else {})
            for variant in product['variants']]


def standard_options(product, lang):
    variants = localized_variants(product, lang)
    if 'options' in product:
        return [{
            'id': option['id'], 'name': option['translations'][lang]['name'],
            'description': option['translations'][lang].get('description', ''),
            'price': next(variant for variant in variants if variant['id'] in option['variantIds']).get('price', product['price']),
            'priceType': next(variant for variant in variants if variant['id'] in option['variantIds']).get('priceType', product['priceType']),
            'variants': [variant for variant in variants if variant['id'] in option['variantIds']],
        } for option in product['options']]
    return [{
        'id': variant['id'] if variant else 'standard',
        'name': variant['label'] if variant else product['translations'][lang].get('optionName', product['translations'][lang]['name']),
        'description': variant.get('description', '') if variant else product['translations'][lang].get('optionDescription', ''),
        'price': variant.get('price', product['price']) if variant else product['price'],
        'priceType': variant.get('priceType', product['priceType']) if variant else product['priceType'],
        'variants': [variant] if variant else [],
    } for variant in (variants or [None])]


def order_item_form(product, lang, t):
    prefix = escape(product['id'])
    name = escape(product['translations'][lang]['name'])
    options = standard_options(product, lang)
    rows, variant_rows, parameter_rows = [], [], []
    for option in options:
        key = escape(option['id'])
        option_id = f'{prefix}-option-{key}'
        price = t['quote'] if option['priceType'] == 'quote' else money(option['price'], lang)
        if option['priceType'] in ('from', 'approx'):
            price = t[option['priceType']] + ' ' + price
        description = option['description']
        rows.append(f'''<tbody class="shop-profile-option">
          <tr>
            <td><label class="shop-profile-radio-label" for="{option_id}">
              <input type="radio" name="option" value="{key}" id="{option_id}" aria-labelledby="{option_id}-name {prefix}-price-heading {option_id}-price"{' aria-describedby="' + option_id + '-description"' if description else ''}>
              <span id="{option_id}-name" class="shop-profile-method">{escape(option['name'])}</span>
            </label></td>
            <td class="shop-profile-price"{' rowspan="2"' if description else ''}><label for="{option_id}"><span id="{option_id}-price" class="shop-profile-value">{escape(price)}</span></label></td>
          </tr>
          {'<tr><td><label class="shop-profile-description" id="' + option_id + '-description" for="' + option_id + '">' + escape(description) + '</label></td></tr>' if description else ''}
        </tbody>''')
        if len(option['variants']) > 1:
            select_id = f'{prefix}-variant-{key}'
            choices = ''.join(f'<option value="{escape(variant["id"])}">{escape(variant["label"])}</option>' for variant in option['variants'])
            label = t['bore'] + ' (mm)' if product['id'] == 'head-gasket' else t['variant']
            variant_rows.append(f'''<tr class="shop-profile-field" data-order-variant-fields="{key}" hidden>
              <th scope="row"><label id="label-{select_id}" for="{select_id}">{escape(label)} *</label></th>
              <td><div class="form-group shop-variant">
                <select id="{select_id}" name="variant-{key}" class="custom-select validate-me" data-order-variant data-warning-id="{select_id}-warning" required disabled>
                  <option value="">{escape(t['variantChoose'])}</option>{choices}
                </select>
                <span id="{select_id}-warning" class="warning-msg">{escape(t['requiredWarning'])}</span>
              </div></td>
            </tr>''')
        for variant in option['variants']:
            for field in variant.get('fields', []):
                field_id = f'{prefix}-{escape(variant["id"])}-{escape(field["id"])}'
                minimum = (' data-minimum-field="' + escape(field['minimumField']) + '"') if field.get('minimumField') else ''
                field_type = field.get('type', 'integer')
                if field_type == 'text':
                    attributes = f'type="text" maxlength="{field["maxLength"]}"'
                    warning = t['requiredWarning']
                elif field_type == 'decimal':
                    attributes = 'type="number" min="0" step="any" inputmode="decimal" data-positive'
                    warning = t['positiveNumber']
                else:
                    attributes = 'type="number" min="1" max="9007199254740991" step="1" inputmode="numeric"'
                    warning = t['rpmWarning']
                parameter_rows.append(f'''<tr class="shop-profile-field" data-order-field-row="{escape(variant['id'])}" hidden>
              <th scope="row"><label for="{field_id}">{escape(t[field['labelKey']])} *</label></th>
              <td><div class="form-group">
                <input id="{field_id}" name="{escape(field['id'])}" data-order-field="{escape(field['id'])}" data-order-field-type="{field_type}" data-order-field-warning="{escape(warning)}"{minimum} {attributes} class="validate-me" required disabled>
                <span class="warning-msg">{escape(warning)}</span>
              </div></td>
            </tr>''')
    return f'''<form class="shop-wizard-form shop-item-form" id="item-{prefix}" data-order-product="{prefix}" aria-label="{name}" method="post" novalidate>
      <fieldset class="shop-profile-options">
        <legend class="shop-sr-only">{escape(t['variant'])}: {name}</legend>
        <table class="shop-profile-table shop-item-table" aria-label="{name}">
          <colgroup><col class="shop-item-option-column"><col></colgroup>
          <thead><tr><th class="shop-profile-label" scope="col">{escape(t['variant'])}</th><th id="{prefix}-price-heading" class="shop-profile-label shop-profile-price" scope="col">{escape(t['retail'])}</th></tr></thead>
          {''.join(rows)}
          <tbody class="shop-profile-fields" data-profile-fields hidden>
            {''.join(variant_rows)}
            {''.join(parameter_rows)}
            <tr class="shop-profile-field">
              <th scope="row"><label id="label-quantity-{prefix}" for="quantity-{prefix}">{escape(t['quantity'])} *</label></th>
              <td><div class="form-group">
                <div class="shop-quantity" role="group" aria-labelledby="label-quantity-{prefix}">
                  <button type="button" data-order-change="-1" aria-label="{escape(t['decrease'])}: {name}" aria-controls="quantity-{prefix}" disabled>−</button>
                  <input id="quantity-{prefix}" name="quantity" data-order-quantity type="number" min="1" max="9999" step="1" value="1" inputmode="numeric" class="validate-me" data-warning-id="quantity-{prefix}-warning" required disabled>
                  <button type="button" data-order-change="1" aria-label="{escape(t['increase'])}: {name}" aria-controls="quantity-{prefix}" disabled>+</button>
                </div>
                <span id="quantity-{prefix}-warning" class="warning-msg">{escape(t['quantityLimit'])}</span>
              </div></td>
            </tr>
            <tr class="shop-profile-field shop-profile-submit">
              <td></td><td><button class="btn-submit" type="submit" disabled>{escape(t['addConfigured'])}</button>
                <p class="shop-wizard-status" role="status" aria-live="polite" hidden></p>
              </td>
            </tr>
          </tbody>
        </table>
      </fieldset>
    </form>'''


def wizard_form(product, lang, t):
    wizard = product['wizard']
    prefix = escape(product['id'])
    columns = ('profileHeading', 'camDuration', 'camLift', 'price')
    headers = ''.join(f'<th id="{prefix}-{key}-heading" class="shop-profile-label{" shop-profile-price" if key == "price" else ""}" scope="col">{escape(t[key])}</th>'
                      for key in columns)
    options = []
    for profile in wizard['profiles']:
        method = t['manufactureNew' if profile['manufacture'] == 'new' else 'manufactureRegrind']
        option_id = f"{prefix}-{escape(profile['id'])}"
        values = (profile['duration'], profile['lift'], money(profile['price'], lang))
        cells = []
        for key, value in zip(columns[1:], values):
            cell_class = 'shop-profile-stat shop-profile-price' if key == 'price' else 'shop-profile-stat'
            cells.append(f'<td class="{cell_class}" rowspan="2"><label for="{option_id}"><span id="{option_id}-{key}" class="shop-profile-value">{escape(value)}</span></label></td>')
        labelled_by = ' '.join(f'{prefix}-{key}-heading {option_id}-{key}' for key in columns)
        options.append(f'''<tbody class="shop-profile-option">
          <tr>
            <td><label class="shop-profile-radio-label" for="{option_id}">
              <input type="radio" name="profile" value="{escape(profile['id'])}" id="{option_id}" aria-labelledby="{labelled_by}" aria-describedby="{option_id}-description">
              <span id="{option_id}-profileHeading" class="shop-profile-method">{escape(method)}</span>
            </label></td>
            {''.join(cells)}
          </tr>
          <tr><td><label class="shop-profile-description" id="{option_id}-description" for="{option_id}">{escape(profile['translations'][lang])}</label></td></tr>
        </tbody>''')
    bearings = ''.join(f'<option value="{escape(b["id"])}">{escape(t[b["labelKey"]])} {escape(b["diameters"])}</option>'
                       for b in wizard['bearings'])
    bearing_row = f'''        <tr class="shop-profile-field shop-bearing-fields" data-bearing-fields hidden>
          <th scope="row"><label id="label-{prefix}-bearing" for="{prefix}-bearing">{escape(t['bearings'])} *</label></th>
          <td colspan="3"><div class="form-group shop-variant">
            <select id="{prefix}-bearing" name="bearing" class="custom-select validate-me" data-bearing data-warning-id="{prefix}-bearing-warning" disabled>
              <option value="">{escape(t['chooseBearings'])}</option>{bearings}
            </select>
            <span id="{prefix}-bearing-warning" class="warning-msg">{escape(t['requiredWarning'])}</span>
          </div></td>
        </tr>
''' if wizard['bearings'] else ''
    field_rows = []
    for field in wizard['fields']:
        key = escape(field['id'])
        label = t[field['labelKey']] + (f' ({field["unit"]})' if field.get('unit') else '')
        constraints = 'min="0" step="any" inputmode="decimal" data-positive' if field['type'] == 'number' else f'maxlength="{field["maxLength"]}"'
        warning = t['positiveNumber'] if field['type'] == 'number' else t['requiredWarning']
        field_rows.append(f'''        <tr class="shop-profile-field shop-engine-field">
          <th scope="row"><label for="{prefix}-{key}">{escape(label)}{' *' if field['required'] else ''}</label></th>
          <td colspan="3"><div class="form-group">
            <input id="{prefix}-{key}" name="{key}" type="{field['type']}" {constraints} {'required' if field['required'] else ''} class="validate-me" data-engine-field disabled>
            <span class="warning-msg">{escape(warning)}</span>
          </div></td>
        </tr>''')
    profile_fields = f'''      <tbody id="{prefix}-profile-fields" class="shop-profile-fields" data-profile-fields hidden>
{bearing_row}{''.join(field_rows)}
        <tr class="shop-profile-field shop-profile-submit">
          <td></td>
          <td colspan="3">
            <button class="btn-submit" type="submit" disabled>{escape(t['addConfigured'])}</button>
            <p class="shop-wizard-status" role="status" aria-live="polite" hidden></p>
          </td>
        </tr>
      </tbody>'''
    return f'''<form class="shop-wizard-form" id="wizard-{prefix}" data-wizard="{prefix}" aria-label="{escape(t['configure'])}: {escape(product['translations'][lang]['name'])}" method="post" novalidate>
      <fieldset class="shop-profile-options">
        <legend class="shop-sr-only">{escape(t['configure'])}</legend>
        <table class="shop-profile-table" aria-label="{escape(t['configure'])}">
          <colgroup><col class="shop-profile-operation-column"><col class="shop-profile-spec-column"><col class="shop-profile-spec-column"><col class="shop-profile-price-column"></colgroup>
          <thead><tr>{headers}</tr></thead>
          {''.join(options)}
{profile_fields}
        </table>
      </fieldset>
    </form>'''


def product_photos(product, lang, t, position, placeholder_image):
    name = product['translations'][lang]['name']
    is_placeholder = not product.get('image')
    images = product.get('images') or [{
        'src': product.get('image') or placeholder_image, 'width': 640, 'height': 480,
        'alt': {lang: t['noPhoto'] if is_placeholder else name},
    }]
    placeholder_attr = ' data-placeholder="true"' if is_placeholder else ''
    links = []
    for index, image in enumerate(images):
        alt = image['alt'][lang]
        link_label = t['enlargePhoto'] + ': ' + (alt if len(images) > 1 else name)
        loading = 'eager' if position < 2 and index == 0 else 'lazy'
        links.append(f'''<a class="shop-photo-link" id="photo-{escape(product['id'])}-{index + 1}" href="{escape(image['src'])}" style="--shop-photo-width: {image['width']}px" aria-haspopup="dialog" aria-label="{escape(link_label)}">
        <span class="tech-frame">
          <img src="{escape(image['src'])}" alt="{escape(alt)}" width="{image['width']}" height="{image['height']}" loading="{loading}" decoding="async"{placeholder_attr}>
        </span>
      </a>''')
    gallery_class = ' shop-photo-gallery' if len(images) > 1 else ''
    placeholder_class = ' shop-photo-placeholder' if is_placeholder else ''
    return f'''<figure class="shop-photo{gallery_class}{placeholder_class}">
      {''.join(links)}
    </figure>'''


def wizard_description(product, lang, t):
    paragraphs = product['translations'][lang]['description'].split('\n\n')
    groups = product.get('descriptionGroups')
    if not groups:
        return ''.join(f'<p class="shop-description">{escape(paragraph)}</p>' for paragraph in paragraphs)
    headings = {'regrind': t['manufactureRegrind'], 'new': t['manufactureNew'], 'instructions': t['installationInstructions']}
    sections = []
    for group in groups:
        kind = group['kind']
        classes = 'shop-description-section' + (' shop-description-wide' if kind in ('lead', 'instructions') else '')
        heading = f'<h4>{escape(headings[kind])}</h4>' if kind in headings else ''
        content = ''.join(f'<p class="shop-description">{escape(paragraphs[index])}</p>' for index in group['paragraphs'])
        sections.append(f'<section class="{classes}" data-description-group="{kind}">{heading}{content}</section>')
    return ''.join(sections)


def product_card(product, lang, t, position, placeholder_image):
    text = product['translations'][lang]
    product_id = escape(product['id'])
    name = escape(text['name'])
    description = ''.join(f'<p class="shop-description">{escape(paragraph)}</p>' for paragraph in text['description'].split('\n\n') if paragraph.strip())
    is_wizard = product.get('kind') == 'wizard'
    photo = product_photos(product, lang, t, position, placeholder_image)
    if is_wizard:
        return f'''<article class="blog-card shop-product shop-wizard-product" id="{product_id}" data-product="{product_id}" aria-labelledby="name-{product_id}">
      <h3 class="shop-product-title" id="name-{product_id}">{name}</h3>
      {photo}
      <div class="shop-product-content"><div class="shop-product-body shop-description-layout">{wizard_description(product, lang, t)}</div></div>
      {wizard_form(product, lang, t)}
    </article>'''
    article_link = f'<a href="/{lang}/blog#post-2-title">{escape(t["blog"])}: TAZ 1.43 / PS12 ↗</a>' if product['id'] == 'exhaust-headers' else ''
    content = f'<div class="shop-product-content"><div class="shop-product-body">{description}{article_link}</div></div>' if description or article_link else ''
    card = f'''<article class="blog-card shop-product shop-wizard-product shop-option-product{' shop-no-description' if not content else ''}" id="{product_id}" data-product="{product_id}" aria-labelledby="name-{product_id}">
      <h3 class="shop-product-title" id="name-{product_id}">{name}</h3>
      {photo}
      {content}
      {order_item_form(product, lang, t)}
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
        t = {**t, **main_form_copy(root, lang)}
        copy = data['copy'][lang]
        header, footer = site_navigation(root, lang)
        client_products = [{
            'id': p['id'], 'name': p['translations'][lang]['name'],
            'price': p['price'], 'priceType': p['priceType'], 'variants': localized_variants(p, lang),
            **({'options': standard_options(p, lang), 'legacyItems': p.get('legacyItems', [])} if p.get('kind') != 'wizard' else {}),
            **({'kind': 'wizard', 'wizard': {
                **p['wizard'],
                'profiles': [{key: value for key, value in profile.items() if key != 'translations'}
                             | {'description': profile['translations'][lang]} for profile in p['wizard']['profiles']],
            }} if p.get('kind') == 'wizard' else {}),
        } for p in data['products']]
        config = json.dumps({'products': client_products, 'currency': data['currency'],
                             'locale': lang, 'email': data['orderEmail'], 'text': t}, ensure_ascii=False)
        config = config.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
        values = {key: escape(value) for key, value in t.items()}
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
