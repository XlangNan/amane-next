import { Ajv, type ErrorObject, type ValidateFunction } from "ajv";
import addFormats from "ajv-formats";
import type { JSONSchemaObject } from "./types";

/**
 * JSON Schema 校验 - 把后端 Pydantic 导出的标准约束 (minimum/maxLength/pattern/...)
 * 在前端表单层强制执行, 提交前给出即时反馈.
 *
 * 接入点是 TanStack Form 的表单级 `onChange` 校验器: 返回 `{ fields: {...} }`,
 * TanStack 自动把每条投影到对应 `<form.Field>` 的 `meta.errors`, 故无需逐个
 * leaf field 配置校验逻辑. 见 schema-form.tsx / task-submit-form.tsx 的接入.
 *
 * 关键: `resolver.ts` 把 Pydantic 的 `anyOf:[T,null]` 折叠为 `{...T, nullable:true}`
 * (OpenAPI 3.0 方言). ajv (draft 2020-12) 不识别 `nullable`, 因此校验前需经
 * `toAjvSchema` 转换为标准的 `type:[T,"null"]`, 并剥离 `x-*` / undefined 噪声.
 */

const ajv = new Ajv({
  allErrors: true,
  strict: false, // 容忍未知关键字 (x-*), 不抛错
  coerceTypes: false,
  validateFormats: true,
});
addFormats(ajv);

/** ajv keyword -> i18n message key (在 common.json 的 validation.* 下). */
const KEYWORD_I18N: Record<string, string> = {
  minimum: "validation.minimum",
  maximum: "validation.maximum",
  exclusiveMinimum: "validation.exclusiveMinimum",
  exclusiveMaximum: "validation.exclusiveMaximum",
  multipleOf: "validation.multipleOf",
  minLength: "validation.minLength",
  maxLength: "validation.maxLength",
  pattern: "validation.pattern",
  minItems: "validation.minItems",
  maxItems: "validation.maxItems",
  uniqueItems: "validation.uniqueItems",
  type: "validation.type",
  enum: "validation.enum",
  format: "validation.format",
};

type Translate = (key: string, opts?: Record<string, unknown>) => string;

/**
 * 把表单方言的字段 schema 转为 ajv 可校验的标准 JSON Schema.
 * 处理 `nullable` 折叠并剥离表单专用 / undefined 关键字.
 */
function toAjvSchema(schema: JSONSchemaObject): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(schema)) {
    if (value === undefined) continue;
    if (key === "nullable") continue;
    if (key.startsWith("x-")) continue;
    if (key === "discriminator" || key === "default") continue;
    out[key] = value;
  }

  // nullable: 把 type 扩展为允许 null
  if (schema.nullable === true && typeof out.type === "string") {
    out.type = [out.type, "null"];
    if (Array.isArray(out.enum) && !out.enum.includes(null)) {
      out.enum = [...out.enum, null];
    }
  }
  return out;
}

/** 该 schema 是否带有可校验的标准约束 (无约束则跳过编译, 省开销). */
function hasConstraints(schema: JSONSchemaObject): boolean {
  // 在联合类型上按动态 key 探测约束存在性; 用 Record 视图读取, 不改动 schema.
  const s = schema as Record<string, unknown>;
  const keys = [
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "pattern",
    "minItems",
    "maxItems",
    "uniqueItems",
    "format",
    "enum",
  ] as const;
  return keys.some((k) => s[k] !== undefined);
}

function formatError(error: ErrorObject, t: Translate): string {
  const i18nKey = KEYWORD_I18N[error.keyword];
  if (i18nKey) {
    // params 里含 limit / pattern 等, 直接透传给 i18n 插值.
    return t(`common:${i18nKey}`, { ...error.params, defaultValue: error.message ?? "" });
  }
  return error.message ?? t("common:validation.invalid", { defaultValue: "Invalid value" });
}

/**
 * 表单级 onChange 校验器. 对每个字段独立编译并校验 (避免 nullable 折叠后整对象
 * 校验的复杂度, 同时天然对齐逐字段错误展示).
 *
 * @param prefix    表单 state 命名空间 (字段路径为 `${prefix}.${key}`)
 * @param properties 已解析的字段 schema 映射
 * @param t          i18n 翻译函数
 * @returns TanStack Form `validators.onChange` 兼容的函数; 无错误返回 undefined
 */
export function createSchemaValidator(
  prefix: string,
  properties: Record<string, JSONSchemaObject>,
  t: Translate,
): (args: { value: Record<string, unknown> }) => { fields: Record<string, string> } | undefined {
  const validators = new Map<string, ValidateFunction>();
  for (const [key, schema] of Object.entries(properties)) {
    if (typeof schema === "boolean" || !hasConstraints(schema)) continue;
    try {
      validators.set(key, ajv.compile(toAjvSchema(schema)));
    } catch {
      // schema 不被 ajv 接受 (罕见, 如复合类型) - 跳过该字段校验, 不阻塞表单.
    }
  }

  return ({ value }) => {
    const section = (value[prefix] ?? {}) as Record<string, unknown>;
    const fields: Record<string, string> = {};
    for (const [key, validate] of validators) {
      const v = section[key];
      // null/undefined 视为未设置; 是否必填由 schema 自身的 type:[..,null] 决定.
      if (v === undefined) continue;
      if (!validate(v) && validate.errors && validate.errors.length > 0) {
        fields[`${prefix}.${key}`] = formatError(validate.errors[0], t);
      }
    }
    return Object.keys(fields).length > 0 ? { fields } : undefined;
  };
}
