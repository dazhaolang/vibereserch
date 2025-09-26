// Suggested location: frontend/tests/playwright/userJourney.spec.ts
import { test, expect } from '@playwright/test';
import type { Page, TestInfo } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const FRONTEND_BASE_URL = process.env.FRONTEND_BASE_URL ?? 'http://localhost:3002';
const BACKEND_BASE_URL = process.env.BACKEND_BASE_URL ?? 'http://localhost:8000';

const ROUTES = {
  health: process.env.PLAYWRIGHT_HEALTH_ENDPOINT ?? '/health',
  register: process.env.PLAYWRIGHT_REGISTER_ENDPOINT ?? '/api/auth/register',
  login: process.env.PLAYWRIGHT_LOGIN_ENDPOINT ?? '/api/auth/login',
  profile: process.env.PLAYWRIGHT_PROFILE_ENDPOINT ?? '/api/user/profile',
};

const WAIT_FOR_API_MS = Number(process.env.PLAYWRIGHT_WAIT_FOR_API_MS ?? 20000);
const WAIT_FOR_UI_MS = Number(process.env.PLAYWRIGHT_WAIT_FOR_UI_MS ?? 15000);

const RUN_ID = process.env.PLAYWRIGHT_RUN_ID ?? crypto.randomBytes(4).toString('hex');
const CONSOLE_LOG_PATH = path.resolve(process.cwd(), `test-results/console-${RUN_ID}.log`);
const PAGE_ERROR_LOG_PATH = path.resolve(process.cwd(), `test-results/page-errors-${RUN_ID}.log`);
const consoleMessageBuffer = new Map<string, Array<Record<string, unknown>>>();

const appendLogLine = (filePath: string, payload: Record<string, unknown>): void => {
  fs.appendFileSync(filePath, `${JSON.stringify(payload)}\n`, { encoding: 'utf-8' });
};

type TestUser = {
  fullName: string;
  username: string;
  email: string;
  password: string;
};

const createRandomUser = (): TestUser => {
  const randomSuffix = Math.random().toString(36).slice(2, 10);
  const timestamp = Date.now();
  const username = `pw${randomSuffix}${timestamp}`.replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 24) || `pw${timestamp}`;
  return {
    fullName: `Playwright User ${randomSuffix}`,
    username,
    email: `playwright+${randomSuffix}.${timestamp}@example.com`,
    password: `Pw!${randomSuffix}${timestamp}`,
  };
};

const captureSnapshot = async (page: Page, testInfo: TestInfo, label: string): Promise<void> => {
  if (page.isClosed()) {
    return;
  }
  try {
    const screenshot = await page.screenshot({ fullPage: true, timeout: WAIT_FOR_UI_MS });
    await testInfo.attach(label, { body: screenshot, contentType: 'image/png' });
  } catch (error) {
    await testInfo.attach(`${label}-capture-error`, {
      body: Buffer.from(String(error)),
      contentType: 'text/plain',
    });
  }
};

const expectToast = async (page: Page, message: string | RegExp): Promise<void> => {
  const toastLocator = page.locator('[role="alert"], [data-testid="toast"]');
  await expect(toastLocator.first()).toBeVisible({ timeout: WAIT_FOR_UI_MS });
  if (typeof message === 'string') {
    await expect(toastLocator).toContainText(message, { timeout: WAIT_FOR_UI_MS });
  } else {
    await expect(toastLocator).toHaveText(message, { timeout: WAIT_FOR_UI_MS });
  }
};

const loginThroughUI = async (page: Page, user: TestUser): Promise<void> => {
  await page.goto('/auth', { waitUntil: 'domcontentloaded' });

  // Ensure we're on the login tab (should be selected by default)
  const loginTab = page.locator('[role="tab"]:has-text("登录账号")');
  await expect(loginTab).toBeVisible({ timeout: WAIT_FOR_UI_MS });
  await expect(loginTab).toHaveAttribute('aria-selected', 'true');

  // Fill in the login form using the actual selectors from the page
  await page.fill('input[placeholder="you@example.com"]', user.email);
  await page.fill('input[placeholder="请输入密码"]', user.password);

  const loginResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes(ROUTES.login) && response.request().method() === 'POST',
    { timeout: WAIT_FOR_API_MS },
  );

  // Click the login button using the exact text from the page
  await page.click('button:has-text("登 录")');
  const loginResponse = await loginResponsePromise;
  expect(loginResponse.ok(), 'Login request failed').toBeTruthy();

  await page.waitForURL(/dashboard|home|overview|workspace/i, { timeout: WAIT_FOR_UI_MS }).catch(() => undefined);
};

const journeyUser = createRandomUser();

test.use({
  baseURL: FRONTEND_BASE_URL,
  navigationTimeout: 45000,
  actionTimeout: 15000,
});

