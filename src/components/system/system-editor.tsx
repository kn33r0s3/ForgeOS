import { useEffect, useState, type FormEvent } from "react";
import { Check, Lock } from "lucide-react";
import {
  GOAL_LABELS,
  TIME_LABELS,
  parseList,
  stated,
  type SystemGoal,
  type SystemState,
  type TimeAvailability,
} from "@/lib/system/state";
import { cn } from "@/lib/utils";

const field =
  "mt-2 w-full rounded-card border-2 border-line bg-black px-3 py-2.5 text-base text-ink placeholder:text-dim focus:border-accent focus:outline-none";

function joinValues(items: { value: string }[]) {
  return items.map((i) => i.value).join(", ");
}

/**
 * Edits personal context. Values remain self-stated; guest saves stay local,
 * while authenticated saves go to the owner's private account storage.
 */
export function SystemEditor({
  state,
  onSave,
  privacyMode,
  compact = false,
}: {
  state: SystemState | null;
  onSave: (next: (draft: SystemState) => SystemState) => void | Promise<void>;
  privacyMode: "guest" | "account";
  compact?: boolean;
}) {
  const [location, setLocation] = useState("");
  const [time, setTime] = useState<TimeAvailability | "">("");
  const [goals, setGoals] = useState<SystemGoal[]>([]);
  const [capabilities, setCapabilities] = useState("");
  const [resources, setResources] = useState("");
  const [constraints, setConstraints] = useState("");
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    setLocation(state?.location?.value ?? "");
    setTime(state?.time?.value ?? "");
    setGoals(state?.goals.map((g) => g.value) ?? []);
    setCapabilities(state ? joinValues(state.capabilities) : "");
    setResources(state ? joinValues(state.resources) : "");
    setConstraints(state ? joinValues(state.constraints) : "");
    setSaved(false);
    setSaveError(null);
  }, [state]);

  function toggleGoal(goal: SystemGoal) {
    setGoals((current) => (current.includes(goal) ? current.filter((g) => g !== goal) : [...current, goal]));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setSaveError(null);
    const now = new Date().toISOString();
    const keep = (prev: { value: string; provenance: string; updatedAt: string }[], next: string[]) =>
      next.map((value) => {
        const existing = prev.find((p) => p.value.toLowerCase() === value.toLowerCase());
        return existing && existing.value === value ? (existing as ReturnType<typeof stated<string>>) : stated(value, now);
      });
    const result = onSave((draft) => ({
      ...draft,
      location: location.trim() ? stated(location.trim().slice(0, 80), now) : undefined,
      time: time ? stated(time, now) : undefined,
      goals: goals.map((g) => draft.goals.find((d) => d.value === g) ?? stated(g, now)),
      capabilities: keep(draft.capabilities, parseList(capabilities)),
      resources: keep(draft.resources, parseList(resources)),
      constraints: keep(draft.constraints, parseList(constraints)),
    }));
    void Promise.resolve(result)
      .then(() => {
        setSaved(true);
        window.setTimeout(() => setSaved(false), 2200);
      })
      .catch(() => {
        setSaveError("Hami could not save this context. Your changes have not been reported as saved.");
      });
  }

  return (
    <form onSubmit={submit} className="grid gap-6" aria-label="Edit personal context">
      <div className={cn("grid gap-5", !compact && "md:grid-cols-2")}>
        <label className="block">
          <span className="text-sm font-extrabold text-ink">Where are you?</span>
          <input
            className={field}
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Town or district, e.g. Pokhara"
            autoComplete="address-level2"
            maxLength={80}
          />
        </label>
        <label className="block">
          <span className="text-sm font-extrabold text-ink">Time you can give each week</span>
          <select
            className={field}
            value={time}
            onChange={(e) => setTime(e.target.value as TimeAvailability | "")}
          >
            <option value="">Not sure yet</option>
            {(Object.keys(TIME_LABELS) as TimeAvailability[]).map((t) => (
              <option key={t} value={t}>
                {TIME_LABELS[t]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <fieldset>
        <legend className="text-sm font-extrabold text-ink">What do you want to move forward?</legend>
        <div className="mt-3 flex flex-wrap gap-2">
          {(Object.keys(GOAL_LABELS) as SystemGoal[]).map((g) => (
            <button
              key={g}
              type="button"
              className="chip"
              aria-pressed={goals.includes(g)}
              onClick={() => toggleGoal(g)}
            >
              {goals.includes(g) ? <Check className="size-4" aria-hidden="true" /> : null}
              {GOAL_LABELS[g]}
            </button>
          ))}
        </div>
      </fieldset>

      <label className="block">
        <span className="text-sm font-extrabold text-ink">What can you do?</span>
        <span className="block text-sm text-muted">Skills, trades, experience — separate with commas.</span>
        <textarea
          className={cn(field, "min-h-20")}
          value={capabilities}
          onChange={(e) => setCapabilities(e.target.value)}
          placeholder="e.g. wiring, driving, English, cooking, bookkeeping"
        />
      </label>

      <label className="block">
        <span className="text-sm font-extrabold text-ink">What do you already have?</span>
        <span className="block text-sm text-muted">
          Things that could be useful to someone: space, a vehicle, tools, a device, land, produce.
        </span>
        <textarea
          className={cn(field, "min-h-20")}
          value={resources}
          onChange={(e) => setResources(e.target.value)}
          placeholder="e.g. motorbike, empty room, laptop, sewing machine"
        />
      </label>

      {!compact ? (
        <label className="block">
          <span className="text-sm font-extrabold text-ink">Anything that limits you? (optional)</span>
          <textarea
            className={cn(field, "min-h-16")}
            value={constraints}
            onChange={(e) => setConstraints(e.target.value)}
            placeholder="e.g. evenings only, can't travel far, no upfront money"
          />
        </label>
      ) : null}

      <div className="flex flex-wrap items-center gap-4">
        <button
          type="submit"
          className="btn-wipe hero-primary-cta inline-flex min-h-12 items-center gap-2 rounded-card border-2 border-black bg-accent px-5 font-extrabold text-black shadow-[0_4px_0_#000]"
        >
          {saved ? <Check className="size-4" aria-hidden="true" /> : null}
          {saved ? (privacyMode === "account" ? "Saved privately" : "Saved for this tab") : (privacyMode === "account" ? "Save private context" : "Save temporary context")}
        </button>
        <p className="flex items-center gap-2 text-sm text-muted">
          <Lock className="size-4 shrink-0 text-accent" aria-hidden="true" />
          {privacyMode === "account"
            ? "Private to you. Nothing is shared or published unless you authorize it."
            : "Temporary in this tab. It is not sent to Hami's server."}
        </p>
      </div>
      {saveError ? <p className="text-sm font-semibold text-danger" role="alert">{saveError}</p> : null}
    </form>
  );
}
