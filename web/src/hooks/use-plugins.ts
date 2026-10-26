import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  installPluginMutation,
  listPluginsOptions,
  reloadPluginsMutation,
  uninstallPluginMutation,
  updatePluginMutation,
} from "@/client/@tanstack/react-query.gen";
import { useAppMutation } from "@/hooks/use-app-mutation";

/** hey-api keys embed `baseUrl`; match on `_id` so catalog writes still hit the list query. */
const pluginListKey = [{ _id: "listPlugins" }];
const pluginCatalogKeys = [pluginListKey, ["config-schema"]];

export function usePlugins() {
  return useQuery(listPluginsOptions());
}

export function useUpdatePlugin() {
  const { t } = useTranslation("common");
  return useAppMutation({
    mutationOptions: updatePluginMutation(),
    invalidates: [pluginListKey],
    successToast: t("toast.configSaved"),
  });
}

export function useInstallPlugin() {
  const { t } = useTranslation("plugins");
  return useAppMutation({
    mutationOptions: installPluginMutation(),
    invalidates: [...pluginCatalogKeys],
    successToast: t("installed"),
  });
}

export function useUninstallPlugin() {
  const { t } = useTranslation("plugins");
  return useAppMutation({
    mutationOptions: uninstallPluginMutation(),
    invalidates: [...pluginCatalogKeys],
    successToast: t("uninstalled"),
  });
}

export function useReloadPlugins() {
  const { t } = useTranslation("plugins");
  return useAppMutation({
    mutationOptions: reloadPluginsMutation(),
    invalidates: [...pluginCatalogKeys],
    successToast: t("reloaded"),
  });
}
