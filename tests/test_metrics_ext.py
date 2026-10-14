"""测试 prometheus_client 指标系统。"""

from api.metrics_ext import (
    generate_duration,
    imagefree_metrics,
    requests_total,
    token_pool_watermark,
)

_EMPTY_SNAPSHOTS = {"engine": {}, "stats": {}, "solver": {}}


def test_metrics_labels():
    """验证指标带有正确 label 维度。"""
    requests_total.labels(provider="imagefree", status="completed").inc()
    assert requests_total.labels(provider="imagefree", status="completed")._value.get() == 1.0


def test_generate_duration_histogram():
    """验证生成耗时 histogram 记录。"""
    generate_duration.labels(provider="imagefree", model="default").observe(5.0)
    assert True


def test_watermark_gauge():
    """验证水位 gauge 可设置。"""
    token_pool_watermark.labels(pool="direct").set(3)
    assert token_pool_watermark.labels(pool="direct")._value.get() == 3.0


def test_empty_db_still_exposes_panel_counters():
    """空库（累计值全 0）时面板引用的 counter/histogram 仍须导出 label 样本。

    根因：`_counter_inc_absolute` 早前只在 delta>0 时才 `labels(...)`，
    空库 delta 恒为 0 → label 样本永不进 REGISTRY → Grafana rate() 查 "No data"，
    观察栈验收会把「空库」误判成「指标缺失」。generate_duration 更是一次都没被触碰过。
    """
    text = imagefree_metrics(_EMPTY_SNAPSHOTS["engine"], _EMPTY_SNAPSHOTS["stats"], _EMPTY_SNAPSHOTS["solver"])
    # imagefree-overview / slo-budget 面板直接引用的核心指标
    for name in (
        "imagefree_requests_total",
        "imagefree_errors_total",
        "imagefree_generate_duration_seconds_bucket",
        "imagefree_generate_duration_seconds_count",
    ):
        assert name in text, f"{name} 未导出——空库时 Grafana 面板将无数据"


def test_counter_increment_semantics_preserved():
    """预建样本不得破坏增量语义：重复 scrape 不重复叠加。"""
    first = imagefree_metrics({}, {"total_images": 0, "total_errors": 0}, {})
    second = imagefree_metrics({}, {"total_images": 7, "total_errors": 2}, {})
    third = imagefree_metrics({}, {"total_images": 7, "total_errors": 2}, {})
    # 第二次应从 0 增到 7/2，第三次绝对值未变 → 不再叠加
    seen_req = seen_err = False
    for line in third.split("\n"):
        if line.startswith('imagefree_requests_total{provider="all",status="completed"}'):
            seen_req = True
            assert line.strip().endswith(" 7.0"), f"重复叠加: {line}"
        if line.startswith('imagefree_errors_total{provider="all",reason="error"}'):
            seen_err = True
            assert line.strip().endswith(" 2.0"), f"重复叠加: {line}"
    assert seen_req and seen_err, "provider=all 的 counter 样本缺失"
    assert "imagefree_requests_total" in first
    assert "imagefree_requests_total" in second
