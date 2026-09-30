import { createRouter } from "@tanstack/react-router";
import { AppErrorComponent } from "@/lib/error-component";
import { NotFoundPage } from "@/components/not-found";
import { routeTree } from "./routeTree.gen";

export function getRouter() {
  return createRouter({
    routeTree,
    defaultErrorComponent: AppErrorComponent,
    defaultNotFoundComponent: NotFoundPage,
    scrollRestoration: true,
    // Every route's component is its own lazily-imported chunk, so a hover or
    // focus prefetches the code (and its loaders) and the click paints at once
    // instead of waiting on a chunk round trip.
    defaultPreload: "intent",
    defaultPreloadDelay: 30,
    defaultPreloadStaleTime: 30_000,
  });
}
