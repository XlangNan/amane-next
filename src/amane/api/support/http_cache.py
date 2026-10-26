"""资源图 HTTP 缓存头 - 就地超分后 URL 不变, 靠 content_hash ETag 协商失效.

``Cache-Control: public, no-cache``: 允许存本地, 但每次使用前必须带 ``If-None-Match`` 再验证;
未变 → 304, 超分更改字节 → 200 新体. 不用固定 max-age (新鲜期内会跳过协商).
"""

from fastapi import Request, Response

RESOURCE_CACHE_HEADERS = {"Cache-Control": "public, no-cache"}


def format_etag(content_hash: str) -> str:
    return f'"{content_hash}"'


def etag_matches(if_none_match: str | None, content_hash: str) -> bool:
    if not if_none_match or not content_hash:
        return False
    quoted = format_etag(content_hash)
    for part in if_none_match.split(","):
        candidate = part.strip()
        if candidate.startswith("W/"):
            candidate = candidate[2:].strip()
        if candidate == "*" or candidate == quoted:
            return True
    return False


def not_modified_response(content_hash: str) -> Response:
    return Response(status_code=304, headers={**RESOURCE_CACHE_HEADERS, "ETag": format_etag(content_hash)})


def maybe_not_modified(request: Request, content_hash: str | None) -> Response | None:
    if content_hash and etag_matches(request.headers.get("if-none-match"), content_hash):
        return not_modified_response(content_hash)
    return None
