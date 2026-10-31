"""测试 NFO 附属文件生成"""

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

import pytest

from amane.db.models import Metadata
from amane.media import remote_avatar_url, write_nfo

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def metadata() -> Metadata:
    return Metadata(
        number="MIDV-123",
        title="Test Title",
        actors=["Actor A", "Actor B"],
        studio="Studio X",
        release="2026-01-15",
        runtime=120,
        tags=["Drama", "Romance"],
        series="Series Y",
        scores={"javdb": 85.0},
        directors=["Director Z"],
    )


@pytest.mark.asyncio(loop_scope="function")
async def test_write_nfo_has_required_fields(tmp_path: Path, metadata: Metadata):
    nfo_path = tmp_path / "MIDV-123.nfo"
    ok = await write_nfo(metadata, nfo_path)
    assert ok is True
    assert nfo_path.exists()
    content = nfo_path.read_text(encoding="utf-8")
    assert "<title>MIDV-123 Test Title</title>" in content
    assert "<num>MIDV-123</num>" in content
    assert "<actor>" in content
    assert "<name>Actor A</name>" in content
    assert "<studio>Studio X</studio>" in content
    assert "<genre>Drama</genre>" in content
    assert "<director>Director Z</director>" in content
    assert "<rating>85.0</rating>" in content
    # 系列使用规范嵌套: <set><name>…</name></set>
    assert "<series>Series Y</series>" in content
    assert "<set>" in content
    assert "<name>Series Y</name>" in content


@pytest.mark.asyncio(loop_scope="function")
async def test_write_nfo_plot_is_plain_text(tmp_path: Path):
    """长文本按纯文本写出: 无 CDATA, HTML 转义, 非法字符剥离, 换行原样保留."""
    plot = "结尾 ]]> 之后 & <标签>\n\n第二段\x0b"
    nfo_path = tmp_path / "PLOT-1.nfo"

    assert await write_nfo(Metadata(number="PLOT-1", title="T", plot=plot), nfo_path) is True

    content = nfo_path.read_text(encoding="utf-8")
    assert "<![CDATA[" not in content
    assert "]]>" not in content
    assert "\x0b" not in content

    root = ET.fromstring(content)
    assert root.findtext("plot") == "结尾 ]]> 之后 & <标签>\n\n第二段"
    assert root.findtext("outline") == root.findtext("plot")


@pytest.mark.parametrize(
    ("image_urls", "expected"),
    [
        (None, None),
        ([], None),
        (["/api/resources/abcd1234"], None),
        (["ftp://x/a.jpg", "not a url"], None),
        (["/api/resources/abcd1234", "https://img.example/a.jpg"], "https://img.example/a.jpg"),
        (["http://img.example/a.jpg", "https://img.example/b.jpg"], "http://img.example/a.jpg"),
    ],
)
def test_remote_avatar_url(image_urls: list[str] | None, expected: str | None):
    assert remote_avatar_url(image_urls) == expected


@pytest.mark.asyncio(loop_scope="function")
async def test_write_nfo_actor_thumb_only_for_known_avatars(tmp_path: Path, metadata: Metadata):
    nfo_path = tmp_path / "MIDV-123.nfo"
    assert await write_nfo(metadata, nfo_path, {"Actor A": "https://img.example/a.jpg?x=1&y=2"}) is True
    actors = {a.findtext("name"): a for a in ET.fromstring(nfo_path.read_text(encoding="utf-8")).findall("actor")}
    assert actors["Actor A"].findtext("thumb") == "https://img.example/a.jpg?x=1&y=2"
    assert actors["Actor B"].find("thumb") is None
