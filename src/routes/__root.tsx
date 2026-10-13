import {
  createRootRoute,
  HeadContent,
  Outlet,
  Scripts,
  useRouterState,
} from "@tanstack/react-router";
import { AuthProvider } from "@/lib/auth/provider";
import { getAuthAvailability } from "@/lib/auth/availability";
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
  areaServed: "Worldwide",
  description: SITE.description,
});

export const Route = createRootRoute({
  // Auth availability is loaded once at the root so the header and footer
  // can apply the same gate as the login page: when sign-in is disabled or
  // unconfigured, nothing may advertise it. Fails closed, like /login does.
  loader: async () => {
    try {
      return await getAuthAvailability();
    } catch {
      return {
        authConfigured: false,
        googleConfigured: false,
        termsConfigured: false,
        termsUrl: null,
      };
    }
  },
  head: ({ matches }) => {
    const matchedPathname = matches[matches.length - 1]?.pathname ?? "/";
    const pathname = matchedPathname.length > 1
      ? matchedPathname.replace(/\/+$/, "")
      : matchedPathname;
    const canonicalHref = SITE.url
      ? pathname === "/"
        ? SITE.url
        : new URL(pathname, SITE.url).href
      : null;

    return {
      meta: [
        { charSet: "utf-8" },
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        { title: `${SITE.name} — ${SITE.tagline}` },
        { name: "description", content: SITE.description },
        { property: "og:title", content: SITE.name },
        { name: "apple-mobile-web-app-title", content: SITE.name },
        { name: "theme-color", content: SITE.themeColor },
        { name: "color-scheme", content: "dark" },
      ],
      links: [
        { rel: "icon", type: "image/svg+xml", href: "/favicon.svg" },
        { rel: "stylesheet", href: appCss },
        { rel: "manifest", href: "/manifest.webmanifest" },
        { rel: "preconnect", href: "https://fonts.googleapis.com" },
        { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
        {
          rel: "stylesheet",
          href: "https://fonts.googleapis.com/css2?family=Roboto:ital,wght@0,400;0,500;0,600;0,700;0,800;0,900;1,400;1,700&family=Roboto+Mono:wght@400;500;700&family=Archivo:wght@500;600;700;800&family=Source+Sans+3:ital,wght@0,400;0,600;0,700;1,400&family=Noto+Sans+Devanagari:wght@400;600;700&display=swap",
        },
        ...(canonicalHref ? [{ rel: "canonical", href: canonicalHref }] : []),
      ],
    };
  },
  component: RootDocument,
});

function RootDocument() {
  const isOwnerConsole = useRouterState({
    select: (state) => state.location.pathname === "/owner",
  });

  return (
    <html lang="en" className="antialiased" suppressHydrationWarning>
      <head>
        <HeadContent />
      </head>
      <body className="flex min-h-dvh flex-col bg-paper font-sans text-ink">
        <a href="#main" className="skip-link">
          Skip to content
        </a>
        <AuthProvider>
          {!isOwnerConsole ? <SiteHeader /> : null}
          <div id="main" className="flex flex-1 flex-col">
            <Outlet />
          </div>
          {!isOwnerConsole ? <SiteFooter /> : null}
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
