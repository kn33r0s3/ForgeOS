import { B as require_jsx_runtime } from "../_libs/@tanstack/react-router+[...].mjs";
import { n as Container } from "./eyebrow-CRXddjtH.mjs";
import { c as processSteps } from "./content-Do6sOcrt.mjs";
import { t as PageHero } from "./page-hero-BZaxG8vo.mjs";
import { t as CtaBand } from "./cta-band-CinmItwG.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/process-DVcg4TDK.js
var import_jsx_runtime = require_jsx_runtime();
function ProcessPage() {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("main", { children: [
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(PageHero, {
			eyebrow: "How we work",
			title: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(import_jsx_runtime.Fragment, { children: [
				"A clear path through",
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("br", {}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
					className: "text-muted",
					children: "the unclear part."
				})
			] }),
			lede: "Understand → Build → Operate → Improve. A public process for shaping useful work without pretending every brief is the same."
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)("section", {
			className: "py-16 sm:py-20",
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Container, {
				className: "max-w-3xl",
				children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "border-t border-line",
					children: processSteps.map((step) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("article", {
						className: "grid grid-cols-[2.75rem_1fr] gap-5 border-b border-line py-7",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "font-mono text-micro text-cyan",
							children: step.number
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
							className: "font-display text-xl font-semibold tracking-tight text-fg",
							children: step.title
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
							className: "mt-2 max-w-lg text-sm leading-relaxed text-muted",
							children: step.body
						})] })]
					}, step.number))
				})
			})
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(CtaBand, {})
	] });
}
//#endregion
export { ProcessPage as component };
