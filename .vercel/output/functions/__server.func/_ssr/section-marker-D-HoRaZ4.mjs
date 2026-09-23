import { B as require_jsx_runtime } from "../_libs/@tanstack/react-router+[...].mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/section-marker-D-HoRaZ4.js
var import_jsx_runtime = require_jsx_runtime();
function SectionMarker({ label, index }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "flex items-start justify-between gap-4 border-t border-line pt-3 font-mono text-kicker uppercase tracking-[0.14em] text-cyan lg:max-w-36",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: label }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: index })]
	});
}
//#endregion
export { SectionMarker as t };
