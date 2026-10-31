import { Alert, Center, Loader, Stack } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { type QueryKey, type UseQueryOptions, useQuery } from "@tanstack/react-query";
import { type ReactNode, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { EnumToggle } from "@/components/common/enum-toggle";
import { extractErrorMessage } from "@/lib/api-error";
import { encodeFormBody } from "./encode";
import { FieldChrome } from "./fields/field-chrome";
import { type JSONSchemaObject, resolveDiscriminator, resolveSchema } from "./schema";
import { SchemaForm } from "./schema-form";

type SchemaObject = { [key: string]: unknown };

/** Strip the discriminator const field so SchemaForm does not render it. */
function stripDiscriminatorField(schema: JSONSchemaObject, propertyName: string): JSONSchemaObject {
  const props = schema.properties ?? {};
  const { [propertyName]: _, ...rest } = props;
  return {
    ...schema,
    properties: rest,
    required: (schema.required ?? []).filter((k) => k !== propertyName),
  };
}

/** Seed form values from schema defaults (fallback null / empty). */
function defaultsFromSchema(schema: JSONSchemaObject): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, field] of Object.entries(schema.properties ?? {})) {
    if (typeof field === "boolean") continue;
    if ("default" in field && field.default !== undefined) {
      out[key] = field.default;
      continue;
    }
    if (field.type === "boolean") {
      out[key] = false;
    } else if (field.type === "array") {
      out[key] = [];
    } else if (field.type === "string") {
      out[key] = "";
    } else {
      out[key] = null;
    }
  }
  return out;
}

function sanitizeValues(
  values: Record<string, unknown>,
  schema: JSONSchemaObject,
): Record<string, unknown> {
  return encodeFormBody(schema, values);
}

export interface DiscriminatedSchemaFormProps<T extends string, TQueryKey extends QueryKey> {
  /** Discriminator values shown in the type selector. */
  types: readonly T[];
  defaultType: T;
  /** When false, schema query is disabled (e.g. modal closed). */
  active?: boolean;
  /**
   * Query options for the discriminator root schema (`GET .../schema`).
   * `TQueryKey` is inferred from hey-api `get*SchemaOptions()` so call sites type-check.
   */
  schemaQuery: UseQueryOptions<SchemaObject, Error, SchemaObject, TQueryKey>;
  /** i18n prefix for field labels (default `tasks:submit`). */
  i18nPrefix?: string;
  submitLabel?: string;
  saving: boolean;
  /** Extra disable gate (e.g. schedule cron empty). */
  submitDisabled?: boolean;
  /** Content above the type selector (envelope fields like name/cron). */
  header?: ReactNode;
  onSubmit: (value: { type: T } & Record<string, unknown>) => void;
}

/**
 * Shell for discriminator-union create forms (task submit / schedule submission).
 *
 * Owns type EnumToggle + variant SchemaForm (`create`); callers supply
 * schema query options and handle the assembled `{ type, ...fields }` payload.
 */
export function DiscriminatedSchemaForm<T extends string, TQueryKey extends QueryKey>({
  types,
  defaultType,
  active = true,
  schemaQuery,
  i18nPrefix = "tasks:submit",
  submitLabel,
  saving,
  submitDisabled = false,
  header,
  onSubmit,
}: DiscriminatedSchemaFormProps<T, TQueryKey>) {
  const { t } = useTranslation(["tasks", "common"]);
  const [type, setType] = useState<T>(defaultType);

  const {
    data: rawSchema,
    isLoading,
    error,
  } = useQuery({
    ...schemaQuery,
    enabled: active && (schemaQuery.enabled ?? true),
  });

  const rootSchema = useMemo((): JSONSchemaObject | null => {
    if (!rawSchema) return null;
    // OpenAPI / JSON Schema 运行时对象 → 表单内部结构化类型.
    return resolveSchema(rawSchema as JSONSchemaObject, rawSchema as JSONSchemaObject);
  }, [rawSchema]);

  const variantSchema = useMemo((): JSONSchemaObject | null => {
    if (!rootSchema) return null;
    const raw = resolveDiscriminator(type, rootSchema, rootSchema);
    if (!raw) return null;
    return stripDiscriminatorField(resolveSchema(raw, rootSchema), "type");
  }, [rootSchema, type]);

  const initialValues = useMemo(
    () => (variantSchema ? defaultsFromSchema(variantSchema) : {}),
    [variantSchema],
  );

  function handleSave(values: Record<string, unknown>) {
    if (!variantSchema) return;
    const cleaned = sanitizeValues(values, variantSchema);
    onSubmit({ type, ...cleaned });
  }

  return (
    <Stack gap="md">
      {header}

      <FieldChrome label={t("submit.typeLabel")}>
        <EnumToggle
          fullWidth
          options={types}
          value={type}
          onChange={setType}
          getLabel={(tt) =>
            // 动态表单: type 标签 key 随调用方传入的联合变化, 无法静态穷尽.
            t(`submit.types.${tt}` as never)
          }
        />
      </FieldChrome>

      {isLoading && (
        <Center py="md">
          <Loader size="sm" />
        </Center>
      )}

      {error && (
        <Alert icon={<IconAlertCircle size={18} />} color="red" variant="light">
          {extractErrorMessage(error, t("common:toast.operationFailed"))}
        </Alert>
      )}

      {!isLoading && !error && variantSchema && (
        <SchemaForm
          key={type}
          schema={variantSchema}
          prefix={type}
          i18nPrefix={i18nPrefix}
          values={initialValues}
          onSave={handleSave}
          saving={saving}
          mode="create"
          submitLabel={submitLabel ?? t("common:actions.submit")}
          submitDisabled={submitDisabled}
        />
      )}
    </Stack>
  );
}
