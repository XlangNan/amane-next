import type { AnyFieldApi } from "@tanstack/react-form";
import { EnumToggle } from "@/components/common/enum-toggle";
import { useEnumI18n } from "../hooks";
import type { FieldProps, NumericEnumJSONSchema, TextEnumJSONSchema } from "../schema";
import { FieldChrome } from "./field-chrome";

type EnumSchema = TextEnumJSONSchema | NumericEnumJSONSchema;

interface EnumToggleFieldProps extends FieldProps<EnumSchema> {
  multiple?: boolean;
}

export { EnumToggle } from "@/components/common/enum-toggle";

/**
 * Toggle-button group for small enum selections (≤5 options).
 * Supports both single-select (default) and multi-select (multiple=true).
 */
export function EnumToggleField({
  name,
  label,
  description,
  schema,
  form,
  i18nPath,
  i18nPrefix,
  multiple,
  variant,
}: EnumToggleFieldProps) {
  const enumValues = schema.enum;
  const getOptionLabel = useEnumI18n(i18nPath, i18nPrefix);

  return (
    <form.Field name={name}>
      {(field: AnyFieldApi) => {
        const raw = field.state.value;
        return (
          <FieldChrome variant={variant} label={label} description={description}>
            {multiple ? (
              <EnumToggle
                multiple
                options={enumValues}
                value={enumValues.filter(
                  (opt) => Array.isArray(raw) && raw.some((item) => item === opt),
                )}
                onChange={(next) => field.handleChange(next)}
                getLabel={(opt, i) => getOptionLabel(opt, i, schema)}
              />
            ) : (
              <EnumToggle
                options={enumValues}
                value={enumValues.find((opt) => opt === raw)}
                onChange={(next) => field.handleChange(next)}
                getLabel={(opt, i) => getOptionLabel(opt, i, schema)}
              />
            )}
          </FieldChrome>
        );
      }}
    </form.Field>
  );
}
