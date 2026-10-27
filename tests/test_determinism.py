"""确定性守门（`plan/02` §四 / `plan/03` §六）。

三条判据，各自可证伪：
1. 同一份 payload 两次序列化逐字节相等；
2. `report.md` 两次渲染逐字节相等；
3. 报告里只有一个时间戳字段，且它的值来自 `SOURCE_DATE_EPOCH` 而非系统时钟。
"""

from __future__ import annotations

from crsscope import report


def _sample() -> report.ModuleResult:
    return report.ModuleResult(
        command="demo",
        findings=[
            report.Finding(check="magnitude", status="conflict", reason="magnitude", detail="声明为度制但量级是米", evidence={"rule": "§4.1"}),
            report.Finding(check="axis", status="consistent", detail="轴序呈 lon,lat", evidence={"rule": "§4.1"}),
        ],
        payload={"header": report.build_header("demo", declared_crs="4326"), "verdict": "存在冲突"},
        exit_code=1,
    )


def test_json_is_byte_identical_across_runs() -> None:
    first = report.dumps_json({"b": 1, "a": [3, 2, 1]})
    second = report.dumps_json({"a": [3, 2, 1], "b": 1})
    assert first.encode() == second.encode()
    assert first.endswith("\n")


def test_markdown_is_byte_identical_across_runs() -> None:
    assert report.render_markdown(_sample()) == report.render_markdown(_sample())


def test_generated_at_uses_source_date_epoch(monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    assert report.generated_at_from_env() == "2023-11-14T22:13:20Z"


def test_generated_at_falls_back_to_fixed_value(monkeypatch) -> None:
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    assert report.generated_at_from_env() == report.FALLBACK_TIMESTAMP


def test_only_one_timestamp_field_in_payload() -> None:
    payload = {"header": report.build_header("demo"), "findings": []}
    hits = []

    def walk(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == report.TIMESTAMP_FIELD:
                    hits.append(path + "/" + k)
                walk(v, path + "/" + k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(payload)
    assert len(hits) == 1, f"报告只允许一个时间戳字段，实得 {hits}"


def test_scrub_removes_absolute_paths() -> None:
    text = "读取 C:\\Users\\someone\\data\\a.geojson 失败"
    scrubbed = report.scrub(text)
    assert "someone" not in scrubbed
    assert "C:\\" not in scrubbed


def test_scrub_removes_posix_home_paths() -> None:
    assert "/home/alice" not in report.scrub("见 /home/alice/track.gpx")
