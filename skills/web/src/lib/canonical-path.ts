/**
 * 规范路径解析: 服务器回传的 `path` (恒绝对、as_posix、无 `\\?\` 前缀) 拆为 根 + 段.
 *
 * 三种前缀形态互斥, 由规范串本身判定, 与服务器平台无关:
 * - `//server/share/...` → UNC, 根 = 前两段 (server 无 share 不可寻址)
 * - `/data/...`          → POSIX 根 = `/`
 * - `S:/movies`          → Windows 盘符根 = `S:/`
 * 其余输入 (相对路径等) 防御性视为无根, 仅段序列.
 */

export interface CanonicalPathParts {
  root: string;
  segments: string[];
}

export function splitCanonicalPath(path: string): CanonicalPathParts {
  const parts = path.split("/").filter(Boolean);

  if (path.startsWith("//")) {
    const [server, share, ...tail] = parts;
    if (server && share) {
      return { root: `//${server}/${share}`, segments: tail };
    }
    return { root: "", segments: parts };
  }

  const drive = path.match(/^([A-Za-z]):\//);
  if (drive) {
    return { root: `${drive[1]}:/`, segments: parts.slice(1) };
  }

  if (path.startsWith("/")) {
    return { root: "/", segments: parts };
  }

  return { root: "", segments: parts };
}

/** 第 index 级 (0 = 根) 的完整路径. */
export function canonicalAncestor(parts: CanonicalPathParts, index: number): string {
  if (index <= 0) return parts.root;
  return parts.root + parts.segments.slice(0, index).join("/");
}
