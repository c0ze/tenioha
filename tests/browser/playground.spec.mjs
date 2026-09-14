import { test, expect } from "@playwright/test";

test.describe.serial("Tenioha in a real browser", () => {
  let page;
  let failures;
  const expensive = `関数 遅い (数:整数)を -> 整数 {
    もし (数 と 0が 等しい) なら { 1 }
    そうでなければ {
      (( (数 から 1を 引く)を 遅い)に ((数 から 1を 引く)を 遅い)を 足す)
    }
  } (40を 遅い)`;

  test.beforeAll(async ({ browser, baseURL }) => {
    page = await browser.newPage({ baseURL });
    failures = [];
    page.on("pageerror", (error) => failures.push(error.message));
    await page.goto("./");
    await expect(page.locator("#run")).toBeEnabled();
  });
  test.afterAll(async () => {
    await page?.close();
  });

  async function run(source, check = false) {
    if (source !== undefined) await page.locator("#source").fill(source);
    await page.locator(check ? "#check" : "#run").click();
    await expect(page.locator("#run")).toBeEnabled({ timeout: 70_000 });
  }

  test("all bundled examples run through the real interpreter", async () => {
    const catalog = await page.evaluate(async () =>
      (await fetch("./examples.json")).json(),
    );
    expect(catalog).toHaveLength(23);
    for (const example of catalog) {
      await page.locator("#example").selectOption(example.id);
      await run();
      await expect(page.locator("#error"), example.id).toBeHidden();
      await expect(page.locator("#output"), example.id).toHaveText(
        example.expected,
      );
    }
  });

  test("checks prevent I/O and errors recover without stale bindings", async () => {
    await run("(読む)(「hidden」を 表示する)(1を 0で 割る)", true);
    await expect(page.locator("#output")).toContainText(
      "No program code was executed",
    );
    await run("(「early」を 表示する)(3に 5に 足す)");
    await expect(page.locator("#error")).toContainText("E_ARGUMENTS");
    await expect(page.locator("#output")).toBeEmpty();
    await run("(「early」を 表示する)(1を 0で 割る)");
    await expect(page.locator("#output")).toHaveText("early\n");
    await expect(page.locator("#error")).toContainText("E_ZERO_DIVISION");
    await run("値 は 7。値");
    await expect(page.locator("#output")).toHaveText("7\n");
    await run("値");
    await expect(page.locator("#error")).toContainText("E_NAME");
  });

  test("input, EOF, reset, and HTML-like output are handled as text", async () => {
    await page.locator("#example").selectOption("greeting");
    await page.locator("#stdin").fill("花子\n");
    await run();
    await expect(page.locator("#output")).toHaveText("こんにちは、花子\n");
    await page.locator("#stdin").fill("");
    await run();
    await expect(page.locator("#error")).toContainText("E_IO");
    await page.locator("#reset").click();
    await expect(page.locator("#stdin")).toHaveValue("Ada\n");
    await run("「<img src=x onerror=alert(1)>」");
    await expect(page.locator("#output")).toHaveText(
      "<img src=x onerror=alert(1)>\n",
    );
    await expect(page.locator("#output img")).toHaveCount(0);
  });

  test("Stop terminates a busy worker and a subsequent run works", async () => {
    await page.locator("#source").fill(expensive);
    await page.locator("#run").click();
    await expect(page.locator("#runtime-status")).toHaveText("Running…");
    await page.locator("#stop").click();
    await expect(page.locator("#run")).toBeEnabled();
    await expect(page.locator("#error")).toContainText("Stopped.");
    await expect(page.locator("#source")).toHaveValue(expensive);
    await run("(5から 3を 引く)");
    await expect(page.locator("#output")).toHaveText("2\n");
  });

  test("time and output limits preserve a usable page", async () => {
    await run(expensive);
    await expect(page.locator("#error")).toContainText(
      "Stopped after 10 seconds",
    );
    await run("(「" + "x".repeat(64_000) + "」を 表示する)");
    await expect(page.locator("#error")).toContainText("64,000");
    expect((await page.locator("#output").textContent()).length).toBe(64_000);
    await run("42");
    await expect(page.locator("#output")).toHaveText("42\n");
  });

  test("keyboard focus reaches Stop and returns without interrupting editor composition", async () => {
    await page.locator("#source").fill(expensive);
    await page.locator("#run").focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("#stop")).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("#run")).toBeFocused();
    await expect(page.locator("#error")).toContainText("Stopped.");
    await page.locator("#source").fill("42");
    await page.locator("#check").focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("#check")).toBeEnabled({ timeout: 70_000 });
    await expect(page.locator("#check")).toBeFocused();
    await page.locator("#source").focus();
    await page.locator("#source").dispatchEvent("keydown", {
      key: "Enter", ctrlKey: true, isComposing: true,
    });
    await expect(page.locator("#stop")).toBeHidden();
    await page.keyboard.press("Control+Enter");
    await expect(page.locator("#run")).toBeEnabled({ timeout: 70_000 });
    await expect(page.locator("#source")).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.locator("#source")).not.toBeFocused();
  });

  test("example links, argument swap, keyboard shortcut, and download work", async () => {
    await page.locator('[data-example="fizzbuzz"]').click();
    await expect(page.locator("#example")).toHaveValue("fizzbuzz");
    await expect(page).toHaveURL(/#example=fizzbuzz$/);
    const before = await page.locator(".call-demo").textContent();
    await page.locator("#swap").click();
    expect(await page.locator(".call-demo").textContent()).not.toBe(before);
    await expect(page.locator(".demo-result")).toHaveText("2");
    await page.locator("#source").fill("(3を 5から 引く)");
    await page.locator("#source").press("Control+Enter");
    await expect(page.locator("#run")).toBeEnabled();
    await expect(page.locator("#output")).toHaveText("2\n");
    const downloadPromise = page.waitForEvent("download");
    await page.locator("#download").click();
    expect((await downloadPromise).suggestedFilename()).toBe("fizzbuzz.ten");
  });

  test("mobile and desktop layouts have no page overflow or script errors", async () => {
    for (const width of [360, 390, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        `width ${width}`,
      ).toBe(true);
      await expect(page.locator("#source")).toBeVisible();
      await expect(page.locator("#example")).toHaveAccessibleName("EXAMPLE");
      await expect(page.locator("#download")).toHaveAccessibleName("Download .ten");
    }
    expect(failures).toEqual([]);
  });
});

test("runtime download failure leaves a useful retry", async ({ page }) => {
  await page.route("**/runtime.json", (route) => route.abort());
  await page.goto("./");
  await expect(page.locator("#run")).toBeEnabled();
  await page.locator("#run").click();
  await expect(page.locator("#error")).toContainText("Could not prepare");
  await expect(page.locator("#run")).toBeEnabled();
  await expect(page.locator("#source")).not.toHaveValue("");
  await page.unroute("**/runtime.json");
  await page.locator("#source").fill("42");
  await page.locator("#run").click();
  await expect(page.locator("#run")).toBeEnabled({ timeout: 70_000 });
  await expect(page.locator("#output")).toHaveText("42\n");
});
