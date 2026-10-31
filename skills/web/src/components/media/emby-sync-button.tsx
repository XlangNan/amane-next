import {
  Alert,
  Button,
  Group,
  Modal,
  MultiSelect,
  SegmentedControl,
  Stack,
  Text,
  Tooltip,
} from "@mantine/core";
import { IconRefresh } from "@tabler/icons-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { extractErrorMessage } from "@/lib/api-error";
import { apiFetch } from "@/lib/api-token";

const API = import.meta.env.VITE_API_URL || "";

const librariesSchema = z.array(z.string());

const syncReportSchema = z.object({
  emby_persons: z.number(),
  skipped_has_image: z.number(),
  targeted: z.number(),
  uploaded: z.number(),
  no_local_image: z.number(),
  not_in_amane: z.number(),
  failed: z.number(),
  no_local_names: z.array(z.string()),
  not_in_amane_names: z.array(z.string()),
  failed_names: z.array(z.string()),
  error: z.string().nullable(),
});
type SyncReport = z.infer<typeof syncReportSchema>;

type Mode = "fill" | "overwrite";

/**
 * 演员页的 Emby 头像同步: 弹窗里选 Emby 媒体库 (留空 = 全部) 与模式 (只补缺失 / 覆盖已有),
 * 用「设置 → Emby」里已保存的地址与密钥立即同步一轮, 并在弹窗里显示本轮统计.
 */
export function EmbySyncButton() {
  const { t } = useTranslation("settings");
  const [opened, setOpened] = useState(false);
  const [libraries, setLibraries] = useState<string[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [mode, setMode] = useState<Mode>("fill");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [report, setReport] = useState<SyncReport | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  async function open() {
    setOpened(true);
    setReport(null);
    setRunError(null);
    setLoadError(null);
    try {
      const resp = await apiFetch(`${API}/api/emby/libraries`);
      const body: unknown = await resp.json().catch(() => null);
      if (!resp.ok) {
        setLoadError(extractErrorMessage(body, t("embySync.loadFailed")));
        return;
      }
      setLibraries(librariesSchema.parse(body));
    } catch (err) {
      setLoadError(extractErrorMessage(err, t("embySync.loadFailed")));
    }
  }

  async function run() {
    setRunning(true);
    setReport(null);
    setRunError(null);
    try {
      const resp = await apiFetch(`${API}/api/emby/sync-actors`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ libraries: selected, overwrite: mode === "overwrite" }),
      });
      const body: unknown = await resp.json().catch(() => null);
      if (!resp.ok) {
        setRunError(extractErrorMessage(body, t("embySync.failed")));
        return;
      }
      const parsed = syncReportSchema.parse(body);
      if (parsed.error !== null) {
        setRunError(parsed.error);
        return;
      }
      setReport(parsed);
    } catch (err) {
      setRunError(extractErrorMessage(err, t("embySync.failed")));
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <Tooltip label={t("embySync.hint")} multiline maw={260}>
        <Button
          variant="light"
          leftSection={<IconRefresh size={16} />}
          onClick={() => void open()}
        >
          {t("embySync.button")}
        </Button>
      </Tooltip>
      <Modal opened={opened} onClose={() => setOpened(false)} title={t("embySync.title")} size="md">
        <Stack gap="md">
          {loadError !== null && (
            <Alert color="red" variant="light">
              {loadError}
            </Alert>
          )}
          <MultiSelect
            label={t("embySync.libraries")}
            placeholder={t("embySync.librariesPlaceholder")}
            data={libraries}
            value={selected}
            onChange={setSelected}
            clearable
            searchable
            comboboxProps={{ withinPortal: true }}
          />
          <Stack gap={4}>
            <Text size="sm" fw={500}>
              {t("embySync.mode")}
            </Text>
            <SegmentedControl
              value={mode}
              onChange={(v) => setMode(v === "overwrite" ? "overwrite" : "fill")}
              data={[
                { value: "fill", label: t("embySync.modeFill") },
                { value: "overwrite", label: t("embySync.modeOverwrite") },
              ]}
            />
            <Text size="xs" c="dimmed">
              {mode === "fill" ? t("embySync.modeFillHint") : t("embySync.modeOverwriteHint")}
            </Text>
          </Stack>
          {runError !== null && (
            <Alert color="red" variant="light">
              {runError}
            </Alert>
          )}
          {report !== null && <ReportView report={report} />}
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setOpened(false)}>
              {t("embySync.close")}
            </Button>
            <Button loading={running} onClick={() => void run()}>
              {t("embySync.run")}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}

function ReportView({ report }: { report: SyncReport }) {
  const { t } = useTranslation("settings");
  const lines: string[] = [
    t("embySync.summary", {
      persons: report.emby_persons,
      skipped: report.skipped_has_image,
      targeted: report.targeted,
      uploaded: report.uploaded,
    }),
  ];
  if (report.no_local_image > 0) {
    lines.push(
      t("embySync.noLocal", {
        count: report.no_local_image,
        names: report.no_local_names.join("、"),
      }),
    );
  }
  if (report.not_in_amane > 0) {
    lines.push(
      t("embySync.notInAmane", {
        count: report.not_in_amane,
        names: report.not_in_amane_names.join("、"),
      }),
    );
  }
  if (report.failed > 0) {
    lines.push(
      t("embySync.failedLine", { count: report.failed, names: report.failed_names.join("、") }),
    );
  }
  return (
    <Alert color={report.failed > 0 ? "yellow" : "green"} variant="light">
      <Stack gap={4}>
        {lines.map((line) => (
          <Text key={line} size="sm">
            {line}
          </Text>
        ))}
      </Stack>
    </Alert>
  );
}
