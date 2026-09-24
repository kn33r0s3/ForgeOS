"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, EarningOffer } from "@/lib/api";
import { pathways } from "@/lib/earn/pathways";
import { Offer, OfferStatus, PendingSync, STATUS_LABEL } from "@/lib/earn/types";
import { SafetyBanner } from "@/components/earn/SafetyBanner";
import { PathwayPicker } from "@/components/earn/PathwayPicker";
import { OfferForm } from "@/components/earn/OfferForm";
import { OfferList } from "@/components/earn/OfferList";

function makeClientId(prefix: string) {
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    const buffer = new Uint8Array(16);
    crypto.getRandomValues(buffer);
    const hex = Array.from(buffer)
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
    return `${prefix}-${hex}`;
  }

  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function EarnPage() {
  const [age, setAge] = useState("");
  const [workspaceKey, setWorkspaceKey] = useState("");
  const [selected, setSelected] = useState(pathways[0].id);
  const [offer, setOffer] = useState({ title: "", skill: "", customer: "", price: "" });
  const [saved, setSaved] = useState<Offer[]>([]);
  const [message, setMessage] = useState("");
  const [outcomeDrafts, setOutcomeDrafts] = useState<Record<string, string>>({});

  useEffect(() => {
    const key = localStorage.getItem("forgeos-nepal-workspace-key") || makeClientId("workspace");
    localStorage.setItem("forgeos-nepal-workspace-key", key);
    setWorkspaceKey(key);
    try {
      setSaved(JSON.parse(localStorage.getItem("forgeos-nepal-offers") || "[]"));
    } catch {
      setSaved([]);
    }
    api.listEarningOffers(key).then((remote) => {
      const merged: Offer[] = remote.map((item: EarningOffer) => ({
        id: `server-${item.id}`,
        serverId: item.id,
        pathway: item.pathway,
        title: item.title,
        skill: item.skill,
        customer: item.customer,
        price: item.price_npr === null ? "" : String(item.price_npr),
        createdAt: item.created_at,
        status: item.status,
        nextActions: item.next_actions,
        outcomeNote: item.outcome_note || undefined,
      }));
      if (merged.length) {
        setSaved(merged);
        localStorage.setItem("forgeos-nepal-offers", JSON.stringify(merged));
      }
      void flushSync(key);
    }).catch(() => {
      setMessage("Offline mode: local offers remain available; sync will retry when the server is reachable.");
    });
    const retry = () => void flushSync(key);
    window.addEventListener("online", retry);
    return () => window.removeEventListener("online", retry);
  }, []);

  function persist(all: Offer[]) {
    setSaved(all);
    localStorage.setItem("forgeos-nepal-offers", JSON.stringify(all));
  }

  function queueSync(operation: PendingSync) {
    const current = JSON.parse(localStorage.getItem("forgeos-nepal-sync-queue") || "[]") as PendingSync[];
    localStorage.setItem("forgeos-nepal-sync-queue", JSON.stringify([...current, operation]));
  }

  async function flushSync(key: string) {
    const queue = JSON.parse(localStorage.getItem("forgeos-nepal-sync-queue") || "[]") as PendingSync[];
    if (!queue.length) return;
    const remaining: PendingSync[] = [];
    for (const operation of queue) {
      try {
        if (operation.kind === "create") {
          const remote = await api.createEarningOffer({ ...operation.payload, workspace_key: key });
          const local = JSON.parse(localStorage.getItem("forgeos-nepal-offers") || "[]") as Offer[];
          const updated = local.map((item) => item.id === operation.localId
            ? { ...item, id: `server-${remote.id}`, localId: operation.localId, serverId: remote.id }
            : item);
          localStorage.setItem("forgeos-nepal-offers", JSON.stringify(updated));
          setSaved(updated);
        } else if (operation.kind === "status") {
          const local = JSON.parse(localStorage.getItem("forgeos-nepal-offers") || "[]") as Offer[];
          const item = local.find((candidate) => candidate.id === operation.localId || candidate.localId === operation.localId || candidate.serverId === operation.serverId);
          const serverId = operation.serverId || item?.serverId;
          if (!serverId) { remaining.push(operation); continue; }
          await api.updateEarningOfferStatus(serverId, key, operation.status, operation.outcomeNote);
        } else {
          const local = JSON.parse(localStorage.getItem("forgeos-nepal-offers") || "[]") as Offer[];
          const item = local.find((candidate) => candidate.id === operation.localId || candidate.localId === operation.localId || candidate.serverId === operation.serverId);
          const serverId = operation.serverId || item?.serverId;
          if (!serverId) { remaining.push(operation); continue; }
          await api.updateEarningOfferChecklist(serverId, key, operation.nextActions);
        }
      } catch {
        remaining.push(operation);
      }
    }
    localStorage.setItem("forgeos-nepal-sync-queue", JSON.stringify(remaining));
  }

  function saveOffer(e: FormEvent) {
    e.preventDefault();
    const numericAge = Number(age);
    if (!Number.isInteger(numericAge) || numericAge < 14) {
      setMessage("Earning workflows start at age 14. Use your real age. Do not bypass safety or KYC rules.");
      return;
    }
    if (!offer.title.trim() || !offer.skill.trim() || !offer.customer.trim()) {
      setMessage("Add a specific offer, your real skill, and a real customer type.");
      return;
    }
    const next: Offer = {
      id: makeClientId("offer"),
      pathway: selected,
      ...offer,
      createdAt: new Date().toISOString(),
      status: "draft",
      nextActions: chosen.nextActions.map((text) => ({ text, completed: false })),
    };
    persist([next, ...saved]);
    if (workspaceKey) {
      api.createEarningOffer({
        workspace_key: workspaceKey, pathway: selected, title: offer.title,
        skill: offer.skill, customer: offer.customer,
        price_npr: offer.price ? Number(offer.price) : null,
        age_band: numericAge < 18 ? "14_17" : "18_plus",
        next_actions: next.nextActions,
      }).then((remote) => {
        const synced = { ...next, id: `server-${remote.id}`, serverId: remote.id };
        const current = JSON.parse(localStorage.getItem("forgeos-nepal-offers") || "[]") as Offer[];
        const merged = current.map((item) => item.id === next.id ? synced : item);
        persist(merged);
        setMessage("Saved locally and synced to ForgeOS. This is still a draft—not a customer, payment, or profit claim.");
      }).catch(() => {
        queueSync({ kind: "create", localId: next.id, payload: {
          pathway: selected, title: offer.title, skill: offer.skill, customer: offer.customer,
          price_npr: offer.price ? Number(offer.price) : null,
          age_band: numericAge < 18 ? "14_17" : "18_plus",
          next_actions: next.nextActions,
        }});
        setMessage("Saved offline. ForgeOS queued this draft and will sync it when the server is reachable.");
      });
    }
    setOffer({ title: "", skill: "", customer: "", price: "" });
    setMessage("Saved offline on this device. This is a draft — not a customer, payment, or profit.");
  }

  function updateStatus(id: string, status: OfferStatus) {
    const current = saved.find((o) => o.id === id);
    if (!current) return;
    const allowed: Record<OfferStatus, OfferStatus[]> = {
      draft: ["customer_confirmed", "failed", "abandoned"],
      customer_confirmed: ["paid", "failed", "abandoned"],
      paid: [], failed: [], abandoned: [],
    };
    if (!allowed[current.status].includes(status)) {
      setMessage(`Cannot move ${STATUS_LABEL[current.status].en} directly to ${STATUS_LABEL[status].en}.`);
      return;
    }
    const terminal = status === "paid" || status === "failed" || status === "abandoned";
    const outcomeNote = (outcomeDrafts[id] || "").trim();
    if (terminal && outcomeNote.length < 3) {
      setMessage("Add a brief honest outcome before closing this offer.");
      return;
    }
    const all = saved.map((o) => (o.id === id ? { ...o, status, outcomeNote: outcomeNote || o.outcomeNote } : o));
    persist(all);
    if (current.serverId && workspaceKey) {
      api.updateEarningOfferStatus(current.serverId, workspaceKey, status, outcomeNote)
        .then(() => setMessage(`Status updated in ForgeOS: ${STATUS_LABEL[status].en}`))
        .catch(() => {
          queueSync({ kind: "status", localId: current.id, serverId: current.serverId, status, outcomeNote });
          setMessage(`Status saved offline: ${STATUS_LABEL[status].en}. Sync is queued.`);
        });
    } else {
      queueSync({ kind: "status", localId: current.id, status, outcomeNote });
      setMessage(`Status updated locally: ${STATUS_LABEL[status].en}`);
    }
  }

  function toggleNextAction(id: string, index: number) {
    const current = saved.find((o) => o.id === id);
    if (!current) return;
    const nextActions = current.nextActions.map((action, actionIndex) =>
      actionIndex === index ? { ...action, completed: !action.completed } : action
    );
    persist(saved.map((o) => o.id === id ? { ...o, nextActions } : o));
    if (current.serverId && workspaceKey) {
      api.updateEarningOfferChecklist(current.serverId, workspaceKey, nextActions)
        .then(() => setMessage("Next-action checklist saved in ForgeOS."))
        .catch(() => {
          queueSync({ kind: "checklist", localId: current.id, serverId: current.serverId, nextActions });
          setMessage("Checklist saved offline. Sync is queued.");
        });
    } else {
      queueSync({ kind: "checklist", localId: current.id, nextActions });
      setMessage("Checklist updated locally.");
    }
  }

  function removeOffer(id: string) {
    persist(saved.filter((o) => o.id !== id));
  }

  const chosen = pathways.find((p) => p.id === selected) || pathways[0];

  return (
    <div className="space-y-7 animate-fade-up">
      <header className="space-y-2">
        <p className="section-label">NEPAL-FIRST EARNING WORKSPACE · NPR</p>
        <h1 className="text-3xl md:text-4xl font-bold tracking-tight text-neutral-50">
          Turn a real skill into a real offer.
        </h1>
        <p className="text-neutral-400 max-w-3xl leading-relaxed">
          आफ्नो सीपलाई वास्तविक आम्दानीको अवसरमा बदल्नुहोस्। ForgeOS helps you test demand safely.
          It never guarantees profit and never counts a draft as a customer or payment.
        </p>
      </header>

      <SafetyBanner age={age} onAgeChange={setAge} />

      <PathwayPicker pathways={pathways} selected={selected} onSelect={setSelected} />

      <OfferForm chosen={chosen} offer={offer} onChange={setOffer} onSubmit={saveOffer} message={message} />

      <OfferList
        saved={saved}
        pathways={pathways}
        outcomeDrafts={outcomeDrafts}
        onOutcomeDraftChange={(id, value) => setOutcomeDrafts({ ...outcomeDrafts, [id]: value })}
        onToggleNextAction={toggleNextAction}
        onUpdateStatus={updateStatus}
        onRemove={removeOffer}
      />

      <p className="text-xs text-neutral-600 leading-relaxed max-w-3xl">
        Payment providers (eSewa, Khalti, Fonepay) require merchant approval and live credentials before
        automatic verification. Until then, mark &ldquo;payment received&rdquo; only when money has actually arrived
        in a real account you control. ForgeOS never invents revenue.
      </p>
    </div>
  );
}
