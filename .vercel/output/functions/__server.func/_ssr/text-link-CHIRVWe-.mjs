import { B as require_jsx_runtime, v as Link } from "../_libs/@tanstack/react-router+[...].mjs";
import { i as cn } from "./eyebrow-CRXddjtH.mjs";
import { p as ArrowUpRight } from "../_libs/lucide-react.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/text-link-CHIRVWe-.js
var import_jsx_runtime = require_jsx_runtime();
function TextLink({ to, children, className, onClick }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Link, {
		to,
		onClick,
		className: cn("inline-flex items-center gap-1.5 text-nav font-semibold text-cyan transition-colors duration-150 hover:text-fg", className),
		children: [children, /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ArrowUpRight, { className: "size-3.5" })]
	});
}
//#endregion
export { TextLink as t };
