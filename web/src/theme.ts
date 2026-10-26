import { createTheme, type MantineColorsTuple } from "@mantine/core";

const brand: MantineColorsTuple = [
  "#e8f3ff",
  "#d0e4ff",
  "#a1c6ff",
  "#6ea6ff",
  "#458bfe",
  "#2b7afe",
  "#1a71ff",
  "#0060e4",
  "#0055cc",
  "#0049b4",
];

export const theme = createTheme({
  primaryColor: "brand",
  colors: { brand },
  fontFamily: '"IBM Plex Sans", "Noto Sans SC", "Segoe UI", system-ui, -apple-system, sans-serif',
  fontFamilyMonospace: '"IBM Plex Mono", "JetBrains Mono", ui-monospace, monospace',
  defaultRadius: "md",
  headings: {
    fontFamily: '"IBM Plex Sans", "Noto Sans SC", system-ui, sans-serif',
    fontWeight: "600",
  },
});
