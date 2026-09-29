import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

/** Flat ESLint config for the TanStack Start app-builder template. */
export default tseslint.config(
  {
    ignores: [
      "dist/**",
      ".output/**",
      ".vercel/**",
      ".nitro/**",
      "node_modules/**",
      "src/routeTree.gen.ts",
      // Generated build output, never source: `frontend/` is the legacy Next
      // app, and linting its compiled chunks made `npm run check` fail with
      // hundreds of `require()` errors that no source change could fix.
      "**/.next/**",
      "**/coverage/**",
      // Two embedded projects with their own toolchains ship inside this repo:
      // `frontend/` (legacy Next.js app — `next.config.js`/`next-env.d.ts` are
      // its own conventions) and `sanipops_clean/` (a vendored copy of the app
      // template, 228 files, with its own eslint.config.mjs). This config
      // describes *this* app; linting the others reports their conventions as
      // failures here.
      "frontend/**",
      "sanipops_clean/**",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx,js,jsx,mjs,cjs}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
  // Disable rules that conflict with Prettier formatting.
  prettier,
);
