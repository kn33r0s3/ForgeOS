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

const APP_NAME = "Forge";

const jsonLd = JSON.stringify({
  "@context": "https://schema.org",
  "@type": "Organization",
  name: SITE.legalName,
  alternateName: SITE.name,
  url: SITE.url,
  email: SITE.email,
  areaServed: "NP",
  description: SITE.description,
});

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: `${APP_NAME} — ${SITE.tagline}` },
      { name: "description", content: SITE.description },
      { name: "theme-color", content: "#0a0a0c" },
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
        href: "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&family=Space+Grotesk:wght@500;600;700&display=swap",
      },
      { rel: "canonical", href: SITE.url },
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
      <body className="flex min-h-dvh flex-col bg-void font-sans text-fg">
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
