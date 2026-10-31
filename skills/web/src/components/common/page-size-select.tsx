import { Button, Menu } from "@mantine/core";
import { IconListNumbers } from "@tabler/icons-react";
import { useTranslation } from "react-i18next";
import { PAGE_SIZE_OPTIONS, type PageSize, type PageSizeKey } from "@/lib/page-size";
import { useUIStore } from "@/stores/ui";

interface PageSizeSelectProps {
  sizeKey: PageSizeKey;
  /** 调用方应重置 URL `page` 为 1, 并视需要清空多选. */
  onChanged?: (size: PageSize) => void;
}

/** 紧凑分页大小: 按钮显示"N/页", 菜单选值 - 无独立 label 下拉. */
export function PageSizeSelect({ sizeKey, onChanged }: PageSizeSelectProps) {
  const { t } = useTranslation("common");
  const value = useUIStore((s) => s.pageSizes[sizeKey]);
  const setPageSize = useUIStore((s) => s.setPageSize);
  const options = PAGE_SIZE_OPTIONS[sizeKey];

  return (
    <Menu shadow="md" width={120} position="bottom-start">
      <Menu.Target>
        <Button variant="default" size="sm" leftSection={<IconListNumbers size={16} />}>
          {t("pagination.pageSizeShort", { size: value })}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        {options.map((n) => (
          <Menu.Item
            key={n}
            fw={n === value ? 600 : undefined}
            onClick={() => {
              setPageSize(sizeKey, n as PageSize);
              onChanged?.(n as PageSize);
            }}
          >
            {t("pagination.pageSizeShort", { size: n })}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}
