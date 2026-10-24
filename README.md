# 302API Developer Kit

**302API 的公开开发者资料与接入示例。商业用途须事先取得书面授权。** 提供技术说明、Python / Node.js / cURL 示例、客户端配置和无框架依赖的前端组件。

[官网](https://302api.com) · [模型与价格](https://302api.com/models) · [接入文档](https://302api.com/docs) · [教程](https://302api.com/guides/) · [服务状态](https://302api.com/status/)

## 公开范围

| 内容 | 位置 |
|---|---|
| 快速开始、地址与协议选择 | [docs/quick-start.md](docs/quick-start.md) |
| 对外技术能力与边界 | [docs/technical-overview.md](docs/technical-overview.md) |
| 常见接入问题 | [docs/troubleshooting.md](docs/troubleshooting.md) |
| Python：聊天、流式、Anthropic Messages | [examples/python/](examples/python/) |
| Node.js：聊天、Responses | [examples/node/](examples/node/) |
| cURL：模型列表、聊天 | [examples/curl/](examples/curl/) |
| DSH、Cherry Studio、Claude Code 配置 | [clients/](clients/) |
| 代码复制、模型筛选、状态展示组件 | [components/](components/) |
| 不访问生产接口的组件演示 | [demo/](demo/) |
| 安全问题报告与贡献说明 | [SECURITY.md](SECURITY.md)、[CONTRIBUTING.md](CONTRIBUTING.md) |

这是第一阶段公开资料。**没有公开生产后端、账户系统、支付回调、计费结算实现、生产配置或用户数据。** 前端组件为独立示例实现，不能把本仓库称为完整网站源码开源。

## 最短接入路径

1. 在 [控制台](https://dashboard.302api.com/login) 创建自己的 API Key。
2. 查询该 Key 当前可用的模型 ID，并确认模型支持的协议。
3. 选择一个下面的示例，配置环境变量后运行。

以下命令以 Bash 为例，Key 交互输入，不出现在命令历史中：

```bash
read -r -s -p '302API Key: ' API_302API_KEY; printf '\n'
export API_302API_KEY
export API_302API_BASE_URL='https://api.302api.com/v1'

# 先查看 Key 当前有权限访问的模型列表
bash examples/curl/models.sh

# 用上一步获得的真实 ID 替换占位符
export MODEL_ID='MODEL_ID_HERE'
```

`.env.example` 只列出变量名称，脚本不自动加载该文件。不同 Shell 的交互输入语法不同，详见 [快速开始](docs/quick-start.md)。

### Python

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python examples/python/chat.py
python examples/python/stream.py
```

Anthropic 原生接口使用独立的模型变量与根地址：

```bash
export ANTHROPIC_BASE_URL='https://api.302api.com'
export ANTHROPIC_MODEL_ID='NATIVE_MODEL_ID_HERE'
python examples/python/anthropic_messages.py
```

### Node.js

需要 Node.js 20 或以上。示例运行在服务端 / 本机 Node.js，不要将 Key 打包进公开网页。

```bash
npm install
node examples/node/chat.mjs

# 需先选择支持 Responses 的模型
node examples/node/responses.mjs
```

### cURL

```bash
bash examples/curl/chat.sh
```

cURL 示例需要较新的 cURL（支持 `--fail-with-body`）；聊天脚本还使用 Python 3 生成 JSON。

运行推理示例会产生相应调用费用。示例将 SDK 自动重试关闭，避免不清楚结果时反复调用；生产项目应自行设计超时、重试、去重与对账策略。

## 客户端配置

- [DSH 最小 Profile 补丁](clients/dsh/README.md)：只增加 provider 和默认模型，不修改原有沙箱 / 审批权限。
- [Cherry Studio](clients/cherry-studio/README.md)：OpenAI 兼容地址与模型配置。
- [Claude Code](clients/claude-code/README.md)：Anthropic 原生入口、环境变量与模型选择。

客户端、模型和协议需要同时匹配。支持 OpenAI 兼容接口，不代表任意模型都支持 Responses、图片、工具调用或所有 OpenAI 产品功能。

## 前端组件演示

```bash
python3 -m http.server 8080 --bind 127.0.0.1
```

打开 `http://127.0.0.1:8080/demo/`。演示使用明确标注的虚构模型和未知状态，不携带 Key，不请求生产接口。复用方式见 [组件文档](components/README.md)。

## 透明度与验证范围

- 示例不写死模型清单、价格、折扣或上下文上限，避免文档变成过期承诺。
- 仓库内容已做凭据与私人信息扫描、语法检查、JSON / YAML 结构检查和相对文档链接检查。
- 本次未进行真实付费推理、第三方客户端、浏览器 / 移动设备或完整安全验收；示例和组件不能据此被视为所有环境都已验证。
- 公开资料不单独证明线上部署版本、上游来源或实时服务可用性；相应信息应结合公开规则、实际账单与真实观测核对。

## 许可证与商业授权

本版本自行编写的代码和文档采用 [PolyForm Noncommercial 1.0.0](LICENSE)。非商业学习、研究、实验等用途依许可证使用；**商业用途须另行取得维护者的书面商业授权**。具体允许用途、机构例外、分发和通知义务以许可证原文为准。

这是限制商业用途的 **source-available（源码可见）** 项目，不属于 OSI 定义的开源软件。商业授权申请及旧版本许可说明见 [LICENSING.md](LICENSING.md)。

初始提交曾以 MIT 许可证公开，已授予的旧版本许可不会被本次变更追溯撤回。后续新增、修改内容以对应版本许可证为准；不能认为更换默认分支的许可就阻止了他人依旧 MIT 版本使用已有代码。

许可证不授权使用未包含的生产代码、用户数据、第三方产品商标或 302API 品牌标识。第三方 SDK、客户端及其名称按各自许可证和权利使用；本项目不表示获得这些厂商的官方背书。
