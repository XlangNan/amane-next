/**
 * 用于检查数组 / Record / switch 与常量联合一一对应的工具.
 */

/** A 的所有成员都属于 B (非分布式). */
type Covers<A, B> = [A] extends [B] ? true : false;

/** A 与 B 互相包含 (非分布式). */
type SetEqual<A, B> =
  Covers<A, B> extends true ? (Covers<B, A> extends true ? true : false) : false;

/**
 * 元组中重复出现 (≥ 2 次) 的元素 union; 无重复时为 `never`.
 * 必须在元组层面递归: `T[number]` 会去重, 丢失多重性.
 */
type FindDuplicates<T extends readonly unknown[], Seen = never> = T extends readonly [
  infer Head,
  ...infer Tail,
]
  ? [Head] extends [Seen]
    ? Head | FindDuplicates<Tail, Seen>
    : FindDuplicates<Tail, Seen | Head>
  : never;

/**
 * 一一对应判定的人类可读形态, 用作返回类型:
 * 通过 → T 自身; 出错 → `["__exhaustive_error__", { ... }]`.
 */
export type Exhaustive<T extends readonly unknown[], U> =
  SetEqual<T[number], U> extends true
    ? FindDuplicates<T> extends never
      ? T
      : ["__exhaustive_error__", { duplicates: FindDuplicates<T> }]
    : ["__exhaustive_error__", { missing: Exclude<U, T[number]>; extra: Exclude<T[number], U> }];

/** Call-site 错误标签. 在编译错误中直接打印 Reason 与 Detail. */
export type Mismatch<Reason extends string, Detail> = {
  readonly __exhaustive_error__: Reason;
  readonly detail: Detail;
};

/** 元组每个位置 mapped 替换为 V, 长度不变 (避免 "Expected N args" 误导). */
type ReplaceElements<T extends readonly unknown[], V> = { [K in keyof T]: V };

/**
 * 调用参数的形状校验. 合规返回 T; 不合规按"missing > extra > duplicates"
 * 优先级把每个位置替换为带说明的 `Mismatch`, 让 TS 错误把根因带到 call site.
 *
 * 注: rest 参数下 TS 对 `T` 的字面量精度会退化, `duplicates` 可能显示为整个 U
 * 而非具体重复元素. 元组参数版 (`assertExhaustive`) 不受此限.
 */
type GuardArgs<T extends readonly unknown[], U> = [Exclude<U, T[number]>] extends [never]
  ? [Exclude<T[number], U>] extends [never]
    ? [FindDuplicates<T>] extends [never]
      ? T
      : ReplaceElements<
          T,
          Mismatch<"Tuple has duplicate elements", { duplicates: FindDuplicates<T> }>
        >
    : ReplaceElements<
        T,
        Mismatch<"Tuple has extra elements not in union", { extra: Exclude<T[number], U> }>
      >
  : ReplaceElements<
      T,
      Mismatch<"Tuple is missing union members", { missing: Exclude<U, T[number]> }>
    >;

// ============================================================================
// 运行时工具
// ============================================================================

/**
 * 构造与 U 一一对应的只读元组.
 *
 * @example
 *   type Status = "queued" | "running" | "done" | "failed";
 *   const ALL = exhaustiveTuple<Status>()("queued", "running", "done", "failed");
 *   //  ^? readonly ["queued", "running", "done", "failed"]
 */
export function exhaustiveTuple<U>() {
  // `as never` 把 GuardArgs 桥接回字面量元组, 避免给每种 arity 写重载.
  return <const T extends readonly U[]>(...values: GuardArgs<T, U>): Exhaustive<T, U> =>
    values as never;
}

/**
 * 校验已存在的元组是否与 U 一一对应. 元组在别处构造 (如来自 `Object.keys`) 时使用.
 *
 * @example
 *   const RAW = ["queued", "running", "done", "failed"] as const;
 *   const CHECKED = assertExhaustive<Status>()(RAW);
 */
export function assertExhaustive<U>() {
  return <const T extends readonly U[]>(tuple: GuardArgs<T, U>): Exhaustive<T, U> => tuple as never;
}

/**
 * 构造 key 集合恰好等于 K 的只读对象, 保留 value 字面量类型.
 * 与 `satisfies Record<K, V>` 等价, 但可在调用点显式指定 K.
 *
 * @example
 *   const SCHEMAS = exhaustiveRecord<SubmittableTaskType>()({
 *     scrape: ScrapeSubmissionSchema,
 *     scan: ScanSubmissionSchema,
 *     organize: OrganizeSubmissionSchema,
 *   });
 */
export function exhaustiveRecord<K extends PropertyKey>() {
  return <T extends Record<K, unknown>>(record: T & Record<Exclude<keyof T, K>, never>): T =>
    record;
}

/**
 * Switch / if-else 默认分支的穷尽断言: 若有未覆盖分支, `value` 不为 `never`, 编译报错.
 *
 * @example
 *   switch (kind) {
 *     case "a": ...; return;
 *     case "b": ...; return;
 *     default: assertNever(kind, "kind");
 *   }
 */
export function assertNever(value: never, label = "value"): never {
  throw new Error(`Unhandled exhaustive ${label}: ${JSON.stringify(value)}`);
}

/**
 * 类型守卫: `value` 命中 `tuple` 时窄化为 `T[number]`.
 *
 * @example
 *   const TYPES = exhaustiveTuple<TaskType>()("scrape", "organize", "scan", "cleanup");
 *   if (isOneOf(TYPES, raw)) { /* raw: TaskType *\/ }
 */
export function isOneOf<const T extends readonly unknown[]>(
  tuple: T,
  value: unknown,
): value is T[number] {
  for (const candidate of tuple) {
    if (Object.is(candidate, value)) return true;
  }
  return false;
}
