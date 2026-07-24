// Imports eslint-config-next's flat-config-native shareable configs
// directly, rather than routing them through @eslint/eslintrc's
// FlatCompat.extends() (the original scaffold pattern). FlatCompat exists
// to convert legacy .eslintrc-style configs into flat config, but
// eslint-config-next@16 already ships flat config natively -- pushing it
// through that legacy conversion layer anyway is what triggers a real,
// documented crash on ESLint 9.35+ ("TypeError: Converting circular
// structure to JSON ... property 'react' closes the circle", see
// https://github.com/vercel/next.js/issues/85244 and
// https://github.com/eslint/eslint/issues/20237): the legacy config
// validator tries to JSON.stringify a config object that legitimately
// contains a circular reference (a plugin's own recommended config
// referencing the plugin object itself), which flat config's own
// validator doesn't choke on but the old one does. This is the fix
// Next.js's own docs recommend (nextjs.org/docs/app/api-reference/config/eslint#setup-eslint).
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores(["node_modules/**", ".next/**", "out/**", "build/**", "next-env.d.ts"]),
]);

export default eslintConfig;
