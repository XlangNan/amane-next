import { Box, Text } from "@mantine/core";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { sanitizeFeedHtml } from "@/lib/feeds/html";
import classes from "./feed-html.module.css";

export function FeedHtml({ html }: { html: string | null | undefined }) {
  const { t } = useTranslation("feeds");
  const sanitized = useMemo(() => {
    const raw = html?.trim() ?? "";
    return raw === "" ? "" : sanitizeFeedHtml(raw);
  }, [html]);

  if (sanitized === "") {
    return (
      <Text size="sm" c="dimmed">
        {t("reader.noContent")}
      </Text>
    );
  }

  return <Box className={classes.root} dangerouslySetInnerHTML={{ __html: sanitized }} />;
}
