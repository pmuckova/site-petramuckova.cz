import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
const playwright = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const { chromium } = playwright.default || playwright;
const [base, mailDirectory, output] = process.argv.slice(2);
assert.match(base, /^http:\/\/127\.0\.0\.1:\d+$/);
const browser = await chromium.launch({ headless: true,
    ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
    await context.route('**/*', route => {
        const url = new URL(route.request().url());
        return url.origin === base || ['cdn.jsdelivr.net', 'fonts.googleapis.com', 'fonts.gstatic.com'].includes(url.hostname)
            ? route.continue() : route.abort();
    });
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + '/cs/shop.html', { waitUntil: 'networkidle' });
    await page.locator('#ignition-coil input[name="option"][value="contactless"]').click();
    await page.locator('#ignition-coil input[name="quantity"]').fill('2');
    await page.locator('#ignition-coil button[type="submit"]').click();
    await page.locator('#taz-camshaft input[name="profile"][value="new-284-284-8-0"]').click();
    for (const [field, value] of Object.entries({ bore: '82', stroke: '90', exhaustValve: '31', intakeValve: '35' })) {
        await page.locator(`#taz-camshaft input[name="${field}"]`).fill(value);
    }
    await page.locator('#taz-camshaft button[type="submit"]').click();
    const fields = { fullName: 'Test Customer', email: 'customer@example.test', company: 'Test Company', phone: '+420 604 123 456',
        street: 'Test Street 1', city: 'Test City', postcode: '123 45', country: 'Test Country', notes: 'Test <note>\nSecond line' };
    for (const [name, value] of Object.entries(fields)) await page.locator(`#shop-order-form [name="${name}"]`).fill(value);
    await page.locator('#order-attachment-1').setInputFiles({ name: 'instructions.txt', mimeType: 'text/plain', buffer: Buffer.from('Test attachment') });
    await page.locator('#order').screenshot({ path: path.join(output, 'order-form-desktop.png') });
    assert.equal(await page.locator('#basket-items > li').count(), 2);

    const requestIds = [];
    let releasePost;
    await page.route('**/backend/order_form_handler.php', async route => {
        if (route.request().method() === 'POST') {
            requestIds.push(route.request().postData().match(/name="requestId"\r\n\r\n([^\r]+)/)[1]);
            await new Promise(resolve => { releasePost = resolve; });
        }
        await route.fulfill({ response: await route.fetch() });
    });
    const waitForPost = async () => {
        for (let attempt = 0; !releasePost && attempt < 100; attempt++) await new Promise(resolve => setTimeout(resolve, 25));
        assert.ok(releasePost, 'Expected POST');
    };
    await fs.writeFile(path.join(mailDirectory, 'fail'), '');
    await page.locator('#order-prepare').click();
    await waitForPost();
    assert.equal(await page.locator('#order-prepare').isDisabled(), true);
    assert.equal(await page.locator('#shop-order-form').getAttribute('aria-busy'), 'true');
    assert.equal(await page.locator('#basket').evaluate(node => node.inert), true);
    releasePost(); releasePost = null;
    await page.locator('#order-message .msg-error').waitFor();
    assert.equal(await page.locator('#order-name').inputValue(), fields.fullName);
    assert.equal(await page.locator('#order-attachment-1').evaluate(node => node.files.length), 1);
    assert.equal(await page.locator('#basket-items > li').count(), 2);
    await fs.unlink(path.join(mailDirectory, 'fail'));
    await page.locator('#order-prepare').click();
    await waitForPost();
    assert.equal(requestIds[0], requestIds[1], 'An unchanged retry must keep its receipt ID');
    // Simulate a genuine other-tab addition while this tab is sending.
    const other = await context.newPage();
    await other.goto(base + '/cs/shop.html', { waitUntil: 'domcontentloaded' });
    await other.evaluate(() => {
        const saved = JSON.parse(localStorage.getItem('muckova-shop-basket'));
        saved.items.push({ id: 'resonance-exhaust', variant: '', quantity: 1 });
        localStorage.setItem('muckova-shop-basket', JSON.stringify(saved));
    });
    releasePost(); releasePost = null;
    await page.locator('#order-message .msg-success').waitFor();
    assert.equal(await page.locator('#order-name').inputValue(), '');
    assert.equal(await page.locator('#order-attachment-1').evaluate(node => node.files.length), 0);
    const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('muckova-shop-basket')));
    assert.deepEqual(saved.items, [{ id: 'resonance-exhaust', variant: '', quantity: 1 }]);
    const sentFiles = (await fs.readdir(mailDirectory)).filter(name => name.endsWith('.json'));
    assert.equal(sentFiles.length, 2);
    const messages = await Promise.all(sentFiles.map(async name => JSON.parse(await fs.readFile(path.join(mailDirectory, name), 'utf8'))));
    const message = messages.find(message => message.to[0] === 'info@petramuckova.cz');
    const recap = messages.find(message => message.to[0] === fields.email);
    assert.ok(message.html.includes('17 700 Kč'));
    assert.ok(message.html.includes('Test &lt;note&gt;'));
    assert.ok(message.html.includes('Vačková hřídel TAZ'));
    assert.equal(message.attachments.length, 1);
    assert.equal(recap.attachments.length, 0);
    assert.ok(recap.html.includes('17 700 Kč'));
    assert.ok(recap.html.includes('Test &lt;note&gt;'));
    assert.ok(recap.html.includes('Vačková hřídel TAZ'));
    assert.ok(recap.html.includes('Nyní prosím vyčkejte na naši odpověď, ve které si s Vámi objednávku potvrdíme a ověříme dostupnost zboží, zvolenou dopravu a konečnou cenu.'));
    assert.ok(!recap.html.includes('Toto je automatická rekapitulace'));
    assert.ok(!recap.html.includes('Doprava není zahrnuta.'));
    assert.equal(recap.replyTo[0], 'info@petramuckova.cz');
    await fs.writeFile(path.join(output, 'order-email-example.html'), message.html);
    const emailPreview = await context.newPage();
    await emailPreview.setViewportSize({ width: 1000, height: 900 });
    await emailPreview.setContent(message.html);
    await emailPreview.screenshot({ path: path.join(output, 'order-email-example.png'), fullPage: true });
    await fs.writeFile(path.join(output, 'customer-recap-example.html'), recap.html);
    await emailPreview.setContent(recap.html);
    assert.equal(await emailPreview.locator('body > :first-child').innerText(), 'Děkujeme za Vaši objednávku.');
    assert.ok(await emailPreview.locator('body > p:nth-child(2) > strong').count());
    assert.equal(await emailPreview.locator('body > :last-child').innerText(), 'Petra Mücková s.r.o.\nIČ: 25393928\nFučíkova 1311, 742 58 Příbor\ninfo@petramuckova.cz\n+420 604 487 263');
    await emailPreview.screenshot({ path: path.join(output, 'customer-recap-example.png'), fullPage: true });
    await emailPreview.setViewportSize({ width: 390, height: 844 });
    await emailPreview.screenshot({ path: path.join(output, 'customer-recap-mobile.png'), fullPage: true });
    await page.locator('#shop-order-form').screenshot({ path: path.join(output, 'order-sent.png') });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('#order').scrollIntoViewIfNeeded();
    const bounds = await page.locator('#shop-order-form').boundingBox();
    assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= 390);
    await page.locator('#order').screenshot({ path: path.join(output, 'order-form-mobile.png') });

    // A failed customer recap must not present the received business order as failed.
    for (const [name, value] of Object.entries(fields)) await page.locator(`#shop-order-form [name="${name}"]`).fill(value);
    await fs.writeFile(path.join(mailDirectory, 'fail-customer'), '');
    await page.locator('#order-prepare').click();
    await waitForPost();
    releasePost(); releasePost = null;
    await page.locator('#order-message .msg-success').waitFor();
    assert.ok((await page.locator('#order-message').innerText()).includes('objednávku znovu neodesílejte'));
    assert.equal(await page.locator('#order-name').inputValue(), '');
    assert.equal(await page.locator('#basket-items > li').count(), 0);
    assert.equal((await fs.readdir(mailDirectory)).filter(name => name.endsWith('.json')).length, 3);
    await page.locator('#order').screenshot({ path: path.join(output, 'customer-recap-failed.png') });
    await fs.unlink(path.join(mailDirectory, 'fail-customer'));

    // Regress the existing contact form without calling a real contact handler.
    const main = await context.newPage();
    main.on('pageerror', error => errors.push(error.message));
    await main.route('**/backend/contact_form_handler.php', async route => {
        assert.equal(route.request().method(), 'POST');
        assert.ok(route.request().postData().includes('instructions.txt'));
        await route.fulfill({ status: 200, contentType: 'text/plain', body: '' });
    });
    await main.goto(base + '/cs/index.html#contact', { waitUntil: 'networkidle' });
    for (const [name, value] of Object.entries({ fullname: 'Contact Test', email: fields.email, city: fields.city, phone: fields.phone })) {
        await main.locator(`#inquiryForm [name="${name}"]`).fill(value);
    }
    await main.locator('#inquiryForm input[type="file"]').first().setInputFiles({ name: 'instructions.txt', mimeType: 'text/plain', buffer: Buffer.from('Test attachment') });
    for (const selector of ['input[type="email"]', '.file-upload-btn', 'h4.form-section-title']) {
        const properties = node => {
            const style = getComputedStyle(node);
            return [style.fontFamily, style.fontSize, style.color, style.padding, style.borderStyle];
        };
        await page.setViewportSize({ width: 1440, height: 1100 });
        assert.deepEqual(await main.locator('#inquiryForm ' + selector).first().evaluate(properties),
            await page.locator('#shop-order-form ' + selector).first().evaluate(properties));
    }
    await main.locator('#inquiryForm button[type="submit"]').click();
    await main.locator('#form-message .msg-success').waitFor();
    assert.equal(await main.locator('#inquiryForm [name="fullname"]').inputValue(), '');
    assert.deepEqual(errors, []);
    console.log('Browser smoke passed: business + customer emails, partial recap failure, attachments, retry preservation, multi-tab basket, mobile layout, and shared contact styling/submission.');
    console.log('Screenshots and sample email: ' + output);
} finally { await browser.close(); }
