import type { JSONSchemaObject } from "./types";

/**
 * Resolve a $ref reference within the root schema.
 *
 * Handles internal references of the form "#/$defs/SomeName" by navigating
 * the root schema object along the slash-separated path.
 */
function resolveRef(ref: string, root: JSONSchemaObject): JSONSchemaObject | undefined {
  if (!ref.startsWith("#/")) {
    console.warn(`Unsupported $ref format: ${ref}`);
    return undefined;
  }

  const path = ref.slice(2).split("/");
  let current: unknown = root;

  for (const segment of path) {
    if (!current || typeof current !== "object") {
      console.warn(`Cannot resolve $ref: ${ref}, stopped at ${segment}`);
      return undefined;
    }
    current = (current as Record<string, unknown>)[segment];
  }

  return current as JSONSchemaObject;
}

/**
 * Normalize a schema node: collapse Pydantic Optional patterns.
 *
 * Pydantic Optional fields generate: anyOf/oneOf: [{type: T}, {type: "null"}]
 * This collapses them to a single type with nullable flag.
 */
function normalize(schema: JSONSchemaObject): JSONSchemaObject {
  // Handle anyOf: [T, null]
  if ("anyOf" in schema && Array.isArray(schema.anyOf) && schema.anyOf.length === 2) {
    const nonNull = schema.anyOf.find((s) => typeof s === "object" && s.type !== "null");
    const hasNull = schema.anyOf.some((s) => typeof s === "object" && s.type === "null");
    if (nonNull && hasNull && typeof nonNull === "object") {
      return { ...nonNull, ...schema, nullable: true, anyOf: undefined };
    }
  }

  // Handle oneOf: [T, null]
  if ("oneOf" in schema && Array.isArray(schema.oneOf) && schema.oneOf.length === 2) {
    const nonNull = schema.oneOf.find((s) => typeof s === "object" && s.type !== "null");
    const hasNull = schema.oneOf.some((s) => typeof s === "object" && s.type === "null");
    if (nonNull && hasNull && typeof nonNull === "object") {
      return { ...nonNull, ...schema, nullable: true, oneOf: undefined };
    }
  }

  return schema;
}

/**
 * Recursively resolve all $ref references and normalize composed schemas.
 *
 * Merges referenced definitions into the schema, preserving local overrides.
 * Tracks visited refs to detect circular references.
 * Normalizes Pydantic Optional patterns (anyOf/oneOf: [T, null]) at every level.
 */
export function resolveSchema(
  schema: JSONSchemaObject,
  root: JSONSchemaObject,
  visited: Set<string> = new Set(),
): JSONSchemaObject {
  // Resolve $ref
  if ("$ref" in schema && typeof schema.$ref === "string") {
    if (visited.has(schema.$ref)) {
      console.warn(`Circular $ref detected: ${schema.$ref}`);
      return schema;
    }

    const resolved = resolveRef(schema.$ref, root);
    if (!resolved) return schema;

    const newVisited = new Set(visited);
    newVisited.add(schema.$ref);

    const fullyResolved = resolveSchema(resolved, root, newVisited);

    // Merge outer schema properties (title, description, etc.) over the resolved definition
    // Preserve readonly and other metadata properties
    const { $ref: _, ...rest } = schema;
    if (typeof fullyResolved === "object" && fullyResolved !== null) {
      return normalize({ ...fullyResolved, ...rest });
    }
    return fullyResolved;
  }

  let result = { ...schema };

  // Resolve additionalProperties
  if ("additionalProperties" in result && typeof result.additionalProperties === "object") {
    result = {
      ...result,
      additionalProperties: resolveSchema(result.additionalProperties, root, new Set()),
    };
  }

  // Resolve propertyNames
  if ("propertyNames" in result && typeof result.propertyNames === "object") {
    const resolved = resolveSchema(result.propertyNames, root, new Set());
    if (typeof resolved !== "boolean") {
      result = { ...result, propertyNames: resolved };
    }
  }

  // Resolve items
  if ("items" in result && typeof result.items === "object") {
    const resolved = resolveSchema(result.items, root, new Set());
    if (typeof resolved !== "boolean") {
      result = { ...result, items: resolved };
    }
  }

  // Resolve properties
  if (
    "properties" in result &&
    typeof result.properties === "object" &&
    result.properties !== null
  ) {
    const properties: Record<string, JSONSchemaObject> = {};
    for (const [key, value] of Object.entries(result.properties)) {
      const resolved = resolveSchema(value, root, new Set());
      if (typeof resolved !== "boolean") {
        properties[key] = resolved;
      }
    }
    result = { ...result, properties };
  }

  // Resolve composed schemas
  for (const key of ["anyOf", "oneOf", "allOf"] as const) {
    if (key in result && Array.isArray(result[key])) {
      const arr = result[key];
      if (arr.length > 0) {
        result = {
          ...result,
          [key]: arr.map((s) => resolveSchema(s, root, new Set())),
        };
      }
    }
  }

  // Normalize after all children are resolved
  return normalize(result);
}

export function resolveDiscriminator(
  target: string,
  schema: JSONSchemaObject | undefined,
  root: JSONSchemaObject,
): JSONSchemaObject | undefined {
  if (!(schema && "discriminator" in schema && schema.discriminator)) return;
  if (!(target in schema.discriminator.mapping)) return;
  const ref = schema.discriminator.mapping[target];
  return resolveRef(ref, root);
}
