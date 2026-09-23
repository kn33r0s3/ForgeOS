/**
 * Read-only SDK inspection utility.
 *
 * Prints the parts of the x402 SDK surface that the service build depends on:
 *  - the default (USDC) asset table per CAIP-2 network
 *  - the public facilitator's advertised supported kinds
 *
 * This performs network reads only. It never signs, settles, or moves funds.
 */

import { DEFAULT_ASSETS } from "@x402/evm";

type DefaultAssetRow = {
  network?: string;
  asset: string;
  symbol?: string;
  name?: string;
  version?: string;
  decimals?: number;
};

const FACILITATOR_URL = process.env.X402_FACILITATOR_URL ?? "https://x402.org/facilitator";

export function defaultAssetRows(): Array<DefaultAssetRow & { key: string }> {
  const table = DEFAULT_ASSETS as unknown as Record<string, Record<string, DefaultAssetRow>>;
  const rows: Array<DefaultAssetRow & { key: string }> = [];
  for (const network of Object.keys(table)) {
    const perSymbol = table[network];
    for (const symbol of Object.keys(perSymbol)) {
      rows.push({ key: `${network}/${symbol}`, network, ...perSymbol[symbol] });
    }
  }
  return rows;
}

async function fetchSupported(): Promise<unknown> {
  const response = await fetch(`${FACILITATOR_URL.replace(/\/$/, "")}/supported`, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(15_000),
  });
  if (!response.ok) throw new Error(`facilitator /supported returned ${response.status}`);
  return response.json();
}

async function main(): Promise<void> {
  const rows = defaultAssetRows();
  console.log("=== default assets (USDC) ===");
  for (const row of rows) {
    console.log(
      `${row.key.padEnd(28)} asset=${row.asset} symbol=${row.symbol ?? "-"} decimals=${row.decimals ?? "-"} name=${row.name ?? "-"} version=${row.version ?? "-"}`,
    );
  }

  console.log("\n=== facilitator supported kinds ===");
  console.log(JSON.stringify(await fetchSupported(), null, 1));

  const wanted = ["eip155:8453", "eip155:84532"];
  console.log("\n=== base + base-sepolia default asset ===");
  for (const network of wanted) {
    const match = rows.find((row) => row.network === network);
    console.log(`${network} -> ${match ? JSON.stringify(match) : "NOT FOUND"}`);
  }
}

main().catch((error: unknown) => {
  console.error("inspect-sdk failed:", error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
