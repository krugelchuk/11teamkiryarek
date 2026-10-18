import { test, expect, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const currentDir = fileURLToPath(new URL('.', import.meta.url));
const SCREENSHOTS_DIR = resolve(currentDir, 'screenshots');
mkdirSync(SCREENSHOTS_DIR, { recursive: true });

const WIDTHS = [390, 768, 1440] as const;

async function checkNoOverflow(page: Page, screenName: string, width: number) {
  // Allow 1px tolerance for browser subpixel rounding
  const isWithin = await page.evaluate(() => {
    return document.documentElement.scrollWidth <= window.innerWidth + 1;
  });
  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(
    isWithin,
    `Horizontal overflow on ${screenName} at ${width}px: scrollWidth (${scrollWidth}px) > innerWidth (${width}px)`
  ).toBe(true);
}

async function captureScreen(page: Page, name: string, width: number) {
  await checkNoOverflow(page, name, width);
  await page.screenshot({
    path: resolve(SCREENSHOTS_DIR, `${width}_${name}.png`),
    fullPage: false,
  });
}

async function openSidebarIfMobile(page: Page, width: number) {
  if (width < 960) {
    const menuBtn = page.locator('.menu-btn');
    if (await menuBtn.isVisible()) {
      await menuBtn.click();
      await page.waitForTimeout(200);
    }
  }
}

async function logout(page: Page, width: number) {
  await openSidebarIfMobile(page, width);
  const logoutBtn = page.locator('button:has-text("Выйти")');
  await logoutBtn.waitFor({ state: 'visible' });
  await logoutBtn.click();
  await page.waitForURL('**/login', { timeout: 10000 });
}

async function loginAs(page: Page, email: string, pass = 'Demo2026!') {
  await page.goto('/login');
  await page.waitForSelector('input[type="email"]');
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', pass);
  await page.click('button:has-text("Войти")');
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10000 });
}

