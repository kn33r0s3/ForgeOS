import { B as require_jsx_runtime, v as Link } from "../_libs/@tanstack/react-router+[...].mjs";
import { n as Container, r as Eyebrow, t as Button } from "./eyebrow-CRXddjtH.mjs";
import { n as SITE } from "./content-Do6sOcrt.mjs";
import { p as ArrowUpRight } from "../_libs/lucide-react.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/contact-BpIseIOS.js
var import_jsx_runtime = require_jsx_runtime();
function ContactPage() {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("main", {
		className: "py-16 sm:py-20 lg:py-24",
		children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Container, {
			className: "grid gap-12 lg:grid-cols-2 lg:gap-20",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Eyebrow, { children: "Contact Sanip Ops" }),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("h1", {
					className: "font-display text-display tracking-tight text-fg",
					children: [
						"Start with the",
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("br", {}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "text-muted",
							children: "situation."
						})
					]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
					className: "mt-6 max-w-md text-lede text-muted",
					children: "For a project, operating question, or conversation about building something useful, start with the context."
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
					asChild: true,
					className: "mt-8",
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Link, {
						to: "/request",
						children: ["Start a Project", /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ArrowUpRight, {})]
					})
				})
			] }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("aside", {
				className: "self-start rounded-xl border border-line bg-surface p-7",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Eyebrow, { children: "Direct line" }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("a", {
						href: `mailto:${SITE.email}`,
						className: "block font-display text-2xl font-semibold tracking-tight text-fg transition-colors duration-150 hover:text-cyan sm:text-3xl",
						children: SITE.email
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-3 text-sm text-muted",
						children: "A direct note before you are ready to scope work."
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", { className: "my-8 h-px bg-line" }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Eyebrow, { children: "Location" }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "text-sm text-muted",
						children: SITE.location
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", { className: "my-8 h-px bg-line" }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Eyebrow, { children: "Entity" }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", {
						className: "text-sm text-muted",
						children: [
							SITE.legalName,
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("br", {}),
							SITE.name,
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("br", {}),
							SITE.domain
						]
					})
				]
			})]
		})
	});
}
//#endregion
export { ContactPage as component };
