// Renovation Phase 4: SANDBOX banner.
//
// Any private page or tool that displays SANDBOX (test/mock/hypothesis)
// data must say so loudly, so nobody mistakes pretend numbers for real
// traction. This module is the reusable piece: sandboxBannerHtml() returns
// the banner markup; a page drops it above its content. Framework-free so
// it can be used from React, plain HTML, or server-rendered pages.

export interface SandboxBannerOptions {
  /** Extra context, e.g. "Revenue lab" or "Experiment #12 rehearsal". */
  context?: string;
}

const BASE_STYLE = [
  "display:block",
  "width:100%",
  "box-sizing:border-box",
  "padding:14px 18px",
  "margin:0 0 16px 0",
  "background:#3a2a00",
  "border:3px solid #f5a623",
  "border-radius:10px",
  "color:#ffd98a",
  "font-family:inherit",
  "text-align:center",
].join(";");

const TITLE_STYLE = [
  "font-size:32px",
  "font-weight:800",
  "letter-spacing:6px",
  "line-height:1.2",
].join(";");

const SUB_STYLE = [
  "font-size:13px",
  "margin-top:6px",
  "color:#ffe9bd",
].join(";");

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function sandboxBannerHtml(options: SandboxBannerOptions = {}): string {
  const sub = options.context
    ? `Pretend data only — ${options.context}. Nothing here counts as real traction.`
    : "Pretend data only. Nothing here counts as real traction.";
  return (
    `<div role="note" aria-label="Sandbox data warning" style="${BASE_STYLE}">` +
    `<div style="${TITLE_STYLE}">SANDBOX</div>` +
    `<div style="${SUB_STYLE}">${escapeHtml(sub)}</div>` +
    `</div>`
  );
}
