import { Alert, Button, Group, Stack, Text } from "@mantine/core";
import { IconCheck, IconX } from "@tabler/icons-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { extractErrorMessage } from "@/lib/api-error";
import { apiFetch } from "@/lib/api-token";

const API = import.meta.env.VITE_API_URL || "";

const resultSchema = z.object({
  source: z.string(),
  results: z.array(
    z.object({
      provider: z.string(),
      ok: z.boolean(),
      text: z.string().nullable(),
      error: z.string().nullable(),
    }),
  ),
});

type TestResult = z.infer<typeof resultSchema>;

/** 用已保存的网络设置对每个翻译源各真实请求一次, 分别显示结果与失败原因. */
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
      {result?.results.map((item) =>
        item.ok ? (
          <Alert key={item.provider} color="green" variant="light" icon={<IconCheck size={18} />}>
            {t("translateTest.ok", {
              provider: item.provider,
              source: result.source,
              text: item.text ?? "",
            })}
          </Alert>
        ) : (
          <Alert key={item.provider} color="red" variant="light" icon={<IconX size={18} />}>
            {t("translateTest.fail", { provider: item.provider, error: item.error ?? "" })}
          </Alert>
        ),
      )}
      {failure !== null && (
        <Alert color="red" variant="light" icon={<IconX size={18} />}>
          {failure}
        </Alert>
      )}
    </Stack>
  );
}
