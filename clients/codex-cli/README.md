# Codex CLI

Codex CLI 通过 **Responses 接口**接入本站。完整图文步骤见官网教程：[Codex CLI 接入 302API](https://302api.com/guides/codex-cli/)。

## 配置

1. 把本站 Key 放在环境变量 `API302_KEY`（不要写进配置文件）：

   ```bash
   read -r -s -p '302API Key: ' API302_KEY; printf '\n'; export API302_KEY
   ```

2. 在 `~/.codex/config.toml`（Windows 为 `%USERPROFILE%\.codex\config.toml`，设置了 `CODEX_HOME` 时以它为准）**合并**以下字段，修改前先备份：

   ```toml
   model = "gpt-6-luna"
   model_provider = "302api"

   [model_providers.302api]
   name = "302API"
   base_url = "https://api.302api.com/v1"
   env_key = "API302_KEY"
   wire_api = "responses"
   supports_websockets = false
   ```

3. 运行 `codex`，发一个短任务，然后在控制台调用记录里核对模型、用量和扣费。

## 要点

- 服务商名称用自定义的 `302api`，不要占用内置的 `openai`。
- `base_url` 带 `/v1`，不要写完整的 `/responses` 路径；`env_key` 填的是**变量名**，不是 Key 本身。
- 本站按 SSE 流式接入，所以关闭 WebSocket（`supports_websockets = false`）。
- 可选模型：`gpt-6-luna`（最省）、`gpt-6-sol`、`gpt-6-astra` 等支持 Responses 的模型，以 [模型页](https://302api.com/models) 为准。
- Responses 的 HTTP 200 也可能带 `incomplete` 或 `error` 状态，要看最终结束原因，不能只看界面出现了文字。

## 常见问题

| 现象 | 处理 |
|---|---|
| 仍在用其他账号或服务商 | 检查 `model_provider` 是否为 `302api`，有没有 profile 或命令行参数覆盖 |
| 提示缺少 `API302_KEY` | 在启动 Codex 的同一个终端里设置变量；已打开的进程不会读到新变量 |
| 404 / 协议错误 | 地址应为 `https://api.302api.com/v1`，并且 `wire_api = "responses"`，不要写成 `/v1/v1` |
