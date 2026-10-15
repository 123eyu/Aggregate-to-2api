"""集成测试：捐赠页（/v1/honor）+ 首页 footer 捐赠入口。"""

from pathlib import Path

import pytest

# `/` 由 api/main.py **条件挂载**（`if _LANDING_DIR.exists()`）——landing 未构建时
# 该挂载整个跳过，`GET /` 落到 404。
# 后端 CI job（.github/workflows/ci.yml 的 unit 矩阵）**只装 Python 依赖、不构建前端**，
# 故 CI 上 landing/dist 必然不存在；而本地开发机通常已 `npm run build` 过。
# 本文件的首页断言必须先确认这个前置条件，否则会在 CI 上稳定误报（实测：
# run 38777822213 的 pytest-intg-junit —— `assert 404 == 200`）。
_LANDING_INDEX = Path(__file__).resolve().parents[2] / "landing" / "dist" / "index.html"


@pytest.mark.integration
class TestHonor:
    """捐赠通道端点 + 首页 footer 落地。"""

    async def test_honor_returns_donation_page(self, app_with_mocks):
        """GET /v1/honor 返回渲染好的独立 HTML 页面。"""
        client = app_with_mocks
        r = await client.get("/v1/honor")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("text/html")
        assert "支持听风AI" in r.text
        assert "/static/zanshang.jpg" in r.text

    async def test_honor_data_returns_json(self, app_with_mocks):
        """GET /v1/honor/data 返回 JSON 数据。"""
        client = app_with_mocks
        r = await client.get("/v1/honor/data")
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") == "ok"
        assert body.get("qr_path") == "/static/zanshang.jpg"
        assert body.get("contact_wx") == "Tf00798"
        assert body.get("title") == "支持听风"

    async def test_index_linked_to_zanshang(self, app_with_mocks):
        """GET / 返回 200 且为 Vue3 公开落地页（SPA shell 由 JS 挂载）。

        前置条件：`landing/dist` 必须已构建 —— 否则 `api/main.py` 的条件挂载不生效，
        `GET /` 返回 404，本测试在 CI 后端 job 上会稳定失败（该 job 不构建前端）。
        未构建时 skip，并说明原因，而不是把「环境缺产物」误报成「功能坏了」。
        """
        if not _LANDING_INDEX.exists():
            pytest.skip("landing/dist 未构建（后端 CI job 不构建前端），跳过首页 SPA 断言")
        client = app_with_mocks
        r = await client.get("/")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("text/html")
        # v6.5.0：公开首页改为 Vue3 落地页（引导至 /admin、/docs、/v1/honor 捐赠页）。
        # / 现在返回 SPA 壳（<div id="app"> + /assets/* 脚本），内容由 JS 渲染，不再内联单文件 docs.html。
        assert 'id="app"' in r.text
        assert "/assets/" in r.text
