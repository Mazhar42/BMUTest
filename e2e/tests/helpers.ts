import { expect, type Browser, type Page } from "@playwright/test";

export const PATIENT = process.env.PATIENT_URL ?? "http://localhost:5173";
export const STAFF = process.env.STAFF_URL ?? "http://localhost:5174/staff/";
export const DEMO_PASSWORD = process.env.DEMO_PASSWORD ?? "bmu-demo-2026";

export function randomMobile(): string {
  return `017${String(Math.floor(Math.random() * 1e8)).padStart(8, "0")}`;
}

/** A tiny but valid PNG (1×1) — enough for the server's image check. */
export const PNG_1PX = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);

/** Sign in to the staff app in a fresh context (demo users without TOTP). */
export async function staffPage(browser: Browser, username: string): Promise<Page> {
  const context = await browser.newContext({ baseURL: STAFF, viewport: { width: 1440, height: 900 }, locale: "en-GB" });
  const page = await context.newPage();
  await page.goto(STAFF);
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(DEMO_PASSWORD);
  await page.locator("#station").fill("E2E desk");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("navigation")).toBeVisible();
  return page;
}

export async function staffToken(page: Page): Promise<string> {
  const token = await page.evaluate(() => window.sessionStorage.getItem("bmu.staff.token"));
  if (!token) throw new Error("no staff token");
  return token;
}
