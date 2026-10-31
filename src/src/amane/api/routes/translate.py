"""设置页「测试翻译」: 用当前网络配置真实请求一次谷歌翻译, 把失败原因直接给用户看."""

from fastapi import APIRouter
from pydantic import BaseModel

from ...enums import Language
from ...translate import TranslateError, Translator
from ..deps import RuntimeDep

router = APIRouter(prefix="/translate", tags=["translate"])

_SAMPLE = "こんにちは世界"


class TranslateTestResponse(BaseModel):
    ok: bool
    source: str
    text: str | None = None
    provider: str | None = None
    error: str | None = None


@router.post("/test")
async def test_translate(runtime: RuntimeDep) -> TranslateTestResponse:
    try:
        text, provider = await Translator(runtime.web_client).probe(_SAMPLE, Language.ZH_CN)
    except TranslateError as e:
        return TranslateTestResponse(ok=False, source=_SAMPLE, error=str(e))
    return TranslateTestResponse(ok=True, source=_SAMPLE, text=text, provider=provider)
