import {
  HTTPFacilitatorClient,
  x402ResourceServer,
} from "@x402/core/server";
import { ExactEvmScheme } from "@x402/evm/exact/server";
import { paymentMiddlewareFromConfig } from "@x402/hono";

const NETWORK = "eip155:84532" as const;

const FACILITATOR_URL =
  process.env.X402_FACILITATOR_URL ?? "https://x402.org/facilitator";

export function resolvePublicResourceUrl(value: string | undefined = process.env.X402_RESOURCE_URL): string {
  const configured = value?.trim() ?? "";
  if (!configured) {
    throw new Error("X402_RESOURCE_URL is required; configure the actual reachable x402 endpoint.");
  }
  let parsed: URL;
  try {
    parsed = new URL(configured);
  } catch {
    throw new Error("X402_RESOURCE_URL must be an absolute HTTP(S) URL.");
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("X402_RESOURCE_URL must use HTTP or HTTPS.");
  }
  return configured;
}

/**
 * X402 resource server for ForgeOS evidence triage.
 *
 * Base Sepolia + USDC + X402 v2 exact scheme.
 * The deterministic triage handler remains separate from payment handling.
 */
export const facilitator = new HTTPFacilitatorClient({
  url: FACILITATOR_URL,
});

export const resourceServer = new x402ResourceServer(facilitator).register(
  NETWORK,
  new ExactEvmScheme(),
);

/**
 * Creates the Hono middleware protecting the evidence-triage endpoint.
 *
 * The route price and public resource identity are supplied through
 * configuration so the economic policy remains explicit and auditable.
 */
export function createX402Middleware(payTo: string) {
  const publicResourceUrl = resolvePublicResourceUrl();
  return paymentMiddlewareFromConfig(
    {
      "POST /triage": {
        accepts: {
          scheme: "exact",
          network: NETWORK,
          price: "$0.01",
          payTo,
        },
        resource: publicResourceUrl,
        description: "Deterministic ForgeOS evidence triage",
        mimeType: "application/json",
      },
    },
    facilitator,
    [
      {
        network: NETWORK,
        server: new ExactEvmScheme(),
      },
    ],
  );
}