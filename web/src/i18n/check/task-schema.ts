/**
 * 编译时检查 tasks.json i18n 翻译完整性.
 *
 * 遍历所有 Submission schema, 穷举字段路径与枚举条目,
 * 验证 en/zh-CN tasks.json 的 `submit` 区域包含所有 label 和 options 翻译.
 * const 字段 (type discriminator) 跳过检查.
 */

import type * as schemas from "@/client/schemas.gen";
import en from "../locales/en/tasks.json";
import zhCN from "../locales/zh-CN/tasks.json";
import type { CollectEnumEntries, CollectFieldPaths } from "./utils";
import { assertEnums, assertFields } from "./utils";

type SubmissionSchemaName = {
  [K in keyof typeof schemas]: K extends `${string}SubmissionSchema` ? K : never;
}[keyof typeof schemas];

type SubmissionRoot<S extends SubmissionSchemaName> = (typeof schemas)[S] extends {
  properties: { type: { const: infer V extends string } };
}
  ? V
  : never;

type SubmissionFieldProps<S extends SubmissionSchemaName> = (typeof schemas)[S] extends {
  properties: infer Props extends Record<string, unknown>;
}
  ? { [K in keyof Props & string as K extends "type" ? never : K]: Props[K] }
  : never;

type FieldPathsForSchema<S extends SubmissionSchemaName> =
  SubmissionFieldProps<S> extends infer Props extends Record<string, unknown>
    ? {
        [K in keyof Props & string]: CollectFieldPaths<
          Props[K],
          `${SubmissionRoot<S>}.${K}`,
          false,
          true
        >;
      }[keyof Props & string]
    : never;

/**
 * 所有 Submission 的字段路径联合.
 * 使用 mapped type + index 避免联合分发深度溢出.
 */
type FieldPaths = {
  [S in SubmissionSchemaName]: FieldPathsForSchema<S>;
}[SubmissionSchemaName];

type EnumEntriesForSchema<S extends SubmissionSchemaName> =
  SubmissionFieldProps<S> extends infer Props extends Record<string, unknown>
    ? {
        [K in keyof Props & string]: CollectEnumEntries<
          Props[K],
          `${SubmissionRoot<S>}.${K}`,
          true
        >;
      }[keyof Props & string]
    : never;

type EnumEntries = {
  [S in SubmissionSchemaName]: EnumEntriesForSchema<S>;
}[SubmissionSchemaName];

assertFields<typeof en.submit, FieldPaths>(en.submit);
assertFields<typeof zhCN.submit, FieldPaths>(zhCN.submit);
assertEnums<typeof en.submit, EnumEntries>(en.submit);
assertEnums<typeof zhCN.submit, EnumEntries>(zhCN.submit);
