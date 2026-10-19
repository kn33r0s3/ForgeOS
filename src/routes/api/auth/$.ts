import { createFileRoute } from "@tanstack/react-router";
import { auth, authConfigured } from "@/lib/auth/server";

async function handleAuthRequest(request: Request): Promise<Response> {
  if (process.env.HAMI_MAINTENANCE_MODE === "true") {
    return new Response(JSON.stringify({ error: "Hami is under development." }), {
      status: 503,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "no-store",
        "x-robots-tag": "noindex, nofollow, noarchive, nosnippet",
      },
    });
  }
  if (!authConfigured) {
    return new Response(JSON.stringify({ error: "Authentication is unavailable." }), {
      status: 503,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "no-store",
      },
    });
  }
  return auth.handler(request);
}

export const Route = createFileRoute("/api/auth/$")({
  server: {
    handlers: {
      GET: ({ request }) => handleAuthRequest(request),
      POST: ({ request }) => handleAuthRequest(request),
    },
  },
});
