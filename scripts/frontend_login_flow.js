#!/usr/bin/env node
// Simple Playwright-driven login flow smoke test.

const { chromium } = require('playwright');

const frontendUrl = process.env.VIBERESEARCH_FRONTEND_URL || 'http://localhost:3000';
const email = process.env.VIBERESEARCH_TEST_EMAIL;
const password = process.env.VIBERESEARCH_TEST_PASSWORD;

if (!email || !password) {
  console.error('Set VIBERESEARCH_TEST_EMAIL and VIBERESEARCH_TEST_PASSWORD before running.');
  process.exit(2);
}

async function run() {
  console.log('🚀 Starting frontend login regression');
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(15000);

  try {
    const authUrl = `${frontendUrl.replace(/\/$/, '')}/auth`;
    console.log(`🔗 Navigating to ${authUrl}`);
    await page.goto(authUrl, { waitUntil: 'networkidle' });

    await page.waitForSelector('[data-testid="login-email"]');
    await page.fill('[data-testid="login-email"]', email);
    await page.fill('[data-testid="login-password"]', password);
    await page.click('[data-testid="login-submit"]');

    const loginResponse = await page.waitForResponse(
      (response) =>
        response.url().includes('/api/auth/login') && response.request().method() === 'POST',
      { timeout: 15000 }
    );

    console.log(`📡 Login API status: ${loginResponse.status()}`);
    if (!loginResponse.ok()) {
      const body = await loginResponse.text();
      throw new Error(`Login API failed with status ${loginResponse.status()}: ${body}`);
    }

    await page.waitForURL((url) => !url.pathname.includes('/auth'), { timeout: 20000 });
    console.log(`✅ Redirected to ${page.url()}`);

    await page.waitForSelector('text=/仪表盘|Dashboard|任务|Tasks/');
    console.log('✅ Dashboard content detected');

    await page.screenshot({ path: 'frontend_login_success.png', fullPage: true });
    console.log('📸 Screenshot saved to frontend_login_success.png');

    console.log('🎉 Frontend login flow succeeded');
  } catch (error) {
    console.error('💥 Frontend login flow failed:', error);
    await page.screenshot({ path: 'frontend_login_failure.png', fullPage: true }).catch(() => undefined);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

run();
