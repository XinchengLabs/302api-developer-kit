# Cline（VS Code）

完整图文步骤见官网教程：[Cline 接入 302API](https://302api.com/guides/cline/)。

## 推荐：OpenAI Compatible

在 Cline 设置的 **API Provider** 选择 **OpenAI Compatible**：

| 字段 | 填写 |
|---|---|
| Base URL | `https://api.302api.com/v1` |
| API Key | 你的 302API Key（`sk-302api-` 开头，建议给 Cline 单独建一个并设置消费上限） |
| Model ID | `claude-sonnet-5-5`（推荐），或 `claude-opus-5-5`、`gpt-6-sol`、`gemini-3.8-flash` 等 |

这种方式可以填任意本站模型 ID，Claude、GPT、Gemini 共用一个 Key 和余额。

**用 Claude 时自动省钱**：Cline 每一步都会重发大量项目上下文。通过 OpenAI Compatible 调用 Claude 时，本站网关会自动加提示缓存标记，后续轮次的重复上下文按缓存命中价计费，不需要在 Cline 里做任何设置。详见 [技术概览](../../docs/technical-overview.md#兼容接口调用-claude-的提示缓存2026-11-22-起)。

## 也可以：Anthropic 方式

API Provider 选 **Anthropic**，勾选自定义地址并填 `https://api.302api.com`（**不带** `/v1`）。前提是 Cline 的模型列表里有你要用的型号。

## 控制成本

- 日常任务用 `claude-sonnet-5-5`，简单任务换 `claude-haiku-5-5` 或 `gpt-6-luna`，大型重构再用 `claude-opus-5-5`。
- Cline 的 Plan / Act 模式可以分别设置模型。
- 一个任务完成后开新任务，避免历史上下文越积越长。

## 常见问题

| 现象 | 处理 |
|---|---|
| 404 或连接失败 | OpenAI Compatible 的地址要带 `/v1`；Anthropic 方式的自定义地址不带 `/v1` |
| 403 模型不可用 | Model ID 必须与本站模型 ID 完全一致，不能填展示名称；可以用 `python3 tools/doctor.py` 列出当前 Key 可用的全部模型 |
