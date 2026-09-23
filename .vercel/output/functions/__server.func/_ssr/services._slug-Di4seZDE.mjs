import { B as require_jsx_runtime, v as Link } from "../_libs/@tanstack/react-router+[...].mjs";
import { n as Container, r as Eyebrow, t as Button } from "./eyebrow-CRXddjtH.mjs";
import { f as Check, p as ArrowUpRight } from "../_libs/lucide-react.mjs";
import { n as Route } from "./router-jwkpWJNm.mjs";
import { t as CtaBand } from "./cta-band-CinmItwG.mjs";
import { t as TextLink } from "./text-link-CHIRVWe-.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/services._slug-Di4seZDE.js
var import_jsx_runtime = require_jsx_runtime();
function ServicePage() {
	const { service } = Route.useLoaderData();
	const sections = [
		["The problem", service.problem],
		["What Sanip Ops does", service.does],
		["What is delivered", service.deliverable],
		["How the process works", service.process],
		["Who it is for", service.forWho]
	];
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("main", { children: [
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)("section", {
			className: "border-b border-line py-16 sm:py-20 lg:py-24",
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Container, {
				className: "grid items-end gap-10 lg:grid-cols-[1.15fr_0.85fr]",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Eyebrow, { children: ["Service / ", service.slug] }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h1", {
						className: "max-w-3xl font-display text-display tracking-tight text-fg",
						children: service.title
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-6 max-w-xl text-lede text-muted",
						children: service.short
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
						asChild: true,
						className: "mt-8",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Link, {
							to: "/request",
							children: ["Start a Project", /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ArrowUpRight, {})]
						})
					})
				] }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "flex min-h-48 flex-col justify-between rounded-xl bg-fg p-6 text-void shadow-[8px_8px_0_rgb(0_0_0_/_0.28)]",
					children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "font-mono text-micro uppercase tracking-[0.12em] opacity-60",
							children: "01—06"
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("strong", {
							className: "font-display text-2xl font-semibold tracking-tight",
							children: [
								"Focused work.",
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("br", {}),
								"Clear ownership."
							]
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("small", {
							className: "font-mono text-micro uppercase tracking-[0.12em] opacity-60",
							children: "Sanip Operations · Nepal"
						})
					]
				})]
			})
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)("section", {
			className: "py-16 sm:py-20",
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Container, {
				className: "grid gap-12 lg:grid-cols-[1fr_1.25fr] lg:gap-20",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Eyebrow, { children: "A useful scope" }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
					className: "max-w-md font-display text-title tracking-tight text-fg",
					children: "Good systems begin with the work, not the tool."
				})] }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "border-t border-line",
					children: [sections.map(([title, body], index) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("article", {
						className: "grid grid-cols-[2.75rem_1fr] gap-4 border-b border-line py-6",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "font-mono text-micro text-cyan",
							children: String(index + 1).padStart(2, "0")
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h3", {
							className: "font-display text-lg font-semibold tracking-tight text-fg",
							children: title
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
							className: "mt-2 max-w-xl text-sm leading-relaxed text-muted",
							children: body
						})] })]
					}, title)), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("article", {
						className: "mt-6 flex gap-4 rounded-xl border border-cyan/25 bg-cyan-dim p-5",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Check, { className: "mt-0.5 size-4 shrink-0 text-cyan" }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h3", {
								className: "font-display text-lg font-semibold tracking-tight text-fg",
								children: "What happens next"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
								className: "mt-2 text-sm leading-relaxed text-muted",
								children: service.next
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
								className: "mt-4",
								children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(TextLink, {
									to: "/request",
									children: "Share the situation"
								})
							})
						] })]
					})]
				})]
			})
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(CtaBand, {})
	] });
}
//#endregion
export { ServicePage as component };
