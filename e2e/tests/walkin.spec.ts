import { expect, test } from "@playwright/test";

import { DEMO_PASSWORD, randomMobile, staffToken } from "./helpers";

/** ROADMAP M3 acceptance — help desk walk-in: register → tests → inline verification → AWAITING_PAYMENT
 *  → 3-part slip PDF. (Barcode decoding of the slip is asserted in backend/tests/pdf/test_slip.py.) */
test("help desk creates a walk-in order and prints the slip", async ({ page }) => {
  await page.goto("");
  await page.locator("#username").fill("helpdesk");
  await page.locator("#password").fill(DEMO_PASSWORD);
  await page.locator("#station").fill("Help desk 1");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("navigation")).toBeVisible();

  await page.goto("helpdesk");
  // Register a new patient (unique name/mobile so no duplicate warning)
  const name = `Walkin ${Date.now().toString(36)}`;
  await page.getByRole("button", { name: "Register patient" }).click();
  await page.getByTestId("reg-name").fill(name);
  await page.getByTestId("reg-mobile").fill(randomMobile());
  await page.getByTestId("reg-age").fill("58");
  await page.getByRole("dialog").getByRole("button", { name: "Register patient" }).click();
  await expect(page.getByTestId("picked-patient")).toHaveText(name);

  // Tests by alias, inline verification
  await page.getByTestId("test-search").fill("CBC");
  await page.getByRole("button", { name: /Complete Blood Count/ }).click();
  await page.getByTestId("test-search").fill("s creat");
  await page.getByRole("button", { name: /Serum Creatinine/ }).click();
  await expect(page.getByTestId("selected-tests").locator("li")).toHaveCount(2);

  const slip = page.waitForResponse((r) => r.url().includes("/slip") && r.request().method() === "POST");
  await page.getByTestId("create-walkin").click();
  const response = await slip;
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toBe("application/pdf");

  const code = (await page.getByTestId("created-code").innerText()).replace(/\D/g, "");
  expect(code).toMatch(/^\d{12}$/);

  // The order is awaiting payment and the slip was printed once (a reprint is watermarked)
  const token = await staffToken(page);
  const order = await page.request.get(`/api/v1/staff/orders/${code}`, { headers: { Authorization: `Bearer ${token}` } });
  const body = await order.json();
  expect(body.status).toBe("AWAITING_PAYMENT");
  expect(body.channel).toBe("HELPDESK");
  expect(body.total).toBe(70000);
  expect(body.slip_print_count).toBe(1);
  const pdf = await page.request.post(`/api/v1/staff/orders/${body.id}/slip`, { headers: { Authorization: `Bearer ${token}` } });
  expect((await pdf.body()).subarray(0, 4).toString()).toBe("%PDF");
});
