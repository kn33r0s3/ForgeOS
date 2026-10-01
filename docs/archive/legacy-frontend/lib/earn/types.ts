export type OfferStatus = "draft" | "customer_confirmed" | "paid" | "failed" | "abandoned";

export type Offer = {
  id: string;
  localId?: string;
  serverId?: number;
  pathway: string;
  title: string;
  skill: string;
  customer: string;
  price: string;
  createdAt: string;
  status: OfferStatus;
  nextActions: { text: string; completed: boolean }[];
  outcomeNote?: string;
};

export type PendingSync =
  | {
      kind: "create";
      localId: string;
      payload: {
        pathway: string;
        title: string;
        skill: string;
        customer: string;
        price_npr: number | null;
        age_band: "14_17" | "18_plus";
        next_actions?: { text: string; completed: boolean }[];
      };
    }
  | { kind: "status"; localId: string; serverId?: number; status: OfferStatus; outcomeNote?: string }
  | { kind: "checklist"; localId: string; serverId?: number; nextActions: { text: string; completed: boolean }[] };

export const STATUS_LABEL: Record<OfferStatus, { en: string; color: string }> = {
  draft: { en: "Hypothesis / Draft", color: "text-forge-warn" },
  customer_confirmed: { en: "Customer confirmed interest", color: "text-forge-accent2" },
  paid: { en: "Payment received (actual)", color: "text-forge-revenue" },
  failed: { en: "No sale / refused", color: "text-forge-danger" },
  abandoned: { en: "Abandoned", color: "text-neutral-500" },
};
