import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        forge: {
          void: "#020208",
          bg: "#05050c",
          panel: "#0a0a14",
          panel2: "#0e0e1a",
          panelElevated: "#12121f",
          border: "rgba(255,255,255,0.06)",
          borderBright: "rgba(255,255,255,0.12)",
          accent: "#8b6cff",
          accent2: "#3dd9ff",
          revenue: "#34d399",
          danger: "#ff5c7a",
          warn: "#ffb84d",
          muted: "#8a8aa3",
        },
      },
      boxShadow: {
        glow: "0 0 32px -8px rgba(139,108,255,0.45)",
        glowBlue: "0 0 32px -8px rgba(61,217,255,0.35)",
        glowRevenue: "0 0 32px -8px rgba(52,211,153,0.4)",
        premium: "0 4px 24px -4px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.03)",
        premiumHover: "0 8px 32px -6px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.06)",
      },
      fontFamily: {
        display: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: {
        "2xs": ["0.65rem", { lineHeight: "1rem" }],
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.25rem",
      },
      keyframes: {
        pulseGlow: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
        flow: {
          "0%": { backgroundPosition: "0% 50%" },
          "100%": { backgroundPosition: "200% 50%" },
        },
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        "pulse-glow": "pulseGlow 2.2s ease-in-out infinite",
        flow: "flow 3.2s linear infinite",
        "fade-up": "fadeUp 0.35s ease-out",
        shimmer: "shimmer 2.5s linear infinite",
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
};
export default config;