for (const width of WIDTHS) {
  test.describe(`Full Walkthrough at ${width}px`, () => {
    test.beforeEach(async ({ page }) => {
      await page.setViewportSize({ width, height: width === 390 ? 844 : width === 768 ? 1024 : 900 });
    });

    test(`E2E flow: 3 roles, vacation, approvals, notifications, course 100%, assistant`, async ({ page }) => {
      // 1. Login screen
      await page.goto('/login');
      await page.waitForSelector('.login-card');
      await captureScreen(page, 'login', width);

      // 2. Login as Employee
      await loginAs(page, 'employee@demo.local');
      await page.waitForSelector('.stats');
      await captureScreen(page, 'dashboard_employee', width);

      // 3. Requests page - Create Vacation
      await page.goto('/requests');
      await page.waitForSelector('form.form');
      await captureScreen(page, 'requests_list', width);

      // Fill and submit vacation request
      const today = new Date();
      const offset = 65 + WIDTHS.indexOf(width) * 12;
      const start = new Date(today.getTime() + offset * 86400000).toISOString().slice(0, 10);
      const end = new Date(today.getTime() + (offset + 3) * 86400000).toISOString().slice(0, 10);

      await page.fill('input[type="date"] >> nth=0', start);
      await page.fill('input[type="date"] >> nth=1', end);
      await page.fill('textarea', `Проверка отпуска ${width}`);
      await captureScreen(page, 'request_form_filled', width);

      await page.click('button:has-text("Отправить на согласование")');
      await page.waitForSelector('.alert-success');
      await captureScreen(page, 'request_submitted', width);

      // Logout employee
      await logout(page, width);

      // 4. Login as Manager - Approvals
      await loginAs(page, 'manager@demo.local');
      await page.goto('/approvals');
      await page.waitForSelector('.table');
      await captureScreen(page, 'approvals_manager', width);

      // Approve pending request
      const approveBtn = page.locator('tr').filter({ hasText: `Проверка отпуска ${width}` }).getByRole('button', { name: 'Одобрить', exact: true });
      await approveBtn.waitFor({ state: 'visible' });
      await approveBtn.click();

      await page.waitForSelector('.modal');
      await page.fill('.modal textarea', 'Согласовано, хорошего отдыха');
      await captureScreen(page, 'approval_modal', width);

      await page.click('.modal-actions button:has-text("Одобрить")');
      await page.waitForSelector('.alert-success');
      await captureScreen(page, 'approval_success', width);

      // Logout manager
      await logout(page, width);

      // 5. Login back as Employee - Check Status, History, Notifications, Balance
      await loginAs(page, 'employee@demo.local');

      // Check Requests
      await page.goto('/requests');
      await page.waitForSelector('.table');
      // Click first row to view details modal
      await page.click('.table tbody tr >> nth=0');
      await page.waitForSelector('.modal');
      await captureScreen(page, 'request_details_history', width);

      // Close modal
      await page.click('.modal-head button[aria-label="Закрыть"]');
      await page.waitForTimeout(300);

      // Notifications
      await page.goto('/notifications');
      await page.waitForSelector('.notif-list');
      await captureScreen(page, 'notifications', width);

      // 6. Jana Academy - Complete course to 100%
      await page.goto('/academy');
      await page.waitForSelector('.cards');
      await captureScreen(page, 'academy_catalog', width);

      // Open first course
      await page.click('.course-card >> nth=0 >> a.btn');
      await page.waitForSelector('.lessons');
      await captureScreen(page, 'course_view', width);

      // Expand lessons and complete all uncompleted lessons
      const lessonButtons = page.locator('.lesson-head');
      const count = await lessonButtons.count();
      for (let i = 0; i < count; i++) {
        const btn = lessonButtons.nth(i);
        await btn.click();
        await page.waitForTimeout(200);
        const completeBtn = page.locator('button:has-text("Отметить прочитанным")');
        if (await completeBtn.isVisible()) {
          await completeBtn.click();
          await page.waitForTimeout(400);
        }
      }

      // Quiz section
      const quizSection = page.locator('.options');
      if (await quizSection.isVisible()) {
        // Option 1 is the correct answer
        await page.getByRole('radio').nth(0).check();
        await page.getByRole('button', { name: 'Ответить', exact: true }).click();
        await expect(page.getByRole('alert')).toContainText('Ответ неверный');
        const option = page.getByRole('radio').nth(1);
        await option.check();
        await page.click('button:has-text("Ответить")');
        await page.waitForTimeout(500);
      }
      await expect(page.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100');
      await captureScreen(page, 'course_completed_100', width);

      // 7. AI Assistant - Ask Question & Open Source Modal
      await page.goto('/assistant');
      await page.waitForSelector('.chat');
      await captureScreen(page, 'assistant_initial', width);

      await page.fill('.chat-input input', 'Как оформить отпуск?');
      await page.click('.chat-input button:has-text("Отправить")');

      // Wait for bot answer with source button
      const sourceBtn = page.locator('.sources button.source').first();
      await sourceBtn.waitFor({ state: 'visible', timeout: 15000 });
      await captureScreen(page, 'assistant_answered', width);

      // Click source button to open document modal
      await sourceBtn.click();
      await page.waitForSelector('.modal');
      await captureScreen(page, 'assistant_source_modal', width);

      // Close modal
      await page.click('.modal-head button[aria-label="Закрыть"]');
      await page.waitForTimeout(200);

      await page.fill('.chat-input input', 'Какая погода на Марсе?');
      await page.getByRole('button', { name: 'Отправить', exact: true }).click();
      await expect(page.locator('.bubble-nf').last()).toBeVisible();

      // Logout employee
      await logout(page, width);

      // 8. Login as HR
      await loginAs(page, 'hr@demo.local');
      await page.goto('/admin');
      await page.waitForSelector('.admin-tabs');
      await captureScreen(page, 'admin_hr_overview', width);

      // Switch to Knowledge tab
      await page.click('button[role="tab"]:has-text("База знаний")');
      await page.waitForTimeout(300);
      await captureScreen(page, 'admin_knowledge_tab', width);

      // Switch to Courses tab
      await page.click('button[role="tab"]:has-text("Курсы")');
      await page.waitForTimeout(300);
      await captureScreen(page, 'admin_courses_tab', width);
    });
  });
}
