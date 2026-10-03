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
      "max-lines": [
        "warn",
        { max: 200, skipBlankLines: true, skipComments: true },
      ],
    },
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
  prettier,
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts", "lib/api/schema.d.ts"]),
]);

export default eslintConfig;
