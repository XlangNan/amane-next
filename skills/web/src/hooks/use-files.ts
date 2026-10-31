import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { listFilesOptions } from "@/client/@tanstack/react-query.gen";

interface UseFileListParams {
  path: string;
  /** 相对 path 的基准目录 (当前浏览位置); 缺省由服务端取首个安全目录. */
  base?: string;
  show_hidden?: boolean;
}

/** List directory contents at `path` via the `/api/files` endpoint. */
export function useFileList({ path, base, show_hidden }: UseFileListParams) {
  return useQuery({
    ...listFilesOptions({ query: { path, base, show_hidden } }),
    // 导航期间保留上一次响应, 面包屑/列表不闪烁
    placeholderData: keepPreviousData,
  });
}
