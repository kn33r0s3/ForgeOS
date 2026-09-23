import "../_runtime.mjs";
import { n as require_react } from "../_libs/@radix-ui/react-compose-refs+[...].mjs";
import { B as require_jsx_runtime } from "../_libs/@tanstack/react-router+[...].mjs";
import { t as Slot } from "../_libs/radix-ui__react-slot.mjs";
import { n as clsx, t as cva } from "../_libs/class-variance-authority+clsx.mjs";
import { t as twMerge } from "../_libs/tailwind-merge.mjs";
require_react();
var import_jsx_runtime = require_jsx_runtime();
function cn(...inputs) {
	return twMerge(clsx(inputs));
}
var buttonVariants = cva("inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-nav font-semibold tracking-tight transition-[transform,background-color,color,border-color,box-shadow] duration-150 ease-out disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-cyan/70 focus-visible:ring-offset-2 focus-visible:ring-offset-void active:not-disabled:scale-[0.96]", {
	variants: {
		variant: {
			primary: "bg-fg text-void hover:bg-cyan",
			secondary: "border border-line bg-transparent text-fg hover:border-cyan/40 hover:text-cyan",
			ghost: "text-muted hover:text-cyan",
			amber: "bg-amber text-ink hover:bg-amber/90"
		},
		size: {
			default: "h-11 px-4",
			lg: "h-12 px-5",
			sm: "h-9 px-3 text-micro"
		}
	},
	defaultVariants: {
		variant: "primary",
		size: "default"
	}
});
function Button({ className, variant, size, asChild = false, ...props }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)(asChild ? Slot : "button", {
		className: cn(buttonVariants({
			variant,
			size,
			className
		})),
		...props
	});
}
function Container({ children, className }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
		className: cn("mx-auto w-full max-w-site px-5 sm:px-6 lg:px-8", className),
		children
	});
}
function Eyebrow({ children, className, tone = "cyan" }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
		className: cn("mb-5 flex items-center gap-2 font-mono text-kicker font-medium uppercase tracking-[0.16em]", tone === "amber" ? "text-amber" : tone === "muted" ? "text-dim" : "text-cyan", className),
		children
	});
}
//#endregion
export { cn as i, Container as n, Eyebrow as r, Button as t };
