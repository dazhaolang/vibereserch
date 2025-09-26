#!/usr/bin/env node
// End-to-end project workflow: pre-create a project via API, then verify it through the UI.

const { chromium } = require('playwright');
const { randomUUID } = require('crypto');

const frontendUrl = process.env.VIBERESEARCH_FRONTEND_URL || 'http://localhost:3000';
const baseApiUrl = process.env.VIBERESEARCH_BASE_URL || 'http://localhost:8000';
const email = process.env.VIBERESEARCH_TEST_EMAIL;
const password = process.env.VIBERESEARCH_TEST_PASSWORD;

if (!email || !password) {
  console.error('Set VIBERESEARCH_TEST_EMAIL and VIBERESEARCH_TEST_PASSWORD before running.');
  process.exit(2);
}

async function loginForToken() {
  const response = await fetch(`${baseApiUrl.replace(/\/$/, '')}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Login failed (${response.status}): ${text}`);
  }

  return response.json();
}

async function createProject(token) {
  const projectName = `QA UI Project ${randomUUID().slice(0, 8)}`;
  const response = await fetch(`${baseApiUrl.replace(/\/$/, '')}/api/project/create-empty`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({
      name: projectName,
      description: 'UI workflow verification project',
      category: 'frontend-workflow'
    })
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Project creation failed (${response.status}): ${text}`);
  }

  const payload = await response.json();
  return { projectName, projectId: payload.id };
}

async function deleteProject(token, projectId) {
  if (!projectId) return;
  await fetch(`${baseApiUrl.replace(/\/$/, '')}/api/project/${projectId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` }
  }).catch(() => undefined);
}

async function run() {
  console.log('🚀 Starting frontend project workflow test');
  const { access_token: token } = await loginForToken();
  console.log('🔐 Backend login successful');

  const { projectName, projectId } = await createProject(token);
  console.log(`📁 Created project via API: ${projectName} (#${projectId})`);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(20000);

  try {
    const authUrl = `${frontendUrl.replace(/\/$/, '')}/auth`;
    await page.goto(authUrl, { waitUntil: 'networkidle' });

    await page.fill('[data-testid="login-email"]', email);
    await page.fill('[data-testid="login-password"]', password);
    await page.click('[data-testid="login-submit"]');

    const loginResponse = await page.waitForResponse(
      (response) =>
        response.url().includes('/api/auth/login') && response.request().method() === 'POST',
      { timeout: 15000 }
    );
    console.log(`📡 Login API status: ${loginResponse.status()}`);

    await page.waitForURL((url) => !url.pathname.includes('/auth'), { timeout: 20000 });
    console.log(`✅ Redirected to ${page.url()}`);

    await page.waitForSelector(`text=${projectName}`);
    console.log(`✅ Project visible on dashboard: ${projectName}`);

    await page.screenshot({ path: 'frontend_project_workflow.png', fullPage: true });
    console.log('📸 Screenshot saved to frontend_project_workflow.png');

    console.log('🎉 Frontend project workflow succeeded');
  } catch (error) {
    console.error('💥 Frontend project workflow failed:', error);
    await page.screenshot({ path: 'frontend_project_workflow_failure.png', fullPage: true }).catch(() => undefined);
    process.exitCode = 1;
  } finally {
    await browser.close();
    await deleteProject(token, projectId);
  }
}

run();

