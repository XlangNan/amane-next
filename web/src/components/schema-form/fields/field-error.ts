import type { AnyFieldApi } from "@tanstack/react-form";

/**
 * 从 TanStack Form 字段的 meta 中取首条校验错误消息.
 *
 * 表单级校验器 (createSchemaValidator) 投影的是 string 消息; 这里只接受 string,
 * 其它形态 (对象等) 一律忽略, 避免把非人类可读内容塞进 UI.
 */
export function fieldError(field: AnyFieldApi): string | undefined {
  const errors: unknown[] = field.state.meta.errors;
  for (const e of errors) {
    if (typeof e === "string" && e.length > 0) return e;
  }
  return undefined;
}
