import type { Metadata } from "next";
import "./globals.css";
import Nav from "@/components/Nav";

export const metadata: Metadata = {
  title: "ForgeOS — Intelligence, made legible",
  description: "Forge observes reality, verifies evidence, and turns uncertainty into measured action.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en" className="dark"><body className="min-h-screen"><Nav /><main className="mx-auto max-w-7xl px-5 py-8 sm:px-6 md:py-10">{children}</main></body></html>;
}
