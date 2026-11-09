import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // Raw HTML is only allowed in audited components (JsonLd now, RichText in Phase 2).
      "react/no-danger": "error",
    },
  },
  // These files are the audited exceptions.
  { files: ["src/components/ui/JsonLd.tsx"], rules: { "react/no-danger": "off" } },
  // <Media> is the one image component (pre-resized variants, explicit width/height).
  { files: ["src/components/ui/Media.tsx"], rules: { "@next/next/no-img-element": "off" } },
  // Admin screens show pictures that are already resized when uploaded (and the static logo).
  { files: ["src/components/admin/**"], rules: { "@next/next/no-img-element": "off" } },
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
]);

export default eslintConfig;
