import type * as schemas from "@/client/schemas.gen";

/** "#/components/schemas/Name" → "Name" */
type ExtractRefName<R extends string> = R extends `#/components/schemas/${infer Name}`
  ? Name
  : never;

/** "Name" → typeof schemas.NameSchema */
type SchemaByName<N extends string> = `${N}Schema` extends keyof typeof schemas
  ? (typeof schemas)[`${N}Schema`]
  : never;

type Deref<T> = T extends { $ref: infer R extends string } ? SchemaByName<ExtractRefName<R>> : T;

type NonNull<T> = T extends { anyOf: infer Items extends readonly unknown[] }
  ? Exclude<Items[number], { type: "null" }>
  : T;

type Concrete<T> = Deref<NonNull<T>>;

/**
 * 递归收集需要 label 翻译的字段路径.
 * IsWildcard: 路径以 `$` 结尾时不产出 leaf (仅子属性产出).
 * SkipConst: 跳过 const 字段.
 */
type CollectFieldPaths<
  T,
  P extends string,
  IsWildcard extends boolean = false,
  SkipConst extends boolean = false,
> =
  Concrete<T> extends infer C extends Record<string, unknown>
    ? (SkipConst extends true ? (C extends { const: unknown } ? never : 0) : 0) extends 0
      ? // 非通配路径 → label 字段
        | (IsWildcard extends true ? never : P)
        // properties 递归
        | (C extends { properties: infer Props extends Record<string, unknown> }
            ? {
                [K in keyof Props & string]: CollectFieldPaths<
                  Props[K],
                  `${P}.${K}`,
                  false,
                  SkipConst
                >;
              }[keyof Props & string]
            : never)
        // additionalProperties 递归 (dict 值类型)
        | (C extends { additionalProperties: infer AP }
            ? CollectFieldPaths<AP, `${P}.$`, true, SkipConst>
            : never)
        // items 递归 (array 元素)
        | (C extends { type: "array"; items: infer I }
            ? CollectFieldPaths<I, `${P}.$`, true, SkipConst>
            : never)
      : never
    : never;

/**
 * 递归收集 `路径:枚举值` 条目.
 * 覆盖: 直接 enum, propertyNames.enum, x-show-names.
 * array items / dict additionalProperties 的路径加 `.$`, 与 FieldRouter / DictField 的 i18nPath 对齐.
 * SkipConst: 跳过 const 字段.
 */
type CollectEnumEntries<T, P extends string, SkipConst extends boolean = false> =
  Concrete<T> extends infer C extends Record<string, unknown>
    ? (SkipConst extends true ? (C extends { const: unknown } ? never : 0) : 0) extends 0
      ? // 直接 enum
        | (C extends { enum: readonly (infer V)[] } ? `${P}:${V & string}` : never)
        // propertyNames.enum (dict key)
        | (C extends { propertyNames: { enum: readonly (infer V)[] } }
            ? `${P}:${V & string}`
            : never)
        // x-show-names (无 enum 时)
        | (C extends { "x-show-names": readonly (infer V)[] }
            ? C extends { enum: readonly unknown[] }
              ? never
              : `${P}:${V & string}`
            : never)
        // properties 递归
        | (C extends { properties: infer Props extends Record<string, unknown> }
            ? {
                [K in keyof Props & string]: CollectEnumEntries<Props[K], `${P}.${K}`, SkipConst>;
              }[keyof Props & string]
            : never)
        // additionalProperties 递归
        | (C extends { additionalProperties: infer AP }
            ? CollectEnumEntries<AP, `${P}.$`, SkipConst>
            : never)
        // items 递归
        | (C extends { type: "array"; items: infer I }
            ? CollectEnumEntries<I, `${P}.$`, SkipConst>
            : never)
      : never
    : never;

/** 点分隔路径在嵌套对象中取值 (`$` 为字面量 key) */
type DeepGet<T, Path extends string> = Path extends `${infer Head}.${infer Tail}`
  ? Head extends keyof T
    ? DeepGet<T[Head], Tail>
    : never
  : Path extends keyof T
    ? T[Path]
    : never;

/** 缺失 label 的字段路径 (never = 全部通过) */
type MissingFields<T, FP extends string> = {
  [P in FP]: [DeepGet<T, P>] extends [never]
    ? `MISSING_PATH:${P}`
    : DeepGet<T, P> extends { label: string }
      ? never
      : `MISSING_LABEL:${P}`;
}[FP];

/** 缺失 options 的枚举条目 (never = 全部通过) */
type MissingEnumOptions<T, EE extends string> = {
  [E in EE]: E extends `${infer Path}:${infer Value}`
    ? [DeepGet<T, Path>] extends [never]
      ? `MISSING_PATH:${Path}`
      : DeepGet<T, Path> extends { options: infer O }
        ? Value extends keyof O
          ? never
          : E
        : `NO_OPTIONS:${Path}`
    : never;
}[EE];

/** 断言所有字段路径有 label */
function assertFields<T, FP extends string>(
  _f: [MissingFields<T, FP>] extends [never]
    ? T
    : `ERROR: missing translations: ${MissingFields<T, FP> & string}`,
) {}

/** 断言所有枚举值有 options */
function assertEnums<T, EE extends string>(
  _f: [MissingEnumOptions<T, EE>] extends [never]
    ? T
    : `ERROR: missing enum options: ${MissingEnumOptions<T, EE> & string}`,
) {}

export type {
  CollectEnumEntries,
  CollectFieldPaths,
  Concrete,
  DeepGet,
  Deref,
  ExtractRefName,
  MissingEnumOptions,
  MissingFields,
  NonNull,
  SchemaByName,
};
export { assertEnums, assertFields };
