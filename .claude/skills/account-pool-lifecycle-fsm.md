---
name: account-pool-lifecycle-fsm
description: Account Pool 2.0 多源邮箱与账号生命周期状态机 (FSM) 运维及排障规范
version: 5.0.0
last_verified: 2026-08-25
---

# Account Pool 2.0 运维与排障规范

## 1. 架构拓扑与状态机 (FSM)
- **多源邮箱**：`BaseMailSource` 支持 `LinshiMailSource`、`MailTmSource`、`GuerrillaMailSource`、`CustomImapSource`、`Do22Source`、`TempMailSource`。
- **动态选源**：根据优先级、成功率（Laplace平滑）与 429 冷却动态降级切源。
- **账号生命周期**：
  `unregistered` -> `registering` -> `active` (`ok`) -> `working` -> `cooling` (`exhausted`) -> `dead` (`banned`)。
- **租约管理**：使用 `async with account_pool.lease(provider) as acc:` 安全借号与异常熔断。

## 2. 自动化验证命令
```bash
# 验证多源邮箱策略
python -m pytest tests/test_email_pool.py -v

# 验证账号 FSM 状态流转与延寿唤醒
python -m pytest tests/test_account_pool.py -v

# 验证注册器已随 nanobanana 下线（registry 必须为空）
python -m pytest tests/test_registerer_retired.py -v
```

> 说明（2026-10-14 校正）：原指南引用的 `tests/test_registerer_adaptive.py` **已不存在**——
> 注册器（`api/registerer.py::build_registerers`）随 nanobanana 下线后返回 `{}`，
> 自适应退避测试一并移除。对应的 `IF_REG_BACKOFF_*` 配置项仍保留于
> `api/config/`（`reg_backoff_ip` / `reg_backoff_transient_base` /
> `reg_backoff_transient_max`），但当前**无消费者**（保留以备注册器恢复）。


## 3. 监控快照与看板
- `/healthz`、`/v1/stats`、前端「号池」页：
  - 各提供商状态：`total`, `ok`, `working`, `cooling`, `dead`, `registering`, `credits`。
  - 邮箱源状态：各源故障计数、评分与冷却剩余时间。
