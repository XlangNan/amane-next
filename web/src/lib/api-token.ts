/** API 会话管理 (信任模型见 docs/dev/config.md).

 * 鉴权经 HttpOnly `amane_token` cookie (SameSite=Lax, Path=/api): 登录门
 * 首次用输入框里的 token 以 Bearer 校验, 中间件在响应里下发 cookie, 之后
 * 所有请求 (hey-api / SSE / WS / `<img>` 子资源) 自动携带. token 不写入
 * localStorage, 不出现在任何 URL.
 */

/** 任何 API 请求 401 时触发; Root 监听后切换回登录门. */
export const AUTH_EXPIRED_EVENT = "amane:auth-expired";

/** API fetch 透传: 原样转发, 仅把 401 转成认证失效信号.
 *
 * 禁止在此包装里重建 headers (如 fetch(input, { headers })) — 传入单个
 * `Request` 时 init.headers 会整体替换请求头, 丢弃 Content-Type 等,
 * 后端 FastAPI strict_content_type 下 JSON body 解析会 422.
 */
export async function apiFetch(
  input: Parameters<typeof fetch>[0],
  init?: RequestInit,
): Promise<Response> {
  const resp = await fetch(input, init);
  if (resp.status === 401) {
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  }
  return resp;
}
