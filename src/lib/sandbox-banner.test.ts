import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { sandboxBannerHtml } from "./sandbox-banner.ts";

describe("sandbox banner", () => {
  it("renders SANDBOX in big letters", () => {
    const html = sandboxBannerHtml();
    assert.ok(html.includes("SANDBOX"));
    assert.ok(html.includes("font-size:32px"));
    assert.ok(html.includes("letter-spacing:6px"));
  });

  it("states the data is pretend and not real traction", () => {
    const html = sandboxBannerHtml();
    assert.ok(html.toLowerCase().includes("pretend"));
    assert.ok(html.toLowerCase().includes("not"));
    assert.ok(html.toLowerCase().includes("real traction"));
  });

  it("includes optional context and escapes HTML", () => {
    const html = sandboxBannerHtml({ context: "Revenue <lab>" });
    assert.ok(html.includes("Revenue &lt;lab&gt;"));
    assert.ok(!html.includes("<lab>"));
  });
});
