import {
  Alert,
  Badge,
  Card,
  Group,
  Loader,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from "@mantine/core";
import {
  IconAlertCircle,
  IconDeviceTv,
  IconFolders,
  IconLanguage,
  IconMovie,
  IconUsers,
} from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { listMetadataOptions } from "@/client/@tanstack/react-query.gen";
import { PosterCard } from "@/components/media/poster-card";
import { extractErrorMessage } from "@/lib/api-error";
import { apiFetch } from "@/lib/api-token";
import { formatRelativeTime } from "@/lib/format-relative-time";

const API = import.meta.env.VITE_API_URL || "";
const RECENT_POSTERS = 12;
const REFRESH_MS = 5000;

const taskStatusSchema = z.enum(["queued", "running", "done", "failed"]);

const dashboardSchema = z.object({
  metadata: z.number(),
  actors: z.number(),
  media_files: z.number(),
  libraries: z.number(),
  untranslated: z.number(),
  translate_enabled: z.boolean(),
  worker_paused: z.boolean(),
  tasks_queued: z.number(),
  tasks_running: z.number(),
  tasks_done: z.number(),
  tasks_failed: z.number(),
  recent_tasks: z.array(
    z.object({
      id: z.number(),
      type: z.string(),
      status: taskStatusSchema,
      label: z.string().nullable(),
      error: z.string().nullable(),
      created_at: z.string().nullable(),
      finished_at: z.string().nullable(),
    }),
  ),
});

type Dashboard = z.infer<typeof dashboardSchema>;
type TaskStatus = z.infer<typeof taskStatusSchema>;

const STATUS_COLOR: Record<TaskStatus, string> = {
  queued: "gray",
  running: "blue",
  done: "green",
  failed: "red",
};

async function fetchDashboard(): Promise<Dashboard> {
  const resp = await apiFetch(`${API}/api/dashboard`);
  const body: unknown = await resp.json().catch(() => null);
  if (!resp.ok) throw new Error(extractErrorMessage(body, `HTTP ${resp.status}`));
  return dashboardSchema.parse(body);
}

function StatCard({
  href,
  icon,
  color,
  label,
  value,
}: {
  href: string;
  icon: ReactNode;
  color: string;
  label: string;
  value: number;
}) {
  return (
    <Card
      withBorder
      padding="md"
      radius="md"
      component="a"
      href={href}
      style={{ textDecoration: "none", color: "inherit" }}
    >
      <Group wrap="nowrap" gap="md">
        <ThemeIcon size={44} radius="md" variant="light" color={color}>
          {icon}
        </ThemeIcon>
        <div>
          <Text size="xs" c="dimmed">
            {label}
          </Text>
          <Text fz={26} fw={700} lh={1.2}>
            {value.toLocaleString()}
          </Text>
        </div>
      </Group>
    </Card>
  );
}

export function DashboardPage() {
  const { t, i18n } = useTranslation("dashboard");
  const { t: tTasks } = useTranslation("tasks");

  const summary = useQuery({
    queryKey: ["dashboard"],
    queryFn: fetchDashboard,
    refetchInterval: REFRESH_MS,
  });
  const recent = useQuery({
    ...listMetadataOptions({
      query: { limit: RECENT_POSTERS, offset: 0, sort_by: "updated_at", order: "desc" },
    }),
    refetchInterval: REFRESH_MS * 3,
  });

  if (summary.isLoading) {
    return (
      <Group justify="center" py="xl">
        <Loader size="sm" />
      </Group>
    );
  }
  if (summary.error || !summary.data) {
    return (
      <Alert icon={<IconAlertCircle size={18} />} color="red" variant="light">
        {extractErrorMessage(summary.error, t("loadError"))}
      </Alert>
    );
  }

  const data = summary.data;
  const taskCounters: { key: TaskStatus; value: number }[] = [
    { key: "queued", value: data.tasks_queued },
    { key: "running", value: data.tasks_running },
    { key: "done", value: data.tasks_done },
    { key: "failed", value: data.tasks_failed },
  ];

  return (
    <Stack gap="lg">
      <Title order={2}>{t("title")}</Title>

      {data.worker_paused && (
        <Alert icon={<IconAlertCircle size={18} />} color="yellow" variant="light">
          {t("workerPaused")}
        </Alert>
      )}

      <SimpleGrid cols={{ base: 2, md: 4 }} spacing="md">
        <StatCard
          href="/meta"
          icon={<IconMovie size={24} />}
          color="blue"
          label={t("stats.metadata")}
          value={data.metadata}
        />
        <StatCard
          href="/actors"
          icon={<IconUsers size={24} />}
          color="grape"
          label={t("stats.actors")}
          value={data.actors}
        />
        <StatCard
          href="/libraries"
          icon={<IconDeviceTv size={24} />}
          color="teal"
          label={t("stats.mediaFiles")}
          value={data.media_files}
        />
        <StatCard
          href="/libraries"
          icon={<IconFolders size={24} />}
          color="orange"
          label={t("stats.libraries")}
          value={data.libraries}
        />
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        <Paper withBorder p="md" radius="md">
          <Group justify="space-between" mb="sm">
            <Text fw={600}>{t("tasks.title")}</Text>
            <Text component="a" href="/tasks" size="sm" c="dimmed">
              {t("tasks.viewAll")}
            </Text>
          </Group>
          <Group gap="xs" mb="md">
            {taskCounters.map((item) => (
              <Badge key={item.key} color={STATUS_COLOR[item.key]} variant="light" size="lg">
                {tTasks(`status.${item.key}`)} {item.value.toLocaleString()}
              </Badge>
            ))}
          </Group>
          {data.recent_tasks.length === 0 ? (
            <Text size="sm" c="dimmed">
              {t("tasks.empty")}
            </Text>
          ) : (
            <Stack gap={6}>
              {data.recent_tasks.map((task) => (
                <Group key={task.id} justify="space-between" wrap="nowrap" gap="xs">
                  <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
                    <Badge color={STATUS_COLOR[task.status]} variant="dot" size="sm">
                      {tTasks(`status.${task.status}`)}
                    </Badge>
                    <Text size="sm" truncate>
                      {/* 任务类型运行时才知, 动态键例外. */}
                      {tTasks(`submit.types.${task.type}` as never, { defaultValue: task.type })}
                      {task.label ? ` · ${task.label}` : ""}
                    </Text>
                  </Group>
                  <Text size="xs" c="dimmed" style={{ flexShrink: 0 }}>
                    {task.created_at
                      ? formatRelativeTime(task.created_at, i18n.language, t("justNow"))
                      : ""}
                  </Text>
                </Group>
              ))}
            </Stack>
          )}
        </Paper>

        <Paper withBorder p="md" radius="md">
          <Group gap="xs" mb="sm">
            <IconLanguage size={18} />
            <Text fw={600}>{t("translate.title")}</Text>
            <Badge color={data.translate_enabled ? "green" : "gray"} variant="light">
              {data.translate_enabled ? t("translate.on") : t("translate.off")}
            </Badge>
          </Group>
          <Text fz={26} fw={700} lh={1.2}>
            {data.untranslated.toLocaleString()}
          </Text>
          <Text size="sm" c="dimmed" mt={4}>
            {t("translate.untranslatedHint")}
          </Text>
          {data.untranslated > 0 && (
            <Text size="sm" mt="sm">
              {data.translate_enabled ? t("translate.actionOn") : t("translate.actionOff")}
            </Text>
          )}
        </Paper>
      </SimpleGrid>

      <Paper withBorder p="md" radius="md">
        <Group justify="space-between" mb="sm">
          <Text fw={600}>{t("recent.title")}</Text>
          <Text component="a" href="/meta" size="sm" c="dimmed">
            {t("recent.viewAll")}
          </Text>
        </Group>
        {recent.data && recent.data.items.length > 0 ? (
          <SimpleGrid cols={{ base: 3, sm: 4, md: 6 }} spacing="sm">
            {recent.data.items.map((item) => (
              <PosterCard key={item.id} item={item} />
            ))}
          </SimpleGrid>
        ) : (
          <Text size="sm" c="dimmed">
            {t("recent.empty")}
          </Text>
        )}
      </Paper>
    </Stack>
  );
}
