/**
 * Development-only logger. All methods are no-ops in production builds,
 * allowing tree-shaking to eliminate the logging code entirely.
 *
 * Usage:
 *   import { devLog } from "@/lib/dev-logger";
 *   devLog.info("FieldRouter", "Rendering TextField", { name, schema });
 */

type LogLevel = "debug" | "info" | "warn" | "error";

const LEVEL_STYLES: Record<LogLevel, string> = {
  debug: "color: #8b8b8b",
  info: "color: #2563eb",
  warn: "color: #d97706",
  error: "color: #dc2626; font-weight: bold",
};

function noop() {}

function createLogger(level: LogLevel) {
  if (!import.meta.env.DEV) return noop;

  const style = LEVEL_STYLES[level];
  const consoleFn =
    level === "debug" ? console.debug : level === "info" ? console.info : console[level];

  return (tag: string, message: string, ...data: unknown[]) => {
    consoleFn(`%c[${tag}]`, style, message, ...data);
  };
}

export const devLog = {
  debug: createLogger("debug"),
  info: createLogger("info"),
  warn: createLogger("warn"),
  error: createLogger("error"),
};
