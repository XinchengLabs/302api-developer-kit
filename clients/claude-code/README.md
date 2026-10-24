# Claude Code

需要选择本站当前支持 **Anthropic 原生接口** 的模型。不要用 OpenAI 兼容地址 `/v1` 作为此客户端的根地址。

在启动客户端的终端中配置：

```bash
export ANTHROPIC_BASE_URL='https://api.302api.com'
read -r -s -p '302API Key: ' ANTHROPIC_AUTH_TOKEN; printf '\n'
export ANTHROPIC_AUTH_TOKEN
export ANTHROPIC_MODEL='MODEL_ID_HERE'
claude
```

上述交互读取语法用于 Bash；在其他 Shell 中使用其对应的安全输入方式。将 `MODEL_ID_HERE` 替换为当前可用且支持该协议的模型 ID。

客户端存在已有登录状态、其他 Anthropic 认证变量或自定义设置时，先检查配置来源，避免混用。不同版本对模型别名、工具调用及认证方式可能有差异。

这是第三方 API 接入配置，不表示拥有 Anthropic 官方订阅权益，也不表示所有 Claude Code 功能均由任意模型支持。
