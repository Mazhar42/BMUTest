import { expect, test } from "@playwright/test";

import { PNG_1PX, randomMobile, staffPage } from "./helpers";

/** ROADMAP M3 acceptance — online patient: submit → staff verify → patient sees the price and the
 *  preparation text. */
test("online request is verified by staff and the patient sees price and preparation", async ({ page, browser }) => {
  const mobile = randomMobile();

  // Welcome → language → OTP login (mock SMS returns the code in test mode)
  await page.goto("/welcome");
  await page.getByRole("button", { name: "English" }).click();
  await page.locator("#mobile").fill(mobile);
  await page.getByRole("button", { name: "Send code" }).click();
  const code = (await page.getByTestId("dev-code").textContent())!.trim();
  await page.locator("#code").fill(code);
  await page.getByRole("button", { name: "Verify & continue" }).click();

  // Home: three buttons → Book a Test → "Who is this for?" → myself
  await expect(page.getByTestId("home-book")).toBeVisible();
  await page.getByTestId("home-book").click();
  await page.getByTestId("add-self").click();
  await page.getByTestId("family-name").fill("Rahima Begum");
  await page.getByTestId("family-age").fill("34");
  await page.getByTestId("family-save").click();

  // Prescription photo → tests → review → submit
  await page.getByTestId("photo-input").setInputFiles({ name: "rx.png", mimeType: "image/png", buffer: PNG_1PX });
  await page.getByTestId("book-next").click();
  await page.getByTestId("patient-test-search").fill("fasting blood sugar");
  await page.getByTestId("patient-test-option").first().click();
  await page.getByTestId("patient-test-search").fill("s creat");
  await page.getByTestId("patient-test-option").filter({ hasText: "Serum Creatinine" }).click();
  await page.getByTestId("book-next").click();
  await page.getByTestId("book-submit").click();

  await expect(page.getByRole("status").getByText("Request submitted")).toBeVisible();
  await expect(page.getByText("Waiting for verification")).toBeVisible();
  const orderCode = (await page.getByTestId("order-code").innerText()).replace(/\D/g, "");
  expect(orderCode).toMatch(/^\d{12}$/);

  // Staff: verification queue → open → confirm
  const staff = await staffPage(browser, "verifier");
  await staff.goto("verification");
  const dashed = `${orderCode.slice(0, 6)}-${orderCode.slice(6, 11)}-${orderCode.slice(11)}`;
  await staff.getByTestId("queue-row").filter({ hasText: dashed }).click();
  await expect(staff.getByText("Page 1")).toBeVisible();
  await staff.getByTestId("verify-confirm").click();
  await expect(staff.getByText("Verified — the patient has been told the amount")).toBeVisible();
  await staff.context().close();

  // Patient: verified order with the final price and the preparation instructions
  await page.reload();
  await expect(page.getByText("Awaiting payment").first()).toBeVisible();
  await expect(page.getByTestId("order-total")).toHaveText("৳450");
  const fbs = page.getByTestId("order-item").filter({ hasText: "Fasting Blood Sugar" });
  await expect(fbs.getByTestId("item-price")).toHaveText("৳150");
  await expect(fbs.getByText("Come fasting (8 hours)")).toBeVisible();
  await expect(fbs.getByTestId("item-prep")).toContainText("preparation instructions");
  await expect(page.getByText("Amount to pay: ৳450")).toBeVisible();
});
