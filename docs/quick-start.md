# 快速开始

## 1. 取得 Key 与模型 ID

在 [302API 控制台](https://dashboard.302api.com/login) 登录并创建 Key。Key 是账户访问凭据，不应提交到 Git、放进公开浏览器代码或包含在排障截图中。

模型名必须使用当前 Key 可访问的实际 ID；展示名称不一定等于 API ID。本仓库不固定推荐某个型号，避免名称及支持范围变化造成错误。

## 2. 选择协议和地址

| 场景 | 配置地址 | 典型最终请求 |
|---|---|---|
| OpenAI SDK / 通用兼容客户端 | `https://api.302api.com/v1` | `/v1/chat/completions`、`/v1/responses` |
| Anthropic SDK | `https://api.302api.com` | `/v1/messages` |
| Claude Code | `https://api.302api.com` | 原生 Anthropic 路径 |
| 本仓库 DSH 补丁 | `https://api.302api.com` | 按 DSH 插件规则补全路径 |

同一个模型不一定支持所有协议。先确认模型与路由，再配置地址；避免重复 `/v1`，也不要自行拼接错误的 `/admin` 等前缀。

## 3. 配置环境变量

以下是 Bash 示例：

```bash
read -r -s -p '302API Key: ' API_302API_KEY; printf '\n'
export API_302API_KEY
export API_302API_BASE_URL='https://api.302api.com/v1'
export MODEL_ID='MODEL_ID_HERE'
```

在 zsh 中可以使用 `read -r -s 'API_302API_KEY?302API Key: '; printf '\n'`，然后导出变量。其他终端和部署平台可使用自己的环境变量 / 密钥管理功能。

示例程序直接读取进程环境，不会自动加载 `.env`。不要把 API Key 添加到仓库跟踪的 JSON、YAML、脚本或组件属性中。

## 4. 首次请求

先运行不生成模型文本的模型列表查询：

```bash
bash examples/curl/models.sh
```

从结果中选取支持目标协议的模型 ID，设置 `MODEL_ID`，再运行一个短文本示例。列表查询通过，只代表鉴权和列表入口可用，不能证明每个模型推理均正常。

示例中的 `max_tokens=256` 是该请求的输出预算，不代表本站或模型的最大输出量。客户端可以按模型实际能力配置输出、上下文及图片等参数。

## 5. 流式与错误处理

- `stream=True` 返回的是持续读取的事件流，不是一次完整 JSON。
- 某个分块带有文字，不能证明流已经完整结束；HTTP 200 也不能单独证明最终结算成功。
- `usage` 是否完整、缓存类别及最终账单需要分别核对；不要用界面显示的字符数估算实际 Token 账单。
- 超时后的结果可能不确定，不要立即无限重试；先检查调用记录和请求关联 ID。
- 生产项目需要自己的超时、重试和错误呈现策略，本仓库示例侧重最小接入。

## 6. 运行环境

Python 示例建议 Python 3.10 或以上，并按 `requirements.txt` 安装 SDK。Node.js 示例需要 20 或以上；依赖版本范围写在 `package.json`。

SDK 示例应在本机、服务端或受控运行环境中执行。浏览器组件只处理展示与本地交互，不应该直接持有付费 API Key。
