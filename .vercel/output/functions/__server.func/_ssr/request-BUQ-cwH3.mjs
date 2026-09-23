import { i as __toESM } from "../_runtime.mjs";
import { n as require_react } from "../_libs/@radix-ui/react-compose-refs+[...].mjs";
import { B as require_jsx_runtime } from "../_libs/@tanstack/react-router+[...].mjs";
import { i as cn, n as Container, r as Eyebrow, t as Button } from "./eyebrow-CRXddjtH.mjs";
import { d as timelines, l as projectTypes, n as SITE } from "./content-Do6sOcrt.mjs";
import { f as Check, p as ArrowUpRight } from "../_libs/lucide-react.mjs";
import { a as string, i as object, t as boolean } from "../_libs/zod.mjs";
import { t as TextLink } from "./text-link-CHIRVWe-.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/request-BUQ-cwH3.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
function Input({ className, type, ...props }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
		type,
		className: cn("h-11 w-full rounded-md border border-line bg-void px-3 text-sm text-fg outline-none transition-[border-color,box-shadow] duration-150 placeholder:text-dim focus-visible:border-cyan focus-visible:shadow-[var(--shadow-glow)] disabled:opacity-50", className),
		...props
	});
}
function Label({ className, ...props }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("label", {
		className: cn("mb-2 block text-xs font-semibold tracking-tight text-fg", className),
		...props
	});
}
function Textarea({ className, ...props }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("textarea", {
		className: cn("min-h-28 w-full resize-y rounded-md border border-line bg-void px-3 py-2.5 text-sm text-fg outline-none transition-[border-color,box-shadow] duration-150 placeholder:text-dim focus-visible:border-cyan focus-visible:shadow-[var(--shadow-glow)] disabled:opacity-50", className),
		...props
	});
}
var schema = object({
	name: string().trim().min(2, "Name is required.").max(120),
	company: string().trim().max(160).optional(),
	email: string().trim().email("A valid email is required."),
	phone: string().trim().max(40).optional(),
	projectType: string().refine((value) => projectTypes.includes(value), "Choose what you are exploring."),
	problem: string().trim().min(12, "Give us a little more context.").max(4e3),
	timeline: string().trim().max(40).optional(),
	details: string().trim().max(2e3).optional(),
	consent: boolean().refine((value) => value, "Consent is required to send this inquiry.")
});
var selectClass = "h-11 w-full rounded-md border border-line bg-void px-3 text-sm text-fg outline-none transition-[border-color,box-shadow] duration-150 focus-visible:border-cyan focus-visible:shadow-[var(--shadow-glow)]";
function buildMailto(values) {
	const lines = [
		`Name: ${values.name}`,
		`Email: ${values.email}`,
		values.company ? `Company: ${values.company}` : null,
		values.phone ? `Phone: ${values.phone}` : null,
		`Exploring: ${values.projectType}`,
		values.timeline ? `Timeline: ${values.timeline}` : null,
		"",
		"Context:",
		values.problem,
		values.details ? `\nNotes:\n${values.details}` : null
	].filter((line) => line !== null);
	const subject = encodeURIComponent(`Sanip Ops inquiry — ${values.projectType}`);
	const body = encodeURIComponent(lines.join("\n"));
	return `mailto:${SITE.email}?subject=${subject}&body=${body}`;
}
function ProjectForm() {
	const [submitted, setSubmitted] = (0, import_react.useState)(false);
	const [errors, setErrors] = (0, import_react.useState)({});
	const [mailto, setMailto] = (0, import_react.useState)(null);
	const checks = (0, import_react.useMemo)(() => [
		"A human review of every request",
		"Clear scope before any build",
		"No unsupported promises"
	], []);
	function onSubmit(event) {
		event.preventDefault();
		const form = event.currentTarget;
		const data = Object.fromEntries(new FormData(form).entries());
		if (String(data.hp_field || "").trim()) {
			setSubmitted(true);
			return;
		}
		const parsed = schema.safeParse({
			name: data.name,
			company: data.company || void 0,
			email: data.email,
			phone: data.phone || void 0,
			projectType: data.projectType,
			problem: data.problem,
			timeline: data.timeline || void 0,
			details: data.details || void 0,
			consent: data.consent === "on"
		});
		if (!parsed.success) {
			const next = {};
			for (const issue of parsed.error.issues) {
				const key = issue.path[0];
				if (typeof key === "string" && !next[key]) next[key] = issue.message;
			}
			setErrors(next);
			return;
		}
		setErrors({});
		const href = buildMailto(parsed.data);
		setMailto(href);
		setSubmitted(true);
	}
	if (submitted) return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "flex min-h-96 flex-col justify-center rounded-xl border border-line bg-surface p-8",
		children: [
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
				className: "mb-6 grid size-10 place-items-center rounded-full bg-fg text-void",
				children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Check, { className: "size-5" })
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
				className: "font-mono text-kicker uppercase tracking-[0.16em] text-cyan",
				children: "Request prepared"
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h3", {
				className: "mt-3 font-display text-3xl font-semibold tracking-tight text-fg",
				children: "That’s a useful first step."
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", {
				className: "mt-3 max-w-md text-sm leading-relaxed text-muted",
				children: [
					"Nothing is stored on our servers from this page. Open your email client to send the inquiry directly to ",
					SITE.email,
					"."
				]
			}),
			mailto ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
				asChild: true,
				className: "mt-6 w-fit",
				children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("a", {
					href: mailto,
					children: ["Open email client", /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ArrowUpRight, {})]
				})
			}) : null,
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
				className: "mt-6",
				children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(TextLink, {
					to: "/",
					children: "Back to home"
				})
			})
		]
	});
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "rounded-xl border border-line bg-surface p-5 sm:p-8",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("form", {
			className: "grid gap-5",
			onSubmit,
			noValidate: true,
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "sr-only",
					"aria-hidden": "true",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("label", {
						htmlFor: "hp_field",
						children: "Leave this field empty"
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
						id: "hp_field",
						name: "hp_field",
						tabIndex: -1,
						autoComplete: "off"
					})]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "grid gap-5 sm:grid-cols-2",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Field, {
						id: "name",
						label: "Name",
						required: true,
						error: errors.name,
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Input, {
							id: "name",
							name: "name",
							placeholder: "Your name",
							autoComplete: "name"
						})
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Field, {
						id: "company",
						label: "Company or venture",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Input, {
							id: "company",
							name: "company",
							placeholder: "Company, venture, or team"
						})
					})]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "grid gap-5 sm:grid-cols-2",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Field, {
						id: "email",
						label: "Email",
						required: true,
						error: errors.email,
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Input, {
							id: "email",
							name: "email",
							type: "email",
							placeholder: "you@company.com",
							autoComplete: "email"
						})
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Field, {
						id: "phone",
						label: "Phone",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Input, {
							id: "phone",
							name: "phone",
							placeholder: "Optional",
							autoComplete: "tel"
						})
					})]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Field, {
					id: "projectType",
					label: "What are you exploring?",
					required: true,
					error: errors.projectType,
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("select", {
						id: "projectType",
						name: "projectType",
						defaultValue: "",
						className: selectClass,
						required: true,
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("option", {
							value: "",
							disabled: true,
							children: "Select one"
						}), projectTypes.map((item) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)("option", {
							value: item,
							children: item
						}, item))]
					})
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Field, {
					id: "problem",
					label: "What should we understand first?",
					required: true,
					error: errors.problem,
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Textarea, {
						id: "problem",
						name: "problem",
						placeholder: "Describe the business need, opportunity, or question."
					})
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "grid gap-5 sm:grid-cols-2",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Field, {
						id: "timeline",
						label: "Timeline",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("select", {
							id: "timeline",
							name: "timeline",
							defaultValue: "",
							className: selectClass,
							children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("option", {
								value: "",
								children: "Choose a range"
							}), timelines.map((item) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)("option", {
								value: item,
								children: item
							}, item))]
						})
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Field, {
						id: "details",
						label: "Anything else?",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Input, {
							id: "details",
							name: "details",
							placeholder: "Links, constraints, context"
						})
					})]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
					className: "flex items-start gap-3 text-sm leading-relaxed text-muted",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
						id: "consent",
						name: "consent",
						type: "checkbox",
						className: "mt-1 size-4 shrink-0 accent-cyan"
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "I agree to Sanip Operations using this information to respond to my conversation request." })]
				}),
				errors.consent ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
					className: "text-xs text-amber",
					children: errors.consent
				}) : null,
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
					type: "submit",
					className: "w-full sm:w-auto",
					children: ["Start the conversation", /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ArrowUpRight, {})]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
					className: "font-mono text-micro text-dim",
					children: "Your details are used only to compose this inquiry. No automatic outreach is triggered, and nothing is stored on our servers from this page."
				})
			]
		}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("ul", {
			className: "mt-8 hidden gap-3 text-sm text-muted lg:grid",
			children: checks.map((item) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("li", {
				className: "flex items-center gap-2",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Check, { className: "size-4 text-cyan" }), item]
			}, item))
		})]
	});
}
function Field({ id, label, required, error, children }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [
		/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Label, {
			htmlFor: id,
			children: [label, required ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
				className: "text-cyan",
				children: " *"
			}) : null]
		}),
		children,
		error ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
			className: "mt-1.5 text-xs text-amber",
			children: error
		}) : null
	] });
}
var checks = [
	"A human review of every request",
	"Clear scope before any build",
	"No unsupported promises"
];
function RequestPage() {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("main", {
		className: "py-16 sm:py-20 lg:py-24",
		children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Container, {
			className: "grid gap-12 lg:grid-cols-2 lg:gap-20",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Eyebrow, { children: "Start a conversation" }),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("h1", {
					className: "font-display text-display tracking-tight text-fg",
					children: [
						"Bring us the",
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("br", {}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "text-muted",
							children: "business need."
						})
					]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
					className: "mt-6 max-w-md text-lede text-muted",
					children: "Tell us whether you are exploring a partnership, technology project, operational need, venture idea, or strategic inquiry. We’ll help shape the right next step."
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("ul", {
					className: "mt-10 grid gap-3 text-sm text-muted",
					children: checks.map((item) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("li", {
						className: "flex items-center gap-2",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Check, { className: "size-4 text-cyan" }), item]
					}, item))
				})
			] }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ProjectForm, {})]
		})
	});
}
//#endregion
export { RequestPage as component };
