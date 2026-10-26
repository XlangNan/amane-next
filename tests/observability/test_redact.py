"""redact_hot 表测试."""

import pytest

from amane.observability.models import REDACTION_PLACEHOLDER
from amane.observability.redact import hot_slice_for_task, needs_secrets_file, redact_dsn, redact_hot, redact_proxy


def test_hot_slice_scrape_drops_noise():
    full = {
        "scraping": {"a": 1},
        "network": {"b": 2},
        "r18": {},
        "plugins": {},
        "watcher": {"x": 1},
        "worker": {"y": 1},
        "logging": {"level": "INFO"},
        "notify": {"dingtalk_webhook": "https://oapi.dingtalk.com/robot/send?access_token=t"},
        "emby": {"api_key": "k"},
        "sr": {},
    }
    assert set(hot_slice_for_task(full, "scrape").keys()) == {"scraping", "network", "r18", "plugins"}
    assert {"notify", "emby", "watcher", "worker", "logging"}.isdisjoint(hot_slice_for_task(full, "organize"))


@pytest.mark.parametrize(
    ("dump", "expected"),
    [
        ({"scraping": {"site_config": {"javdb": {"cookie": {}}}}, "network": {}, "r18": {}}, False),
        ({"scraping": {"site_config": {"javdb": {"cookie": {"a": "b"}}}}, "network": {}, "r18": {}}, True),
        ({"scraping": {"site_config": {}}, "emby": {"api_key": "k"}, "network": {}, "r18": {}}, True),
        ({"emby": {"api_key": ""}, "notify": {"dingtalk_webhook": "", "dingtalk_secret": ""}}, False),
        ({"notify": {"dingtalk_webhook": "https://oapi.dingtalk.com/robot/send?access_token=t"}}, True),
        ({"notify": {"dingtalk_secret": "SECabc"}}, True),
        ({"scraping": {"site_config": {}}, "network": {}, "r18": {"dsn": "postgresql://u:p@h/db"}}, True),
        ({"scraping": {"site_config": {}}, "network": {}, "r18": {"read_password": "default"}}, False),
        ({"plugins": {"acme.fake": {"config": {"api_token": "secret"}}}}, True),
    ],
)
def test_needs_secrets_file(dump: dict, expected: bool):
    assert needs_secrets_file(dump) is expected


@pytest.mark.parametrize(
    ("input_hot", "assertions"),
    [
        pytest.param(
            {
                "scraping": {
                    "site_config": {
                        "javdb": {"cookie": {"session": "secret", "dv": "1"}, "api_token": None},
                    }
                }
            },
            lambda out: (
                out["scraping"]["site_config"]["javdb"]["cookie"] == {"session": "***", "dv": "***"}
                and out["scraping"]["site_config"]["javdb"]["api_token"] is None
            ),
            id="cookie-values-redacted-keys-kept",
        ),
        pytest.param(
            {"scraping": {"site_config": {"theporndb": {"cookie": {}, "api_token": "tok_abc"}}}},
            lambda out: out["scraping"]["site_config"]["theporndb"]["api_token"] == REDACTION_PLACEHOLDER,
            id="api-token-redacted",
        ),
        pytest.param(
            {"scraping": {"site_config": {"javdb": {"cookie": {}}}}},
            lambda out: out["scraping"]["site_config"]["javdb"]["cookie"] == {},
            id="empty-cookie-unchanged",
        ),
        pytest.param(
            {"emby": {"api_key": "sk-live", "enabled": True}},
            lambda out: out["emby"]["api_key"] == REDACTION_PLACEHOLDER and out["emby"]["enabled"] is True,
            id="emby-api-key",
        ),
        pytest.param({"emby": {"api_key": ""}}, lambda out: out["emby"]["api_key"] == "", id="emby-api-key-empty"),
        pytest.param(
            {"notify": {"dingtalk_webhook": "https://x/y?access_token=t", "dingtalk_secret": "SEC"}},
            lambda out: out["notify"]["dingtalk_webhook"] == REDACTION_PLACEHOLDER
            and out["notify"]["dingtalk_secret"] == REDACTION_PLACEHOLDER,
            id="dingtalk-secrets",
        ),
        pytest.param(
            {"network": {"proxy": "socks5://user:pass@127.0.0.1:7890"}},
            lambda out: out["network"]["proxy"] == "socks5://127.0.0.1:7890",
            id="proxy-strip-userinfo",
        ),
        pytest.param(
            {"network": {"proxy": "http://127.0.0.1:8080"}},
            lambda out: out["network"]["proxy"] == "http://127.0.0.1:8080",
            id="proxy-no-userinfo",
        ),
        pytest.param({"network": {"proxy": None}}, lambda out: out["network"]["proxy"] is None, id="proxy-null"),
        pytest.param(
            {
                "r18": {
                    "dsn": "postgresql://admin:s3cret@db:5432/postgres",
                    "read_password": "ro_pass",
                }
            },
            lambda out: (
                out["r18"]["read_password"] == REDACTION_PLACEHOLDER
                and "***" in out["r18"]["dsn"]
                and "s3cret" not in out["r18"]["dsn"]
            ),
            id="r18-dsn-and-password",
        ),
        pytest.param(
            {"plugins": {"acme.fake": {"config": {"api_token": "secret", "endpoint": "https://example.test"}}}},
            lambda out: (
                out["plugins"]["acme.fake"]["config"]["api_token"] == REDACTION_PLACEHOLDER
                and out["plugins"]["acme.fake"]["config"]["endpoint"] == "https://example.test"
            ),
            id="plugin-secret",
        ),
    ],
)
def test_redact_hot(input_hot: dict, assertions):
    out = redact_hot(input_hot)
    assert assertions(out)


def test_redact_hot_does_not_mutate_input():
    original = {
        "scraping": {"site_config": {"javdb": {"cookie": {"a": "b"}, "api_token": "t"}}},
        "emby": {"api_key": "k"},
    }
    redact_hot(original)
    assert original["scraping"]["site_config"]["javdb"]["cookie"]["a"] == "b"
    assert original["emby"]["api_key"] == "k"


@pytest.mark.parametrize(
    ("proxy", "expected"),
    [
        ("socks5://u:p@host:1", "socks5://host:1"),
        ("http://host", "http://host"),
        ("http://user@host:80/path", "http://host:80/path"),
    ],
)
def test_redact_proxy(proxy: str, expected: str):
    assert redact_proxy(proxy) == expected


def test_redact_dsn_hides_password():
    assert "secret" not in redact_dsn("postgresql://u:secret@localhost/db")
    assert "localhost" in redact_dsn("postgresql://u:secret@localhost/db")
