import { i as __toESM } from "../_runtime.mjs";
import { n as require_react } from "../_libs/@radix-ui/react-compose-refs+[...].mjs";
import { B as require_jsx_runtime } from "../_libs/@tanstack/react-router+[...].mjs";
import { n as Container, r as Eyebrow, t as Button } from "./eyebrow-CRXddjtH.mjs";
import { a as Shield, h as Activity, i as TrendingUp, l as Layers, n as WifiOff, o as RefreshCw, r as TriangleAlert, s as Play, u as CircleCheckBig } from "../_libs/lucide-react.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/operations-DdUOiZrO.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
function OperationsPage() {
	const [dashboard, setDashboard] = (0, import_react.useState)(null);
	const [actions, setActions] = (0, import_react.useState)([]);
	const [loading, setLoading] = (0, import_react.useState)(true);
	const [error, setError] = (0, import_react.useState)(null);
	const [backendOnline, setBackendOnline] = (0, import_react.useState)(null);
	const [runningCycle, setRunningCycle] = (0, import_react.useState)(false);
	const [cycleMsg, setCycleMsg] = (0, import_react.useState)(null);
	async function checkBackendHealth() {
		try {
			return (await fetch("/api/health", { signal: AbortSignal.timeout(4e3) })).ok;
		} catch {
			return false;
		}
	}
	async function loadOperatingData() {
		setLoading(true);
		setError(null);
		const online = await checkBackendHealth();
		setBackendOnline(online);
		if (!online) {
			setError("ForgeOS engine offline");
			setLoading(false);
			return;
		}
		try {
			const [dashRes, actRes] = await Promise.all([fetch("/api/forge/money/dashboard"), fetch("/api/forge/execution/actions")]);
			if (!dashRes.ok) throw new Error(`Dashboard API HTTP ${dashRes.status}`);
			if (!actRes.ok) throw new Error(`Actions API HTTP ${actRes.status}`);
			const dashData = await dashRes.json();
			const actData = await actRes.json();
			setDashboard(dashData);
			setActions(actData);
		} catch (err) {
			setError(err.message || "Unable to query ForgeOS data endpoints");
		} finally {
			setLoading(false);
		}
	}
	async function handleRunCycle() {
		if (!window.confirm("Run Forge Intelligence Cycle?\n\nThis operation writes to multiple ForgeOS database tables (cycle_runs, patterns, beliefs, research_tasks, predictions, opportunities, and more).\n\nIt does NOT execute any actions or spend money. Proceed only when you want to advance the intelligence cycle.")) return;
		setRunningCycle(true);
		setCycleMsg(null);
		try {
			const res = await fetch("/api/forge/cycle", { method: "POST" });
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const data = await res.json();
			setCycleMsg(`Cycle complete. Status: ${data.status || "COMPLETED"} · Cycle ID: ${data.cycle_id ?? "—"}`);
			await loadOperatingData();
		} catch (err) {
			setCycleMsg(`Cycle error: ${err.message}`);
		} finally {
			setRunningCycle(false);
		}
	}
	async function handleRunDiscovery() {
		if (!window.confirm("Run Economic Discovery Scan?\n\nThis operation writes to the ForgeOS opportunities table. It evaluates patterns and strong signals against the economic evidence gate and creates new Opportunity records where the bar is met.\n\nIt does NOT contact customers or spend money. Proceed only when you want to run autonomous opportunity discovery.")) return;
		setRunningCycle(true);
		setCycleMsg(null);
		try {
			const res = await fetch("/api/forge/economic/discover", { method: "POST" });
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const data = await res.json();
			setCycleMsg(`Discovery complete: reviewed ${data.patterns_reviewed ?? "?"} pattern(s), created ${(data.opportunities_created ?? 0) + (data.single_signal_opportunities_created ?? 0)} new evidence-backed opportunity(ies).`);
			await loadOperatingData();
		} catch (err) {
			setCycleMsg(`Discovery error: ${err.message}`);
		} finally {
			setRunningCycle(false);
		}
	}
	async function handleApproveAction(id) {
		try {
			const res = await fetch(`/api/forge/execution/actions/${id}/approve`, { method: "POST" });
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			if (await res.json() === null) {
				alert(`Approval not applied for Action #${id}.\n\nThe ForgeOS policy engine returned null, which means this action is currently blocked by the autonomy policy. Review the policy_reason shown below the action.`);
				return;
			}
			await loadOperatingData();
		} catch (err) {
			alert(`Approval error: ${err.message}`);
		}
	}
	(0, import_react.useEffect)(() => {
		loadOperatingData();
	}, []);
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("main", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("section", {
		className: "border-b border-line py-12 lg:py-16",
		children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Container, { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "flex flex-col gap-6 md:flex-row md:items-end md:justify-between",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Eyebrow, {
					tone: "amber",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { className: "size-1.5 rounded-full bg-amber shadow-[0_0_0_4px_var(--color-amber-dim)]" }), "Sanip Operations · Internal Engine"]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("h1", {
					className: "font-display text-title tracking-tight text-fg",
					children: [
						"Operating Dashboard",
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("br", {}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "text-muted",
							children: "Evidence, opportunities & proposed actions."
						})
					]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
					className: "mt-4 max-w-2xl text-lede text-muted",
					children: "Sanip Ops internal operating window. Exposes real evidence, scored opportunities, policy-governed approval queues, and verified economic results. All figures are drawn directly from the ForgeOS database — no fabricated data."
				})
			] }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "flex flex-wrap items-center gap-3",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
					onClick: handleRunCycle,
					disabled: runningCycle || backendOnline === false,
					variant: "amber",
					size: "sm",
					className: "gap-2",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Play, { className: `size-4 ${runningCycle ? "animate-spin" : ""}` }), runningCycle ? "Running Cycle..." : "Run Forge Cycle"]
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
					onClick: handleRunDiscovery,
					disabled: runningCycle || backendOnline === false,
					variant: "secondary",
					size: "sm",
					className: "gap-2",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(RefreshCw, { className: `size-4 ${runningCycle ? "animate-spin" : ""}` }), "Run Discovery Scan"]
				})]
			})]
		}), cycleMsg && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "mt-6 rounded-lg border border-amber/30 bg-amber/10 p-4 font-mono text-sm text-amber flex items-center justify-between",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: cycleMsg }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
				onClick: () => setCycleMsg(null),
				className: "text-xs underline hover:text-fg",
				children: "Dismiss"
			})]
		})] })
	}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("section", {
		className: "py-12 lg:py-16",
		children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Container, { children: loading ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "flex items-center justify-center py-20 text-muted",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(RefreshCw, { className: "size-6 animate-spin mr-3 text-cyan" }), "Connecting to ForgeOS backend engine..."]
		}) : backendOnline === false ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "rounded-xl border border-red-500/30 bg-red-500/5 p-8 text-center space-y-4",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "mx-auto flex size-12 items-center justify-center rounded-full bg-red-500/10 text-red-400",
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(WifiOff, { className: "size-6" })
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
					className: "font-display text-lg font-semibold text-fg",
					children: "ForgeOS Engine Offline"
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
					className: "max-w-md mx-auto text-sm text-muted",
					children: "The local ForgeOS backend (FastAPI, port 8000) is not responding. Economic data cannot be shown — displaying empty state here would misrepresent the actual system as having zero opportunities, which is not the same as an offline backend."
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", {
					className: "max-w-md mx-auto text-xs text-dim font-mono",
					children: [
						"Start the backend: ",
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "text-cyan",
							children: "./run_forgeos.sh"
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("br", {}),
						"or: ",
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "text-cyan",
							children: "cd backend && uvicorn app.main:app --port 8000"
						})
					]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
					onClick: loadOperatingData,
					variant: "secondary",
					size: "sm",
					className: "gap-2",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(RefreshCw, { className: "size-4" }), " Retry Connection"]
				})
			]
		}) : error ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "rounded-xl border border-line bg-surface p-8 text-center space-y-4",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "mx-auto flex size-12 items-center justify-center rounded-full bg-amber/10 text-amber",
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(TriangleAlert, { className: "size-6" })
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
					className: "font-display text-lg font-semibold text-fg",
					children: "Data Load Error"
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", {
					className: "max-w-md mx-auto text-sm text-muted",
					children: ["ForgeOS backend is reachable but returned an error: ", error]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
					onClick: loadOperatingData,
					variant: "secondary",
					size: "sm",
					className: "gap-2",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(RefreshCw, { className: "size-4" }), " Retry"]
				})
			]
		}) : dashboard ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "space-y-12",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("h2", {
					className: "font-display text-lg font-semibold text-fg mb-4 flex items-center gap-2",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Activity, { className: "size-5 text-cyan" }), " 1. System & Economic State"]
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "grid gap-4 sm:grid-cols-2 lg:grid-cols-4",
					children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
							className: "rounded-xl border border-line bg-surface p-5",
							children: [
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
									className: "font-mono text-micro uppercase text-dim block mb-1",
									children: "Verified Revenue"
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
									className: "font-display text-2xl font-semibold text-fg",
									children: ["NPR ", dashboard.total_revenue_recorded.toFixed(2)]
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
									className: "mt-1 text-xs text-muted",
									children: "Bank/wallet verified payout only"
								})
							]
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
							className: "rounded-xl border border-line bg-surface p-5",
							children: [
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
									className: "font-mono text-micro uppercase text-dim block mb-1",
									children: "Evidence-Gated Hypotheses"
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
									className: "font-display text-2xl font-semibold text-amber",
									children: dashboard.best_opportunities.length
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
									className: "mt-1 text-xs text-muted",
									children: "Opportunities scored by evidence — current money scores may be 0"
								})
							]
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
							className: "rounded-xl border border-line bg-surface p-5",
							children: [
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
									className: "font-mono text-micro uppercase text-dim block mb-1",
									children: "Proposed Actions"
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
									className: "font-display text-2xl font-semibold text-cyan",
									children: actions.length
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
									className: "mt-1 text-xs text-muted",
									children: "All require owner approval before any execution"
								})
							]
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
							className: "rounded-xl border border-line bg-surface p-5",
							children: [
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
									className: "font-mono text-micro uppercase text-dim block mb-1",
									children: "Completed Experiments"
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
									className: "font-display text-2xl font-semibold text-fg",
									children: dashboard.completed_experiments_count
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
									className: "mt-1 text-xs text-muted",
									children: "Measured validation tests"
								})
							]
						})
					]
				})] }),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "flex items-center justify-between mb-4",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("h2", {
						className: "font-display text-lg font-semibold text-fg flex items-center gap-2",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(TrendingUp, { className: "size-5 text-amber" }), " 2. Ranked Opportunities"]
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
						className: "font-mono text-micro uppercase text-dim",
						children: "Ordered by Money Score · Evidence-gated hypotheses"
					})]
				}), dashboard.best_opportunities.length === 0 ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "rounded-xl border border-line bg-surface p-6 text-center text-sm text-muted",
					children: "No opportunities currently cleared by the evidence engine. Click \"Run Discovery Scan\" to evaluate signals."
				}) : /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "grid gap-4 sm:grid-cols-2",
					children: dashboard.best_opportunities.slice(0, 4).map((item) => {
						const opp = item.opportunity;
						return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
							className: "flex flex-col justify-between rounded-xl border border-line bg-surface p-5 space-y-3",
							children: [
								/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
									className: "space-y-1.5",
									children: [
										/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
											className: "flex items-center justify-between",
											children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
												className: "font-mono text-micro uppercase text-cyan",
												children: [
													"Opp #",
													opp.id,
													" · ",
													opp.customer_segment || opp.target_customer || "General"
												]
											}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
												className: "font-mono text-micro rounded-full border border-amber/30 bg-amber/10 px-2 py-0.5 text-amber",
												children: ["Score: ", opp.score.toFixed(1)]
											})]
										}),
										/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h3", {
											className: "font-display font-semibold text-fg text-base line-clamp-2",
											children: opp.problem
										}),
										/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
											className: "text-xs text-muted line-clamp-2",
											children: opp.solution
										})
									]
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
									className: "border-t border-line pt-3 flex items-center justify-between text-xs text-dim font-mono",
									children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", { children: ["Model: ", opp.business_model || "SaaS"] }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", { children: ["Diff: ", opp.difficulty || "medium"] })]
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
									className: "text-xs text-dim font-mono",
									children: [
										"Money Score: ",
										item.money_score.toFixed(2),
										item.money_score === 0 && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
											className: "ml-2 text-dim opacity-70",
											children: "(pending revenue validation)"
										})
									]
								})
							]
						}, opp.id);
					})
				})] }),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "flex items-center justify-between mb-4",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("h2", {
							className: "font-display text-lg font-semibold text-fg flex items-center gap-2",
							children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Shield, { className: "size-5 text-cyan" }), " 3. Proposed Actions & Approval Queue"]
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "font-mono text-micro uppercase text-dim",
							children: "Requires Owner Approval · None auto-executed"
						})]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", {
						className: "mb-4 text-xs text-dim",
						children: [
							"These are ForgeOS-proposed validation actions (e.g. customer interviews). They are in",
							" ",
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
								className: "text-amber font-mono",
								children: "planned"
							}),
							" status with",
							" ",
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
								className: "text-amber font-mono",
								children: "requires_owner_approval = true"
							}),
							". None have been executed. Approving marks the record; it does not trigger automatic execution."
						]
					}),
					actions.length === 0 ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "rounded-xl border border-line bg-surface p-6 text-center text-sm text-muted",
						children: "No proposed actions in the queue."
					}) : /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "grid gap-3",
						children: actions.map((act) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
							className: "flex flex-col gap-3 rounded-xl border border-line bg-surface p-4 sm:flex-row sm:items-center sm:justify-between",
							children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
								className: "space-y-1",
								children: [
									/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
										className: "flex items-center gap-2",
										children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
											className: "font-mono text-micro uppercase text-cyan",
											children: [
												"Proposal #",
												act.id,
												" · ",
												act.action_type || "Validation"
											]
										}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
											className: `rounded-full border px-2 py-0.5 font-mono text-micro ${act.status === "completed" ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" : act.approved_at ? "border-cyan/30 bg-cyan/10 text-cyan" : "border-amber/30 bg-amber/10 text-amber"}`,
											children: act.status === "completed" ? "completed" : act.approved_at ? "approved (not yet executed)" : act.status
										})]
									}),
									/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
										className: "font-display text-sm font-semibold text-fg",
										children: act.action
									}),
									act.policy_reason && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", {
										className: "text-xs text-dim",
										children: ["Policy: ", act.policy_reason]
									}),
									act.approved_at && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", {
										className: "text-xs text-dim",
										children: [
											"Approved at: ",
											new Date(act.approved_at).toLocaleString(),
											" — awaiting manual execution"
										]
									})
								]
							}), act.requires_owner_approval && act.status !== "completed" && !act.approved_at && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
								onClick: () => handleApproveAction(act.id),
								size: "sm",
								variant: "amber",
								className: "gap-1.5 self-start sm:self-auto",
								children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(CircleCheckBig, { className: "size-4" }), " Approve Proposal"]
							})]
						}, act.id))
					})
				] }),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("h2", {
					className: "font-display text-lg font-semibold text-fg mb-4 flex items-center gap-2",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Layers, { className: "size-5 text-muted" }), " 4. Measured Outcomes & Learning"]
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "rounded-xl border border-line bg-surface p-6 text-center",
					children: dashboard.completed_experiments_count === 0 ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "space-y-2 text-muted",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
							className: "text-sm font-medium text-fg",
							children: "Outcomes Currently Empty"
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
							className: "max-w-md mx-auto text-xs",
							children: "No customer validation experiments have completed yet. As approved proposals are manually executed and real outcomes are recorded into ForgeOS, results will appear here."
						})]
					}) : /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "text-sm text-fg",
						children: [dashboard.winning_experiments.length, " winning validation test(s) recorded."]
					})
				})] })
			]
		}) : null })
	})] });
}
//#endregion
export { OperationsPage as component };
