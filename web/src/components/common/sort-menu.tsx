import { Button, Menu } from "@mantine/core";
import { IconArrowDown, IconArrowUp, IconArrowsSort } from "@tabler/icons-react";

export interface SortMenuOption<T extends string> {
  value: T;
  label: string;
}

export interface SortMenuProps<T extends string> {
  options: readonly SortMenuOption<T>[];
  sortBy: T | undefined;
  order: "asc" | "desc" | undefined;
  defaultSortBy: T;
  defaultOrder?: "asc" | "desc";
  onChange: (sortBy: T, order: "asc" | "desc") => void;
}

/**
 * 合并"排序字段 + 升降序"为单一菜单按钮.
 * 选中新字段用 defaultOrder; 再点同一字段则翻转升降序.
 */
export function SortMenu<T extends string>({
  options,
  sortBy,
  order,
  defaultSortBy,
  defaultOrder = "desc",
  onChange,
}: SortMenuProps<T>) {
  const active = sortBy ?? defaultSortBy;
  const activeOrder = order ?? defaultOrder;
  const activeLabel = options.find((o) => o.value === active)?.label ?? active;
  const OrderIcon = activeOrder === "asc" ? IconArrowUp : IconArrowDown;

  return (
    <Menu shadow="md" width={200} position="bottom-end">
      <Menu.Target>
        <Button
          variant="default"
          size="sm"
          leftSection={<IconArrowsSort size={16} />}
          rightSection={<OrderIcon size={14} />}
        >
          {activeLabel}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        {options.map((opt) => {
          const selected = opt.value === active;
          return (
            <Menu.Item
              key={opt.value}
              rightSection={
                selected ? (
                  activeOrder === "asc" ? (
                    <IconArrowUp size={14} />
                  ) : (
                    <IconArrowDown size={14} />
                  )
                ) : undefined
              }
              fw={selected ? 600 : undefined}
              onClick={() => {
                if (selected) {
                  onChange(opt.value, activeOrder === "asc" ? "desc" : "asc");
                } else {
                  onChange(opt.value, defaultOrder);
                }
              }}
            >
              {opt.label}
            </Menu.Item>
          );
        })}
      </Menu.Dropdown>
    </Menu>
  );
}
