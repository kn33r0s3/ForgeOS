// Browser QA for the Hami System home. Usage: node scripts/qa-system.mjs [baseUrl]
// Drives the real flow and writes screenshots to screenshots/qa-*.png.
import { chromium } from "playwright";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { checkedOutputPath, checkedUrl } from "./browser-guard.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SCREENSHOTS_DIR = join(ROOT, "screenshots");
const base = checkedUrl(process.argv[2] ?? "http://127.0.0.1:8080");
const out = (n) =>
  checkedOutputPath(join(SCREENSHOTS_DIR, `qa-${n}.png`), [SCREENSHOTS_DIR]);
const errors = [];

const browser = await chromium.launch();
try {
for (const [label, viewport] of [
  ["desktop", { width: 1440, height: 1000 }],
  ["mobile", { width: 390, height: 844 }],
]) {
  const page = await browser.newPage({ viewport });
  page.on("pageerror", (e) => errors.push(`${label} pageerror: ${e.message}`));
  page.on("console", (m) => m.type() === "error" && errors.push(`${label} console: ${m.text()}`));

  // Privacy: System state must never be sent to the server. Registered before
  // the first navigation so the whole flow — including the form submission —
  // is observed, not just the /system page at the end.
  const leaked = [];
  page.on("request", (r) => {
    const body = r.postData() ?? "";
    if (/shop shutter|electrical wiring/i.test(body + r.url())) leaked.push(r.url());
  });

  await page.goto(base, { waitUntil: "networkidle" });
  await page.getByText("A System around you").waitFor({ timeout: 20000 });
  await page.screenshot({ path: out(`${label}-1-welcome`), fullPage: true });

  const form = page.locator("#start");
  await form.getByPlaceholder("Town or district").fill("Pokhara");
  await form.locator("select").selectOption("5_to_15h");
  await form.getByRole("button", { name: "Earn more" }).click();
  await form.getByRole("button", { name: "Grow a useful skill" }).click();
  await form.getByPlaceholder(/wiring, driving/).fill("electrical wiring, English, driving");
  await form.getByPlaceholder(/motorbike, empty room/).fill("motorbike, empty shop shutter, laptop");
  await form.getByRole("button", { name: /Update my System/ }).click();

  await page.getByText("System active").waitFor({ timeout: 10000 });
  await page.waitForTimeout(800);
  await page.screenshot({ path: out(`${label}-2-active`), fullPage: true });

  const heading = await page.locator("h1").first().innerText();
  if (!/possible path/.test(heading)) errors.push(`${label}: unexpected heading ${heading}`);

  // Persistence: reload keeps the System (local-only ownership).
  await page.reload({ waitUntil: "networkidle" });
  await page.getByText("System active").waitFor({ timeout: 10000 });

  await page.goto(`${base}/system`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Your gear" }).waitFor();
  await page.screenshot({ path: out(`${label}-3-gear`), fullPage: true });
  if (leaked.length) errors.push(`${label}: system state leaked to ${leaked.join(", ")}`);

  // Clear -> welcome again.
  await page.getByRole("button", { name: "Clear my System" }).click();
  await page.getByRole("button", { name: "Yes, clear it" }).click();
  await page.goto(base, { waitUntil: "networkidle" });
  await page.getByText("A System around you").waitFor();
  await page.close();
}
} finally {
  await browser.close();
}

// Ignore expected network failures when the public API isn't running locally.
const real = errors.filter((e) => !/Failed to load resource|ERR_CONNECTION|404|502|503/.test(e));
console.log(JSON.stringify({ ok: real.length === 0, errors: real, ignored: errors.length - real.length }, null, 2));
process.exit(real.length ? 1 : 0);
