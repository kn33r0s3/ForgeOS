import { B as require_jsx_runtime } from "../_libs/@tanstack/react-router+[...].mjs";
import { i as cn, n as Container, r as Eyebrow } from "./eyebrow-CRXddjtH.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/page-hero-BZaxG8vo.js
var import_jsx_runtime = require_jsx_runtime();
function PageHero({ eyebrow, title, lede, children, className }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("section", {
		className: cn("border-b border-line py-16 sm:py-20 lg:py-24", className),
		children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Container, {
			className: "max-w-3xl",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Eyebrow, { children: eyebrow }),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h1", {
					className: "font-display text-display tracking-tight text-fg",
					children: title
				}),
				lede ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
					className: "mt-6 max-w-xl text-lede text-muted",
					children: lede
				}) : null,
				children
			]
		})
	});
}
//#endregion
export { PageHero as t };
