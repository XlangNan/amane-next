import { defineConfig } from "i18next-cli";

export default defineConfig({
  locales: ["zh-CN", "en"],
  extract: {
    input: ["src/**/*.{ts,tsx}"],
    output: "src/i18n/locales/{{language}}/{{namespace}}.json",
    ignore: ["node_modules/**", "src/i18n/**"],
    outputFormat: "json",
    functions: ["t", "*.t"],
    transComponents: ["Trans"],
    useTranslationNames: ["useTranslation"],
    defaultNS: "common",
    keySeparator: ".",
    removeUnusedKeys: false,
    sort: false,
  },
  types: {
    input: ["src/i18n/locales/zh-CN/**/*.json"],
    basePath: "src/i18n/locales/zh-CN",
    output: "src/i18n/i18next.d.ts",
  },
});
