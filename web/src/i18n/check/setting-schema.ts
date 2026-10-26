/**
 * 编译时检查 settings.json i18n 翻译完整性.
 *
 * 遍历 HotSettings schema, 穷举所有 section 的字段路径与枚举条目,
 * 验证 en/zh-CN settings.json 的 `fields` 区域包含所有 label 和 options 翻译.
 */

import type * as schemas from "@/client/schemas.gen";
import en from "../locales/en/settings.json";
import zhCN from "../locales/zh-CN/settings.json";
import type { CollectEnumEntries, CollectFieldPaths, ExtractRefName, SchemaByName } from "./utils";
import { assertEnums, assertFields } from "./utils";

type HotSettings = typeof schemas.HotSettingsSchema;
type SectionName = keyof HotSettings["properties"] & string;

type SectionSchema<S extends SectionName> = HotSettings["properties"][S] extends {
  $ref: infer R extends string;
}
  ? SchemaByName<ExtractRefName<R>>
  : never;

type FieldPaths = {
  [S in SectionName]: SectionSchema<S> extends {
    properties: infer Props extends Record<string, unknown>;
  }
    ? { [K in keyof Props & string]: CollectFieldPaths<Props[K], `${S}.${K}`> }[keyof Props &
        string]
    : never;
}[SectionName];

type EnumEntries = {
  [S in SectionName]: SectionSchema<S> extends {
    properties: infer Props extends Record<string, unknown>;
  }
    ? { [K in keyof Props & string]: CollectEnumEntries<Props[K], `${S}.${K}`> }[keyof Props &
        string]
    : never;
}[SectionName];

assertFields<typeof en.fields, FieldPaths>(en.fields);
assertFields<typeof zhCN.fields, FieldPaths>(zhCN.fields);
assertEnums<typeof en.fields, EnumEntries>(en.fields);
assertEnums<typeof zhCN.fields, EnumEntries>(zhCN.fields);
