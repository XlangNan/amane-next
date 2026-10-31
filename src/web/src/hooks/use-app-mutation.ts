import type { QueryKey } from "@tanstack/react-query";
import { type UseMutationOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { notifications } from "@mantine/notifications";
import { useTranslation } from "react-i18next";
import { extractErrorMessage } from "@/lib/api-error";

export interface AppMutationConfig<TData, TError, TVars> {
  mutationOptions: UseMutationOptions<TData, TError, TVars>;
  invalidates?: QueryKey[];
  successToast?: string | ((data: TData, vars: TVars) => string | null);
  onSuccess?: (data: TData, vars: TVars) => void;
}

export function useAppMutation<TData, TError, TVars>(
  config: AppMutationConfig<TData, TError, TVars>,
) {
  const { t } = useTranslation("common");
  const queryClient = useQueryClient();

  return useMutation<TData, TError, TVars>({
    ...config.mutationOptions,
    onSuccess: (data, vars, onMutateResult, context) => {
      if (config.invalidates?.length) {
        for (const queryKey of config.invalidates) {
          void queryClient.invalidateQueries({ queryKey });
        }
      }
      const msg =
        typeof config.successToast === "function"
          ? config.successToast(data, vars)
          : config.successToast;
      if (msg) {
        notifications.show({ color: "green", message: msg });
      }
      config.mutationOptions.onSuccess?.(data, vars, onMutateResult, context);
      config.onSuccess?.(data, vars);
    },
    onError: (error, vars, onMutateResult, context) => {
      notifications.show({
        color: "red",
        message: extractErrorMessage(error, t("toast.operationFailed")),
      });
      config.mutationOptions.onError?.(error, vars, onMutateResult, context);
    },
  });
}
