import { B as require_jsx_runtime } from "../_libs/@tanstack/react-router+[...].mjs";
import { n as Container, r as Eyebrow } from "./eyebrow-CRXddjtH.mjs";
import { a as getGroupArea } from "./content-Do6sOcrt.mjs";
import { t as PageHero } from "./page-hero-BZaxG8vo.mjs";
import { t as CtaBand } from "./cta-band-CinmItwG.mjs";
import { t as TextLink } from "./text-link-CHIRVWe-.mjs";
import { t as StatusPill } from "./status-pill-BSs9QqO8.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/area-view-Cce8jYyt.js
var import_jsx_runtime = require_jsx_runtime();
function AreaView({ name }) {
	const area = getGroupArea(name);
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(import_jsx_runtime.Fragment, { children: [
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(PageHero, {
			eyebrow: `Strategic area / ${name}`,
			title: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(import_jsx_runtime.Fragment, { children: [
				name,
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("br", {}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
					className: "text-muted",
					children: "is building."
				})
			] }),
			lede: `${area?.description ?? ""} This is a long-term direction for Sanip Ops, not a claim that a separate subsidiary or operating company exists today.`,
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatusPill, {
				tone: "amber",
				children: "Long-term direction"
			})
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)("section", {
			className: "py-16 sm:py-20",
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Container, {
				className: "max-w-2xl",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Eyebrow, { children: "Current status" }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
						className: "font-display text-title tracking-tight text-fg",
						children: "Direction before declaration."
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-4 text-sm leading-relaxed text-muted",
						children: "Sanip Ops will only describe a business area as active when there is clear evidence of an operating business behind it. Until then, the work is to learn, build carefully, and keep the distinction visible."
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "mt-6",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(TextLink, {
							to: "/group/businesses",
							children: "See what is available today"
						})
					})
				]
			})
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(CtaBand, {})
	] });
}
//#endregion
export { AreaView as t };
