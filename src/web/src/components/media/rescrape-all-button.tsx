import { Button, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconRefresh } from "@tabler/icons-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { extractErrorMessage } from "@/lib/api-error";
import { apiFetch } from "@/lib/api-token";
import { confirm } from "@/lib/confirm";

const API = import.meta.env.VITE_API_URL || "";

const responseSchema = z.object({ submitted: z.number() });

/** 整库重新刮削: 不删除数据, 为每部影片提交一个不复用缓存的刮削任务; ``onlyWithKana`` 只处理仍含日文假名的. */
export function RescrapeAllButton({ onlyWithKana = false }: { onlyWithKana?: boolean }) {
  const { t } = useTranslation("metadata");
  const [running, setRunning] = useState(false);

  async function run() {
    const ok = await confirm({
      title: t(onlyWithKana ? "rescrapeAll.kana.confirmTitle" : "rescrapeAll.confirmTitle"),
      message: t(onlyWithKana ? "rescrapeAll.kana.confirmDesc" : "rescrapeAll.confirmDesc"),
      confirmLabel: t("rescrapeAll.confirm"),
    });
    if (!ok) return;
    setRunning(true);
    try {
      const resp = await apiFetch(`${API}/api/metadata/rescrape-all`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force: true, only_with_kana: onlyWithKana }),
      });
      const body: unknown = await resp.json().catch(() => null);
      if (!resp.ok) {
        notifications.show({ message: extractErrorMessage(body, t("rescrapeAll.failed")), color: "red" });
        return;
      }
      const parsed = responseSchema.parse(body);
      notifications.show({
        message: t("rescrapeAll.started", { count: parsed.submitted }),
        color: "blue",
      });
    } catch (err) {
      notifications.show({ message: extractErrorMessage(err, t("rescrapeAll.failed")), color: "red" });
    } finally {
      setRunning(false);
    }
  }

  return (
    <Tooltip label={t(onlyWithKana ? "rescrapeAll.kana.hint" : "rescrapeAll.hint")} multiline maw={280}>
      <Button
        variant="light"
        leftSection={<IconRefresh size={16} />}
        loading={running}
        onClick={() => void run()}
      >
        {t(onlyWithKana ? "rescrapeAll.kana.button" : "rescrapeAll.button")}
      </Button>
    </Tooltip>
  );
}
