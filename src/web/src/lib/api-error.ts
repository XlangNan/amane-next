import { isRecord } from "@/lib/utils";

/**
 * Pydantic 校验错误信息
 */
interface ValidationError {
  loc: Array<string | number>;
  msg: string;
  type: string;
}

function isValidationArray(v: unknown): v is ValidationError[] {
  return (
    Array.isArray(v) &&
    v.every((item) => isRecord(item) && typeof item.msg === "string" && Array.isArray(item.loc))
  );
}

/**
 * 从抛出的错误提取人类可读消息.
 * @param fallback 无法解析时的默认文案.
 */
export function extractErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === "string" && error.trim()) return error;

  if (isRecord(error)) {
    const detail = error.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (isValidationArray(detail)) {
      return detail
        .map((item) => {
          const field = item.loc.filter((p) => p !== "body").join(".");
          return field ? `${field}: ${item.msg}` : item.msg;
        })
        .join("; ");
    }
    if (typeof error.message === "string" && error.message.trim()) return error.message;
  }

  return fallback;
}
