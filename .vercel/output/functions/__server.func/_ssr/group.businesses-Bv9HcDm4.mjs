import { B as require_jsx_runtime, v as Link } from "../_libs/@tanstack/react-router+[...].mjs";
import { n as Container, t as Button } from "./eyebrow-CRXddjtH.mjs";
import { i as currentOffers, s as groupAreas } from "./content-Do6sOcrt.mjs";
import { p as ArrowUpRight } from "../_libs/lucide-react.mjs";
import { t as PageHero } from "./page-hero-BZaxG8vo.mjs";
import { t as CtaBand } from "./cta-band-CinmItwG.mjs";
import { t as SectionMarker } from "./section-marker-D-HoRaZ4.mjs";
import { t as TextLink } from "./text-link-CHIRVWe-.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/group.businesses-Bv9HcDm4.js
var import_jsx_runtime = require_jsx_runtime();
function OfferCard({ offer }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("article", {
		className: "flex flex-col rounded-xl border border-line bg-surface p-6 transition-[border-color,transform] duration-150 hover:border-cyan/35",
		children: [
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
				className: "font-mono text-micro uppercase tracking-[0.14em] text-cyan",
				children: "Current offer"
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h3", {
				className: "mt-5 font-display text-2xl font-semibold tracking-tight text-fg",
				children: offer.title
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("dl", {
				className: "mt-6 grid gap-4 text-sm",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("dt", {
						className: "font-semibold text-fg",
						children: "Problem"
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("dd", {
						className: "mt-1 leading-relaxed text-muted",
						children: offer.problem
					})] }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("dt", {
						className: "font-semibold text-fg",
						children: "What Sanip Ops does"
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("dd", {
						className: "mt-1 leading-relaxed text-muted",
						children: offer.does
					})] }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("dt", {
						className: "font-semibold text-fg",
						children: "Expected value"
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("dd", {
						className: "mt-1 leading-relaxed text-muted",
						children: offer.value
					})] }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("dt", {
						className: "font-semibold text-fg",
						children: "How to start"
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("dd", {
						className: "mt-1 leading-relaxed text-muted",
						children: offer.start
					})] })
				]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
				className: "mt-6",
				children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(TextLink, {
					to: "/request",
					children: "Explore this need"
				})
			})
		]
	});
}
function BusinessesPage() {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("main", { children: [
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(PageHero, {
			eyebrow: "Businesses / solutions",
			title: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(import_jsx_runtime.Fragment, { children: [
				"Grand ambition.",
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("br", {}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
					className: "text-muted",
					children: "Useful work today."
				})
			] }),
			lede: "Sanip Ops is the parent platform. Today, the practical offer is technical and operational work that helps ideas become systems, and systems become durable businesses.",
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "mt-8 flex flex-col gap-3 sm:flex-row",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
					asChild: true,
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Link, {
						to: "/request",
						children: ["Partner with us", /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ArrowUpRight, {})]
					})
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
					asChild: true,
					variant: "secondary",
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Link, {
						to: "/contact",
						children: "Start a conversation"
					})
				})]
			})
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Container, {
			className: "py-16 sm:py-20",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
					className: "grid gap-8 lg:grid-cols-[9rem_1fr] lg:gap-12",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(SectionMarker, {
						label: "Today",
						index: "01"
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
							className: "font-display text-title tracking-tight text-fg",
							children: "What Sanip Ops can do now"
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
							className: "mt-4 max-w-2xl text-sm leading-relaxed text-muted",
							children: "Current offerings are focused engagements around technology, software, workflows, operations, infrastructure support, and early venture thinking."
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
							className: "mt-8 grid gap-4 md:grid-cols-2",
							children: currentOffers.map((offer) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)(OfferCard, { offer }, offer.title))
						})
					] })]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
					className: "mt-16 grid gap-8 border-t border-line pt-10 lg:grid-cols-[9rem_1fr] lg:gap-12",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(SectionMarker, {
						label: "Building",
						index: "02"
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
							className: "font-display text-title tracking-tight text-fg",
							children: "Developing the group’s operating core."
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
							className: "mt-4 max-w-2xl text-sm leading-relaxed text-muted",
							children: "ForgeOS is in development as Sanip Ops’ internal local-first intelligence, operations, and business-software engine. It supports the long-term direction; it is not being sold as a public product or connected to this website."
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
							className: "mt-5",
							children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(TextLink, {
								to: "/about",
								children: "See the group context"
							})
						})
					] })]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
					className: "mt-16 grid gap-8 border-t border-line pt-10 lg:grid-cols-[9rem_1fr] lg:gap-12",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(SectionMarker, {
						label: "Long-term",
						index: "03"
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
							className: "font-display text-title tracking-tight text-fg",
							children: "Areas the parent platform may grow into."
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
							className: "mt-4 max-w-2xl text-sm leading-relaxed text-muted",
							children: "These are strategic directions, not existing subsidiaries or operating businesses."
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
							className: "mt-8 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2",
							children: groupAreas.map((area) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
								className: "bg-surface p-5",
								children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("strong", {
									className: "font-display text-base font-semibold tracking-tight text-fg",
									children: area.name
								}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
									className: "mt-2 text-xs leading-relaxed text-muted",
									children: area.description
								})]
							}, area.name))
						})
					] })]
				})
			]
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(CtaBand, {})
	] });
}
//#endregion
export { BusinessesPage as component };
