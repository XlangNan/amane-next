import { Alert, Button, Group, Stack, Text } from "@mantine/core";
import { IconCheck, IconX } from "@tabler/icons-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { extractErrorMessage } from "@/lib/api-error";
import { apiFetch } from "@/lib/api-token";

const API = import.meta.env.VITE_API_URL || "";

const resultSchema = z.object({
  ok: z.boolean(),
  source: z.string(),
  text: z.string().nullable(),
  provider: z.string().nullable(),
  error: z.string().nullable(),
});

type TestResult = z.infer<typeof resultSchema>;

/** 用已保存的网络设置真实请求一次谷歌翻译, 失败原因直接显示. */
export function TranslateTest() {
  const { t } = useTranslation("settings");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<TestResult | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setResult(null);
    setFailure(null);
    try {
      const resp = await apiFetch(`${API}/api/translate/test`, { method: "POST" });
      const body: unknown = await resp.json().catch(() => null);
      if (!resp.ok) {
        setFailure(extractErrorMessage(body, t("translateTest.failed")));
        return;
      }
      setResult(resultSchema.parse(body));
    } catch (err) {
      setFailure(extractErrorMessage(err, t("translateTest.failed")));
    } finally {
      setRunning(false);
    }
  }

  return (
    <Stack gap="xs" mt="md">
      <Group gap="sm">
        <Button variant="light" loading={running} onClick={() => void run()}>
          {t("translateTest.button")}
        </Button>
        <Text size="xs" c="dimmed">
          {t("translateTest.hint")}
        </Text>
      </Group>
      {result?.ok === true && (
        <Alert color="green" variant="light" icon={<IconCheck size={18} />}>
          {t("translateTest.ok", {
            source: result.source,
            text: result.text ?? "",
            provider: result.provider ?? "",
          })}
        </Alert>
      )}
      {result?.ok === false && (
        <Alert color="red" variant="light" icon={<IconX size={18} />}>
          {result.error}
        </Alert>
      )}
      {failure !== null && (
        <Alert color="red" variant="light" icon={<IconX size={18} />}>
          {failure}
        </Alert>
      )}
    </Stack>
  );
}
