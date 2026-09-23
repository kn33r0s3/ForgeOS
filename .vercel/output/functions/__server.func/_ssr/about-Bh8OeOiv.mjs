import { B as require_jsx_runtime, v as Link } from "../_libs/@tanstack/react-router+[...].mjs";
import { n as Container, t as Button } from "./eyebrow-CRXddjtH.mjs";
import { p as ArrowUpRight } from "../_libs/lucide-react.mjs";
import { t as PageHero } from "./page-hero-BZaxG8vo.mjs";
import { t as CtaBand } from "./cta-band-CinmItwG.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/about-Bh8OeOiv.js
var import_jsx_runtime = require_jsx_runtime();
var items = [
	{
		number: "01",
		title: "The parent",
		body: "Sanip Operations is the parent identity. Future group areas are strategic directions, not a claim that subsidiaries or operating companies already exist."
	},
	{
		number: "02",
		title: "The operating core",
		body: "ForgeOS is Sanip Ops’ long-term local-first internal intelligence, operations, and business-software engine. It is not connected to this website today."
	},
	{
		number: "03",
		title: "The standard",
		body: "No invented subsidiaries, clients, revenues, acquisitions, employees, investments, awards, partnerships, or market share are presented."
	}
];
function AboutPage() {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("main", { children: [
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(PageHero, {
			eyebrow: "Sanip Ops / Sanip Operations",
			title: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(import_jsx_runtime.Fragment, { children: [
				"A parent platform",
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("br", {}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
					className: "text-muted",
					children: "for useful work."
				})
			] }),
			lede: "Sanip Ops is the long-term parent business group being built from Nepal: a platform to build, own, operate, invest in, and scale useful businesses, technologies, products, infrastructure, and ventures over time.",
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
				asChild: true,
				className: "mt-8",
				children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Link, {
					to: "/request",
					children: ["Start a Project", /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ArrowUpRight, {})]
				})
			})
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)("section", {
			className: "py-16 sm:py-20",
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Container, {
				className: "max-w-3xl",
				children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "border-t border-line",
					children: items.map((item) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("article", {
						className: "grid grid-cols-[2.75rem_1fr] gap-5 border-b border-line py-7",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "font-mono text-micro text-cyan",
							children: item.number
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
							className: "font-display text-xl font-semibold tracking-tight text-fg",
							children: item.title
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
							className: "mt-2 max-w-lg text-sm leading-relaxed text-muted",
							children: item.body
						})] })]
					}, item.number))
				})
			})
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(CtaBand, {})
	] });
}
//#endregion
export { AboutPage as component };
