import {
  createRootRoute,
  HeadContent,
  Outlet,
  redirect,
  Scripts,
  useRouterState,
} from "@tanstack/react-router";
import { AuthProvider } from "@/lib/auth/provider";
import { getAuthAvailability } from "@/lib/auth/availability";
import { SiteHeader } from "@/components/layout/site-header";
import { SiteFooter } from "@/components/layout/site-footer";
import { SITE } from "@/lib/content";
import appCss from "../styles.css?url";

const MAINTENANCE_MODE = import.meta.env.VITE_HAMI_MAINTENANCE_MODE === "true";

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
  beforeLoad: ({ location }) => {
    if (MAINTENANCE_MODE && location.pathname !== "/") {
      throw redirect({ to: "/", replace: true });
    }
  },
  // Auth availability is loaded once at the root so the header and footer
  // can apply the same gate as the login page: when sign-in is disabled or
  // unconfigured, nothing may advertise it. Fails closed, like /login does.
  loader: async () => {
    if (MAINTENANCE_MODE) {
      return {
        authConfigured: false,
        googleConfigured: false,
        termsConfigured: false,
        termsUrl: null,
      };
    }
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
    if (MAINTENANCE_MODE) {
      return {
        meta: [
          { charSet: "utf-8" },
          { name: "viewport", content: "width=device-width, initial-scale=1" },
          { title: "Hami — Under Development" },
          {
            name: "description",
            content: "Hami's public website is temporarily under development.",
          },
          { name: "robots", content: "noindex, nofollow, noarchive, nosnippet" },
          { name: "googlebot", content: "noindex, nofollow, noarchive, nosnippet" },
          { name: "color-scheme", content: "light" },
        ],
        links: [
          { rel: "icon", type: "image/svg+xml", href: "/favicon.svg" },
          { rel: "stylesheet", href: appCss },
        ],
      };
    }
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
        { property: "og:image", content: `${SITE.url}/og.jpg` },
        { property: "og:image:width", content: "1200" },
        { property: "og:image:height", content: "630" },
        { name: "twitter:card", content: "summary_large_image" },
        { name: "twitter:image", content: `${SITE.url}/og.jpg` },
        { name: "apple-mobile-web-app-title", content: SITE.name },
        { name: "theme-color", content: SITE.themeColor },
        { name: "color-scheme", content: "light" },
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

  if (MAINTENANCE_MODE) {
    return (
      <html lang="en" className="antialiased">
        <head>
          <HeadContent />
        </head>
        <body className="min-h-dvh bg-paper font-sans text-ink">
          <main className="relative isolate flex min-h-dvh items-center justify-center overflow-hidden px-5 py-10">
            <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
              <div className="absolute -left-24 -top-24 size-72 rounded-full bg-accent/10 blur-3xl" />
              <div className="absolute -bottom-28 -right-20 size-80 rounded-full bg-ink/5 blur-3xl" />
            </div>
            <section className="relative w-full max-w-3xl border border-line bg-white/90 p-8 shadow-sm sm:p-12 lg:p-16">
              <div className="flex items-center gap-3">
                <div className="grid size-12 place-items-center border border-ink bg-ink font-display text-xl font-black text-paper">
                  H
                </div>
                <div>
                  <p className="font-mono text-xs font-bold uppercase tracking-[0.28em]">
                    Hami Systems
                  </p>
                  <p className="mt-1 text-sm text-muted" lang="ne">
                    हामी
                  </p>
                </div>
              </div>
              <div className="mt-12 inline-flex items-center gap-2 border border-line px-3 py-2 font-mono text-[11px] font-bold uppercase tracking-[0.15em] text-muted">
                <span aria-hidden="true" className="size-2 rounded-full bg-accent" />
                Public site · Temporarily closed
              </div>
              <h1 className="mt-6 max-w-2xl font-display text-[clamp(2.6rem,7vw,5.25rem)] font-extrabold leading-[0.98] tracking-tight text-ink">
                Under development.
              </h1>
              <p className="mt-6 max-w-xl text-base leading-7 text-muted sm:text-lg">
                We’re improving Hami’s public experience. The rest of the site is temporarily unavailable while the work continues.
              </p>
              <p className="mt-3 max-w-xl text-base leading-7 text-muted" lang="ne">
                हामी सार्वजनिक अनुभव सुधार्दैछौँ।
              </p>
              <div className="mt-10 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5 text-sm text-muted">
                <span>Hami Systems</span>
                <span>Built in Nepal · Serving everywhere</span>
              </div>
            </section>
          </main>
        </body>
      </html>
    );
  }

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
