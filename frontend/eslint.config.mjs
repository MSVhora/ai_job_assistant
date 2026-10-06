import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import prettier from "eslint-config-prettier/flat";
import jsxA11y from "eslint-plugin-jsx-a11y";
import testingLibrary from "eslint-plugin-testing-library";
import vitest from "@vitest/eslint-plugin";
import tseslint from "typescript-eslint";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    files: ["**/*.{ts,tsx,mts}"],
    extends: [tseslint.configs.strictTypeChecked, tseslint.configs.stylisticTypeChecked],
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      ...jsxA11y.flatConfigs.strict.rules,
      // Numbers in template literals are safe and read better than String(n).
      "@typescript-eslint/restrict-template-expressions": ["error", { allowNumber: true }],
      // `||` on strings is deliberate: an empty string must fall back too.
      "@typescript-eslint/prefer-nullish-coalescing": [
        "error",
        { ignorePrimitives: { string: true } },
      ],
    },
  },
  {
    files: ["app/**/*.tsx", "components/**/*.tsx"],
    rules: {
      "max-lines": ["error", { max: 200, skipBlankLines: true, skipComments: true }],
    },
  },
  {
    // apiFetch<T> / apiFetchWithTotal<T> are unchecked response casts by design.
    files: ["lib/api/client.ts"],
    rules: { "@typescript-eslint/no-unnecessary-type-parameters": "off" },
  },
  {
    files: ["**/*.test.{ts,tsx}"],
    extends: [testingLibrary.configs["flat/react"]],
    plugins: { vitest },
    rules: {
      ...vitest.configs.recommended.rules,
      "max-lines": "off",
    },
  },
  {
    // The Radix dialog portals an unlabeled <form>; no role or label can reach it.
    files: ["components/features/jobs/SearchStepperModal.test.tsx"],
    rules: { "testing-library/no-node-access": "off" },
  },
  prettier,
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts", "lib/api/schema.d.ts"]),
]);

export default eslintConfig;
