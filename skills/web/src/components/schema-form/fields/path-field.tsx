import type { AnyFieldApi } from "@tanstack/react-form";
import { PathPicker } from "@/components/path-picker";
import type { FieldProps, PathJSONSchema } from "../schema";
import { FieldChrome } from "./field-chrome";
import { fieldError } from "./field-error";

export function PathField({
  name,
  label,
  description,
  schema,
  form,
  variant,
}: FieldProps<PathJSONSchema>) {
  const pathType = schema["x-path-type"] ?? "directory";

  return (
    <form.Field name={name}>
      {(field: AnyFieldApi) => (
        <FieldChrome
          variant={variant}
          label={label}
          description={description}
          error={fieldError(field)}
        >
          <PathPicker
            value={(field.state.value as string) ?? ""}
            onChange={(v) => field.handleChange(v)}
            pathType={pathType}
            placeholder="/path/to/directory"
          />
        </FieldChrome>
      )}
    </form.Field>
  );
}
