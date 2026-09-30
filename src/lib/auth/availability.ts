import { createServerFn } from "@tanstack/react-start";
import { ACTIVE_TERMS } from "./terms-policy";

export const getAuthAvailability = createServerFn({ method: "GET" }).handler(
  async () => {
    const { googleAuthConfigured } = await import("./server");
    return {
      googleConfigured: googleAuthConfigured,
      termsConfigured: ACTIVE_TERMS !== null,
      termsUrl: ACTIVE_TERMS?.url ?? null,
    };
  },
);
