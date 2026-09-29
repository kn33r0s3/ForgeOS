import {
  createRootRoute,
  HeadContent,
  Outlet,
  Scripts,
} from "@tanstack/react-router";
import { AuthProvider } from "@/lib/auth/provider";
import { PreviewHostBridge } from "@/components/preview-host-bridge";
import { SiteHeader } from "@/components/layout/site-header";
import { SiteFooter } from "@/components/layout/site-footer";
import { SITE } from "@/lib/content";
import appCss from "../styles.css?url";

const jsonLd = JSON.stringify({
  "@context": "https://schema.org",
  "@type": "Organization",
  name: SITE.name,
  ...(SITE.url ? { url: SITE.url } : {}),
  ...(SITE.email ? { email: SITE.email } : {}),
  areaServed: "NP",
  description: SITE.description,
});

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: `${SITE.name} — ${SITE.tagline}` },
      { name: "description", content: SITE.description },
      { name: "theme-color", content: SITE.themeColor },
      { name: "color-scheme", content: "dark" },
    ],
    links: [
      { rel: "icon", type: "image/svg+xml", href: "/favicon.svg" },
      { rel: "stylesheet", href: appCss },
      { rel: "manifest", href: "/__grok/manifest.webmanifest" },
      { rel: "apple-touch-icon", href: "/__grok/icon-180.png" },
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Roboto:ital,wght@0,400;0,500;0,700;0,800;0,900;1,400;1,700&family=Roboto+Mono:wght@400;500;700&family=UnifrakturCook:wght@700&display=swap",
      },
      ...(SITE.url ? [{ rel: "canonical", href: SITE.url }] : []),
    ],
  }),
  component: RootDocument,
});

function RootDocument() {
  return (
    <html lang="en" className="antialiased" suppressHydrationWarning>
      <head>
        <HeadContent />
      </head>
      <body className="flex min-h-dvh flex-col bg-paper font-sans text-ink">
        <PreviewHostBridge />
        <a href="#main" className="skip-link">
          Skip to content
        </a>
        <AuthProvider>
          <SiteHeader />
          <div id="main" className="flex flex-1 flex-col">
            <Outlet />
          </div>
          <SiteFooter />
        </AuthProvider>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: jsonLd }}
        />
        <Scripts />
      </body>
    </html>
  );
}
