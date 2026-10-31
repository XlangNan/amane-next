"""设置页「测试翻译」: 用当前网络配置对每个翻译源各真实请求一次, 把各自的结果和失败原因直接给用户看."""

from fastapi import APIRouter
from pydantic import BaseModel

from ...enums import Language
from ...translate import Translator
from ..deps import RuntimeDep

router = APIRouter(prefix="/translate", tags=["translate"])

_SAMPLE = "こんにちは世界"


class TranslateProviderResult(BaseModel):
    provider: str
    ok: bool
    text: str | None = None
    error: str | None = None


class TranslateTestResponse(BaseModel):
    source: str
    results: list[TranslateProviderResult]


@router.post("/test")
async def test_translate(runtime: RuntimeDep) -> TranslateTestResponse:
    probes = await Translator(runtime.web_client).probe_all(_SAMPLE, Language.ZH_CN)
    return TranslateTestResponse(
        source=_SAMPLE,
        results=[TranslateProviderResult(provider=p.provider, ok=p.ok, text=p.text, error=p.error) for p in probes],
    )
