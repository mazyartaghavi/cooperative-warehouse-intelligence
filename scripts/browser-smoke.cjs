// Optional real-browser integration check. The API must be running with a fresh database.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 960 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(process.env.CWI_TEST_URL || 'http://127.0.0.1:8765');
    await page.locator('#token').fill(process.env.CWI_API_TOKEN);
    await page.locator('#connect').click();
    await page.waitForFunction(() => document.querySelector('#mode').textContent.includes('baseline'));
    await page.locator('#message').fill('Move the blue tote to P2');
    await page.locator('#send').click();
    await page.waitForFunction(() => document.querySelector('#log').textContent.includes('Which tote'));
    await page.locator('#message').fill('T17');
    await page.locator('#send').click();
    await page.waitForFunction(() => document.querySelector('#log').textContent.includes('Confirm T17'));
    await page.locator('#confirm').click();
    await page.waitForFunction(() => document.querySelector('#log').textContent.includes('queued'));
    const first = page.locator('.job-card[data-tote="T17"]');
    await first.locator('[data-action="pause"]').click();
    await first.locator('[data-action="resume"]').waitFor();
    await page.locator('#step').click();
    if (!(await first.locator('.job-status').textContent()).includes('Paused')) {
      throw new Error('Paused job lost its state');
    }
    await first.locator('[data-action="resume"]').click();
    await page.locator('#run').click();
    await page.waitForFunction(() => document.querySelector('#metrics').textContent.includes('1 deliveries'),
                              null, { timeout: 30000 });
    await page.locator('#stop').click();
    // Cancel an actual carrying mission; completion must wait for the source return.
    await page.locator('#message').fill('Please bring T23 to P1');
    await page.locator('#send').click();
    await page.waitForFunction(() => document.querySelector('#log').textContent.includes('Confirm T23'));
    await page.locator('#confirm').click();
    const second = page.locator('.job-card[data-tote="T23"]');
    for (let i = 0; i < 40; i++) {
      if ((await second.locator('.job-status').textContent()) === 'carrying') break;
      await page.locator('#step').click();
    }
    if ((await second.locator('.job-status').textContent()) !== 'carrying') {
      throw new Error('Second robot never picked up its tote');
    }
    await page.locator('#step').click();
    await page.locator('#step').click();
    await second.locator('[data-action="cancel"]').click();
    await page.waitForFunction(() => document.querySelector('.job-card[data-tote="T23"] .job-status').textContent === 'returning');
    await page.locator('#run').click();
    await page.waitForFunction(() => document.querySelector('.job-card[data-tote="T23"] .job-status').textContent === 'cancelled',
                              null, { timeout: 30000 });
    await page.locator('#stop').click();
    if (!(await page.locator('#metrics').textContent()).includes('1 deliveries')) {
      throw new Error('Cancellation was incorrectly counted as a delivery');
    }
    const output = process.env.CWI_BROWSER_OUTPUT || 'outputs/browser';
    fs.mkdirSync(output, { recursive: true });
    await page.screenshot({ path: path.join(output, 'desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(output, 'mobile.png'), fullPage: true });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    if (errors.length || overflow) throw new Error(JSON.stringify({ errors, overflow }));
    console.log('Browser passed: clarify, confirm, task pause/resume, delivery, cargo return on cancellation; no script errors or mobile overflow.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
