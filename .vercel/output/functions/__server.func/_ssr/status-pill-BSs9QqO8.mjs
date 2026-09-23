import { B as require_jsx_runtime } from "../_libs/@tanstack/react-router+[...].mjs";
import { i as cn } from "./eyebrow-CRXddjtH.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/status-pill-BSs9QqO8.js
var import_jsx_runtime = require_jsx_runtime();
function StatusPill({ children, tone = "cyan" }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
		className: cn("mt-7 inline-flex items-center border px-3 py-2 font-mono text-micro uppercase tracking-[0.14em]", tone === "amber" ? "border-amber/40 text-amber" : "border-cyan/40 text-cyan"),
		children
	});
}
//#endregion
export { StatusPill as t };
