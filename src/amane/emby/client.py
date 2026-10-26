"""Emby / Jellyfin 的最小接口: 列出人物, 给人物上传主图. 出站 HTTP 一律经 ``WebClient``."""

import base64
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, TypeAdapter

if TYPE_CHECKING:
    from ..config import EmbyConfig
    from ..net.http import WebClient

PAGE_SIZE = 500

_MIME_BY_SUFFIX: dict[str, str] = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}


class EmbyPerson(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(alias="Name")
    id: str = Field(alias="Id")
    image_tags: dict[str, str] = Field(default_factory=dict, alias="ImageTags")

    @property
    def has_primary_image(self) -> bool:
        return "Primary" in self.image_tags


class EmbyLibrary(BaseModel):
    """Emby 的媒体库 (VirtualFolder)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(alias="Name")
    id: str = Field(default="", alias="ItemId")


class _PersonRef(BaseModel):
    """影片条目 ``People`` 里的一项; 有主图时带 ``PrimaryImageTag``."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(alias="Name")
    id: Annotated[str, BeforeValidator(str)] = Field(alias="Id")
    type: str | None = Field(default=None, alias="Type")
    primary_image_tag: str | None = Field(default=None, alias="PrimaryImageTag")


class _Item(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    people: list[_PersonRef] = Field(default_factory=list, alias="People")


class _ItemPage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[_Item] = Field(default_factory=list, alias="Items")
    total: int = Field(default=0, alias="TotalRecordCount")


_LIBRARIES = TypeAdapter(list[EmbyLibrary])
#: 按库取人物时翻的影片条目数; 每条都带完整演员表, 页不宜大.
ITEM_PAGE_SIZE = 100


class _PersonPage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[EmbyPerson] = Field(default_factory=list, alias="Items")
    total: int = Field(default=0, alias="TotalRecordCount")


def base_url(url: str) -> str:
    """去掉末尾的 ``/`` 与 ``/emby``: 路径前缀由本模块统一补."""
    out = url.strip().rstrip("/")
    if out.lower().endswith("/emby"):
        out = out[: -len("/emby")]
    return out


def image_mime(path: Path) -> str:
    return _MIME_BY_SUFFIX.get(path.suffix.lower(), "image/jpeg")


class EmbyClient:
    def __init__(self, client: WebClient, cfg: EmbyConfig) -> None:
        self._client = client
        self._base = f"{base_url(cfg.url)}/emby"
        self._headers = {"X-Emby-Token": cfg.api_key}
        self._use_proxy = cfg.use_proxy

    async def list_persons(self) -> list[EmbyPerson]:
        """分页取全部人物. 密钥放请求头, 不进 URL 与日志."""
        out: list[EmbyPerson] = []
        start = 0
        while True:
            raw = await self._client.get_json(
                f"{self._base}/Persons?StartIndex={start}&Limit={PAGE_SIZE}",
                headers=self._headers,
                use_proxy=self._use_proxy,
            )
            page = _PersonPage.model_validate(raw)
            out.extend(page.items)
            start += len(page.items)
            if not page.items or start >= page.total:
                return out

    async def list_libraries(self) -> list[EmbyLibrary]:
        raw = await self._client.get_json(
            f"{self._base}/Library/VirtualFolders", headers=self._headers, use_proxy=self._use_proxy
        )
        return [lib for lib in _LIBRARIES.validate_python(raw) if lib.id]

    async def list_library_persons(self, library_id: str) -> list[EmbyPerson]:
        """一个媒体库里出现过的演员, 取自该库影片的演员表 (按人物 ID 去重)."""
        found: dict[str, EmbyPerson] = {}
        start = 0
        while True:
            raw = await self._client.get_json(
                f"{self._base}/Items?ParentId={library_id}&Recursive=true&IncludeItemTypes=Movie,Series,Video"
                f"&Fields=People&StartIndex={start}&Limit={ITEM_PAGE_SIZE}",
                headers=self._headers,
                use_proxy=self._use_proxy,
            )
            page = _ItemPage.model_validate(raw)
            for item in page.items:
                for ref in item.people:
                    if ref.type not in (None, "Actor", "GuestStar") or ref.id in found:
                        continue
                    tags = {"Primary": ref.primary_image_tag} if ref.primary_image_tag else {}
                    found[ref.id] = EmbyPerson(name=ref.name, id=ref.id, image_tags=tags)
            start += len(page.items)
            if not page.items or start >= page.total:
                return list(found.values())

    async def refresh_library(self) -> None:
        """让 Emby 扫描全部媒体库 (``POST /Library/Refresh``, 成功返回 204)."""
        await self._client.request(
            "POST", f"{self._base}/Library/Refresh", headers=self._headers, use_proxy=self._use_proxy
        )

    async def upload_primary_image(self, person_id: str, image: bytes, mime: str) -> None:
        """Emby 要求请求体是 Base64 文本, ``Content-Type`` 是图片的 MIME. 成功返回 204, 失败抛 ``RequestError``."""
        await self._client.request(
            "POST",
            f"{self._base}/Items/{person_id}/Images/Primary",
            headers={**self._headers, "Content-Type": mime},
            data=base64.b64encode(image).decode("ascii"),
            use_proxy=self._use_proxy,
        )
