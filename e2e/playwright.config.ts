import { defineConfig, devices } from "@playwright/test";

/** Golden paths (ROADMAP §12). Needs the API stack running (`make up && make migrate && make seed`);
 *  the two Vite dev servers are started here unless already running. */
const PATIENT = process.env.PATIENT_URL ?? "http://localhost:5173";
const STAFF = process.env.STAFF_URL ?? "http://localhost:5174/staff/";
const external = !!process.env.PATIENT_URL;

export default defineConfig({
  testDir: "tests",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "en-GB",
    timezoneId: "Asia/Dhaka",
  },
  metadata: { PATIENT, STAFF },
  projects: [
    { name: "patient", use: { ...devices["Pixel 7"], baseURL: PATIENT }, testMatch: /online\.spec\.ts/ },
    { name: "staff", use: { ...devices["Desktop Chrome"], baseURL: STAFF }, testMatch: /walkin\.spec\.ts/ },
  ],
  webServer: external
    ? undefined
    : [
        { command: "pnpm --dir ../frontend --filter @bmu/patient dev", url: PATIENT, reuseExistingServer: true, timeout: 120_000 },
        { command: "pnpm --dir ../frontend --filter @bmu/staff dev", url: STAFF, reuseExistingServer: true, timeout: 120_000 },
      ],
});