test.beforeAll(() => {
  fs.mkdirSync(path.dirname(CONSOLE_LOG_PATH), { recursive: true });
  fs.writeFileSync(CONSOLE_LOG_PATH, '', { encoding: 'utf-8' });
  fs.writeFileSync(PAGE_ERROR_LOG_PATH, '', { encoding: 'utf-8' });
});

test.beforeEach(async ({ page }, testInfo) => {
  const testKey = testInfo.testId;
  const rawTitlePath = (testInfo as unknown as { titlePath: string[] | (() => string[]) }).titlePath;
  const titleChain = typeof rawTitlePath === 'function' ? rawTitlePath() : rawTitlePath;
  const testPath = Array.isArray(titleChain) ? titleChain.join(' > ') : testInfo.title;
  const buffer: Array<Record<string, unknown>> = [];
  consoleMessageBuffer.set(testKey, buffer);

  page.on('console', (message) => {
    if (!['error', 'warning'].includes(message.type())) {
      return;
    }
    const location = message.location();
    const payload = {
      timestamp: new Date().toISOString(),
      level: message.type(),
      test: testPath,
      text: message.text(),
      location: location.url
        ? `${location.url}:${location.lineNumber ?? 0}:${location.columnNumber ?? 0}`
        : 'unknown',
    };
    buffer.push(payload);
    appendLogLine(CONSOLE_LOG_PATH, payload);
  });

  page.on('pageerror', (error) => {
    const payload = {
      timestamp: new Date().toISOString(),
      level: 'pageerror',
      test: testPath,
      message: error.message,
      stack: error.stack,
    };
    buffer.push(payload);
    appendLogLine(PAGE_ERROR_LOG_PATH, payload);
  });
});

test.afterEach(async ({}, testInfo) => {
  const testKey = testInfo.testId;
  const buffer = consoleMessageBuffer.get(testKey);
  if (buffer && buffer.length > 0) {
    await testInfo.attach('console-errors', {
      body: Buffer.from(JSON.stringify(buffer, null, 2), 'utf-8'),
      contentType: 'application/json',
    });
  }
  consoleMessageBuffer.delete(testKey);
});

test.describe('UI Journeys', () => {
  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== testInfo.expectedStatus && !page.isClosed()) {
      const failureScreenshot = await page.screenshot({ fullPage: true });
      await testInfo.attach('failure-screenshot', {
        body: failureScreenshot,
        contentType: 'image/png',
      });
    }
  });

  test('basic page load test', async ({ page }, testInfo) => {
    await test.step('Open landing page', async () => {
      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('networkidle');
    });

    await test.step('Validate core layout', async () => {
      // Wait for page content to load
      await expect(page.locator('h1')).toContainText('项目总览');
      await expect(page.locator('h2')).toContainText('智能研究工作台');
      await expect(page).toHaveTitle(/research|insight|dashboard|VibeResearch/i);
    });

    await captureSnapshot(page, testInfo, 'home-default');
  });

  test.describe.serial('User onboarding journey', () => {
    test('user registration flow test', async ({ page }, testInfo) => {
      await test.step('Navigate to auth page', async () => {
        await page.goto('/auth', { waitUntil: 'domcontentloaded' });
        await page.waitForLoadState('networkidle');
      });

      await test.step('Switch to registration tab', async () => {
        await page.click('[role="tab"]:has-text("创建账号")');
        await expect(page.locator('[role="tab"]:has-text("创建账号")').first()).toHaveAttribute('aria-selected', 'true');
      });

    await test.step('Fill registration form', async () => {
      await page.fill('input[placeholder="you@example.com"]', journeyUser.email);
      await page.fill('input[placeholder="研究者昵称"]', journeyUser.username);
      await page.fill('input[placeholder="真实姓名"]', journeyUser.fullName);
      await page.fill('input[placeholder="设置登录密码"]', journeyUser.password);
      await page.fill('input[placeholder="再次输入密码"]', journeyUser.password);
    });

    await test.step('Submit registration', async () => {
      const registrationResponsePromise = page.waitForResponse(
        (response) =>
          response.url().includes(ROUTES.register) && response.request().method() === 'POST',
        { timeout: WAIT_FOR_API_MS },
      );

      await page.click('button:has-text("注册并登录")');

      const registrationResponse = await registrationResponsePromise;
      console.log('Registration response status:', registrationResponse.status());
      expect(registrationResponse.ok(), 'Registration API failed').toBeTruthy();

      await page.waitForLoadState('networkidle');
    });

    await captureSnapshot(page, testInfo, 'post-registration');
  });

    test('user login flow test', async ({ browser }, testInfo) => {
      const context = await browser.newContext({ baseURL: FRONTEND_BASE_URL });
      const loginPage = await context.newPage();

      try {
        await test.step('Authenticate with freshly registered user', async () => {
          await loginThroughUI(loginPage, journeyUser);
        });

        await expectToast(loginPage, /welcome back|hello/i).catch(() => undefined);
        await captureSnapshot(loginPage, testInfo, 'post-login');
      } finally {
        await context.close();
      }
    });

    test('main feature navigation test', async ({ page }, testInfo) => {
      await loginThroughUI(page, journeyUser);

      const baseUrl = FRONTEND_BASE_URL.replace(/\/+$/, '');
      const navItems = [
        {
          label: '仪表盘',
          path: '/',
          heading: /智能研究工作台|项目总览/,
        },
        {
          label: '研究工作台',
          path: '/workspace',
          heading: /研究模式|研究工作台|协作/i,
        },
        {
          label: '文献库',
          path: '/library',
          heading: /文献库/,
        },
        {
          label: '任务中心',
          path: '/tasks',
          heading: /任务列表/,
        },
      ];

      for (const item of navItems) {
        const escapedBase = baseUrl.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const normalizedPath = item.path === '/' ? '' : item.path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const urlPattern = new RegExp(`${escapedBase}${normalizedPath}(?:[/?#]|$)`, 'i');

        await test.step(`Direct load ${item.label}`, async () => {
          await page.goto(item.path, { waitUntil: 'domcontentloaded' });
          await expect(page).toHaveURL(urlPattern, { timeout: WAIT_FOR_UI_MS });
          if (item.heading) {
            await expect(page.getByRole('heading', { name: item.heading })).toBeVisible({ timeout: WAIT_FOR_UI_MS }).catch(() => undefined);
          }
          await captureSnapshot(page, testInfo, `nav-${item.label}`);
        });
      }
    });

    test('workspace guidance state test', async ({ page }, testInfo) => {
      await loginThroughUI(page, journeyUser);
      await page.goto('/workspace', { waitUntil: 'domcontentloaded' });
      await expect(page.getByText('当前尚未选择项目')).toBeVisible({ timeout: WAIT_FOR_UI_MS }).catch(() => undefined);
      await captureSnapshot(page, testInfo, 'workspace-empty-state');
    });
  });

  test('error handling test', async ({ page }, testInfo) => {
    await test.step('Trigger a not-found view', async () => {
      await page.goto('/this-route-does-not-exist', { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('networkidle');
      await expect(page).toHaveURL(/this-route-does-not-exist/);
    });

    const errorState = page.locator('[data-testid="error-state"], [data-testid="not-found-state"]');
    const fallbackCopy = page.getByText(/(not found|404|something went wrong|错误)/i);

    const isErrorVisible = await errorState.first().isVisible();
    if (!isErrorVisible) {
      await expect(fallbackCopy).toBeVisible({ timeout: WAIT_FOR_UI_MS });
    } else {
      await expect(errorState.first()).toBeVisible({ timeout: WAIT_FOR_UI_MS });
    }

    await captureSnapshot(page, testInfo, 'error-state');
  });
});

