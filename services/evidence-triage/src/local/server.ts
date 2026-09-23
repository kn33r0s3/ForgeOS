import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { Hono } from "hono";
import { handleEvidenceTriage } from "../app.ts";
import { createX402Middleware } from "../x402.ts";

const HOST = process.env.HOST ?? "127.0.0.1";
const PORT = Number(process.env.PORT ?? 8787);
const PAY_TO = process.env.X402_PAY_TO?.trim();

if (!PAY_TO) {
  throw new Error("X402_PAY_TO is required for evidence-triage");
}

const app = new Hono();

app.use("*", createX402Middleware(PAY_TO));

app.post("/triage", (c) => handleEvidenceTriage(c.req.raw));

async function readBody(request: IncomingMessage): Promise<Buffer> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks);
}

async function writeResponse(
  response: ServerResponse,
  result: Response,
): Promise<void> {
  response.statusCode = result.status;
  result.headers.forEach((value, key) => response.setHeader(key, value));
  const body = Buffer.from(await result.arrayBuffer());
  response.end(body);
}

const server = createServer(async (request, response) => {
  try {
    const body =
      request.method === "GET" || request.method === "HEAD"
        ? undefined
        : await readBody(request);

    const headers = new Headers();

    for (const [key, value] of Object.entries(request.headers)) {
      if (Array.isArray(value)) headers.set(key, value.join(", "));
      else if (value !== undefined) headers.set(key, value);
    }

    const forwardedHost =
      headers.get("x-forwarded-host") ??
      headers.get("host") ??
      `${HOST}:${PORT}`;

    const forwardedProto =
      headers.get("x-forwarded-proto") ?? "http";

    const target =
      `${forwardedProto}://${forwardedHost}${request.url ?? "/"}`;

    const webRequest = new Request(target, {
      method: request.method ?? "GET",
      headers,
      body: body ? body.toString("utf8") : undefined,
    });

    const result = await app.fetch(webRequest);
    await writeResponse(response, result);
  } catch (error) {
    console.error("server error:", error);
    response.statusCode = 500;
    response.setHeader(
      "content-type",
      "application/json; charset=utf-8",
    );
    response.end(
      JSON.stringify({
        error: { code: "INTERNAL_SERVER_ERROR" },
      }),
    );
  }
});

server.listen(PORT, HOST, () => {
  console.log(
    `evidence-triage listening on http://${HOST}:${PORT} x402=${PAY_TO}`,
  );
});
