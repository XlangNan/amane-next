import { Select } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { listLibrariesOptions } from "@/client/@tanstack/react-query.gen";

interface LibraryPickerProps {
  value: number | null;
  onChange: (value: number | null) => void;
  disabled?: boolean;
  placeholder?: string;
  /** Allow clearing the selection (nullable schemas). */
  clearable?: boolean;
}

export function LibraryPicker({
  value,
  onChange,
  disabled = false,
  placeholder,
  clearable = false,
}: LibraryPickerProps) {
  const { t } = useTranslation("common");
  const { data, isLoading } = useQuery(listLibrariesOptions());
  const items = data?.items ?? [];

  return (
    <Select
      data={items.map((lib) => ({
        value: String(lib.id),
        label: lib.name ? `${lib.name} (${lib.path})` : lib.path,
      }))}
      value={value == null ? null : String(value)}
      onChange={(v) => {
        if (v == null) {
          onChange(null);
          return;
        }
        onChange(Number.parseInt(v, 10));
      }}
      placeholder={placeholder ?? t("nav.library")}
      disabled={disabled}
      clearable={clearable}
      searchable
      nothingFoundMessage={isLoading ? t("status.loading") : t("status.empty")}
    />
  );
}