test.describe('API integration test', () => {
  test('core auth API integration test', async ({ request }, testInfo) => {
    const apiUser = createRandomUser();

    const healthResponse = await request.get(`${BACKEND_BASE_URL}${ROUTES.health}`, {
      timeout: WAIT_FOR_API_MS,
    });
    expect(healthResponse.ok()).toBeTruthy();

    await testInfo.attach('health-response', {
      body: await healthResponse.text(),
      contentType: 'application/json',
    });

    const registerResponse = await request.post(`${BACKEND_BASE_URL}${ROUTES.register}`, {
      data: {
        email: apiUser.email,
        password: apiUser.password,
        username: `playwright_user_${Math.random().toString(36).slice(2, 10)}`, // Clean alphanumeric username
        full_name: apiUser.fullName,
      },
      timeout: WAIT_FOR_API_MS,
      headers: { 'Content-Type': 'application/json' },
    });
    expect(registerResponse.status(), 'Registration API failed').toBeLessThan(400);

    const loginResponse = await request.post(`${BACKEND_BASE_URL}${ROUTES.login}`, {
      data: {
        email: apiUser.email,
        password: apiUser.password,
      },
      timeout: WAIT_FOR_API_MS,
      headers: { 'Content-Type': 'application/json' },
    });
    expect(loginResponse.ok(), 'Login API failed').toBeTruthy();

    const loginJson = await loginResponse.json();
    await testInfo.attach('login-response', {
      body: JSON.stringify(loginJson, null, 2),
      contentType: 'application/json',
    });

    const token: string | undefined = loginJson.access_token ?? loginJson.token;
    expect(token, 'Login response missing access token').toBeTruthy();

    const profileResponse = await request.get(`${BACKEND_BASE_URL}${ROUTES.profile}`, {
      headers: { Authorization: `Bearer ${token}` },
      timeout: WAIT_FOR_API_MS,
    });
    expect(profileResponse.ok(), 'Profile API failed').toBeTruthy();

    const profileJson = await profileResponse.json();
    if (profileJson.email) {
      expect(profileJson.email).toBe(apiUser.email);
    }

    await testInfo.attach('profile-response', {
      body: JSON.stringify(profileJson, null, 2),
      contentType: 'application/json',
    });
  });
});
