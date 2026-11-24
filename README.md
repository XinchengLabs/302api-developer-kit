# 302API Developer Kit

[![CI](https://github.com/XinchengLabs/302api-developer-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/XinchengLabs/302api-developer-kit/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![Node.js 20+](https://img.shields.io/badge/Node.js-20%2B-339933)

**一个 Key 调用 Claude、GPT、Gemini 官方模型的开源接入工具包。** 一条命令自检接入，十余个可直接运行的示例，主流 AI 编程工具的现成配置，以及能逐笔核对账单的本地验算器。

[官网](https://302api.com) · [模型与价格](https://302api.com/models) · [接入文档](https://302api.com/docs) · [教程](https://302api.com/guides/) · [服务状态](https://302api.com/status/) · [获取 API Key](https://dashboard.302api.com/login)

## 为什么选 302API

| | |
|---|---|
| **正规线路，不用号池** | 调用走官方 API 线路，不共享账号、不走逆向网页接口；模型名就是实际调用的模型 |
| **两种原生协议** | OpenAI 兼容（`/v1/chat/completions`、`/v1/responses`）与 Anthropic 原生（`/v1/messages`）同时支持，现有 SDK 改地址和 Key 即可 |
| **账单可以自己算** | 每次调用都有请求编号和完整用量；用本仓库的 [验算器](billing-calculator/) 按公开价格算出的金额，与控制台扣费逐笔一致 |
| **长对话自动省钱** | 用 OpenAI 格式调用 Claude 时，网关自动加提示缓存标记，重复上下文按缓存价计费（[实测数据](#兼容接口自动缓存)） |

价格以 [模型页](https://302api.com/models) 为准；本仓库的示例不写死价格和折扣。

## 30 秒上手

**1. 创建 Key**：在 [控制台](https://dashboard.302api.com/login) 注册并创建 API Key（新用户赠送体验额度）。

**2. 一键自检**（只用 Python 标准库，不用装依赖，不产生费用）：

```bash
read -r -s -p '302API Key: ' API_302API_KEY; printf '\n'; export API_302API_KEY
python3 tools/doctor.py
```

它会检查 Key 格式、地址、网络和鉴权，列出这个 Key 能用的全部模型和单价，最后给出 OpenAI SDK、Anthropic SDK、Codex CLI 可直接复制的配置。加 `--chat gpt-6-luna` 会再发一次很短的真实对话（花费不到一分钱）。

**3. 发第一个请求**：

```python
from openai import OpenAI

client = OpenAI(api_key="你的 Key", base_url="https://api.302api.com/v1")
reply = client.chat.completions.create(
    model="claude-sonnet-5-5",  # 或 gpt-6-sol、gemini-3.8-flash……同一个 Key 通用
    messages=[{"role": "user", "content": "你好"}],
)
print(reply.choices[0].message.content)
```

## 示例一览

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
export MODEL_ID=gpt-6-luna    # 用 tools/doctor.py 列出的任意对话模型
```

| 场景 | 运行 | 说明 |
|---|---|---|
| 基础对话 | `python examples/python/chat.py` | 最小的 Chat Completions 调用 |
| 流式输出 | `python examples/python/stream.py` | 逐字输出，并读取最后的用量 |
| 工具调用 | `python examples/python/tool_calling.py` | 模型请求调用函数 → 本地执行 → 把结果交回模型，完整往返 |
| 看图 | `python examples/python/vision.py` | 现场生成一张图片发给模型，不依赖外部图片地址 |
| 文生图 | `python examples/python/generate_image.py "画一张雨夜书店的水彩插画"` | 生成一张 PNG 到当前目录，终端会显示文件路径。[示例源码](examples/python/generate_image.py) |
| 自动缓存 | `python examples/python/prompt_cache.py` | 多轮长对话逐轮显示缓存写入 / 命中和省下的费用 |
| 账单验算 | `python examples/python/verify_bill.py` | 调用一次，再用离线验算器算出应扣金额，按请求编号到控制台核对 |
| Anthropic 原生 | `python examples/python/anthropic_messages.py` | Anthropic SDK 直连 `/v1/messages`（需设置 `ANTHROPIC_MODEL_ID`） |
| Node.js | `node examples/node/chat.mjs`、`responses.mjs` | 先 `npm install`；Node.js 20+ |
| cURL | `bash examples/curl/models.sh`、`chat.sh` | 不装任何 SDK |

运行推理示例会产生少量调用费用。示例关闭了 SDK 的自动重试，避免结果不明时重复扣费；生产项目请自行设计超时、重试和对账。

文生图示例使用上面设置的 `API_302API_KEY`，默认用 `gpt-image-2.6-flare` 生成一张 1024×1024 的低质量档 PNG，按所用模型计费。可用环境变量 `IMAGE_MODEL_ID` 切换到你的 Key 有权调用的其他 GPT 图片模型。[生图接口文档](https://302api.com/docs/#images)

## 客户端配置

| 工具 | 接入方式 | 配置 |
|---|---|---|
| Claude Code | Anthropic 原生 | [clients/claude-code](clients/claude-code/README.md) |
| Codex CLI | Responses | [clients/codex-cli](clients/codex-cli/README.md) |
| Cline（VS Code） | OpenAI 兼容 / Anthropic | [clients/cline](clients/cline/README.md) |
| Cherry Studio | OpenAI 兼容 | [clients/cherry-studio](clients/cherry-studio/README.md) |
| DSH（DeepSeek Harness） | Profile 补丁 | [clients/dsh](clients/dsh/README.md) |

更多图文教程见 [302api.com/guides](https://302api.com/guides/)。

## 账单可以自己算

`verify_bill.py` 发一次请求，拿到用量和请求编号，再用 [离线验算器](billing-calculator/) 按公开价格逐项计算。以下是一次实测（GPT-6 Luna，汇率 6.83）：

```text
请求编号： 14c87fd25129c6ab93fdba1035888ce4
用量： {"prompt_tokens": 14, "completion_tokens": 33, "total_tokens": 47}
  普通输入：14 Token × $0.088/百万 = $0.000001232
  输出：33 Token × $0.44/百万 = $0.00001452
应扣：$0.000016（约 ¥0.000108）
```

控制台调用记录里这条请求的扣费正是 $0.000016 / ¥0.000108。验算器是纯 Python 标准库实现，覆盖缓存读写（5 分钟 / 1 小时）、长上下文倍率、分时价格和舍入规则，附 69 项单元测试；不联网、不需要 Key。

## 兼容接口自动缓存

多数 OpenAI 格式的客户端（Cline、Cherry Studio、自研应用）不会发送 `cache_control`，长对话每轮都按原价重发全部上下文。本站网关会为 Claude 的多轮长对话自动加缓存标记，客户端什么都不用改。`prompt_cache.py` 的实测（Claude Sonnet 5.5，每轮约 3 万 Token 上下文）：

| 轮次 | 缓存 | 本轮输入费用 | 不缓存需 |
|---|---|---|---|
| 第 1 轮 | 不加标记 | $0.0599 | $0.0599 |
| 第 2 轮 | 写入 31,562 Token | $0.0750 | $0.0600 |
| 第 3 轮 | 命中 31,562 Token | $0.0031 | $0.0600 |
| 第 4 轮 | 命中 31,588 Token | $0.0031 | $0.0601 |

4 轮合计 $0.141，不缓存需 $0.240，**节省 41%**；之后每一轮都只要原价的约 5%，对话越长省得越多。规则与核对方法见 [技术概览](docs/technical-overview.md#兼容接口调用-claude-的提示缓存2026-11-22-起)。

## 前端组件

无框架依赖的代码复制按钮、模型筛选器、服务状态徽标，可以直接放进你自己的站点：

```bash
python3 -m http.server 8080 --bind 127.0.0.1   # 打开 http://127.0.0.1:8080/demo/
```

演示页使用虚构数据，不携带 Key、不请求生产接口。用法见 [组件文档](components/README.md)。

## 仓库结构

```text
tools/doctor.py          一键接入自检（标准库，零依赖）
examples/python|node|curl  可运行示例
clients/                 Claude Code、Codex CLI、Cline、Cherry Studio、DSH 配置
billing-calculator/      离线账单验算器、有日期的公开价格快照、单元测试
components/ demo/        前端组件与演示页
docs/                    快速开始、技术概览、问题排查
```

## 文档

- [快速开始](docs/quick-start.md)：地址与协议怎么选、环境变量、第一次请求
- [技术概览](docs/technical-overview.md)：接口能力、自动缓存规则、计费与边界
- [问题排查](docs/troubleshooting.md)：401 / 403 / 404 / 429 / 流式中断 / 账单核对

## 公开范围与边界

- 本仓库公开的是接入资料、示例、客户端配置、前端组件和客户端侧的价格公式；**不包含**生产后端、账户与支付系统、服务端计费结算实现、生产配置或任何用户数据。
- 价格快照有日期，不会自动更新；核对历史账单请使用与调用时间对应的快照。验算结果证明“给定这些输入，公式算得这个金额”，不单独证明某次请求锁定的历史价格。
- CI 会对每次提交运行单元测试、语法和 JSON 检查；真实调用示例由维护者用测试 Key 实测（见 [RELEASE_CHECKS.json](RELEASE_CHECKS.json)），但不能保证覆盖所有客户端版本和运行环境。

安全问题请按 [SECURITY.md](SECURITY.md) 私下报告；欢迎按 [CONTRIBUTING.md](CONTRIBUTING.md) 提交改进。

## License / 开源许可

本项目以 **[Apache License 2.0](LICENSE)** 开源：个人与企业均可免费使用、修改、商用和再分发，无需另行申请授权。

- **唯一要求：保留署名。** 再分发本项目或其衍生作品时，须保留 [NOTICE](NOTICE) 中的项目名称“302API Developer Kit”与仓库地址 `https://github.com/XinchengLabs/302api-developer-kit`，并按 Apache-2.0 保留版权与许可声明、标明重要修改。
- 集成组件不需要把自有产品改成 302API 品牌，也不需要在界面上展示 302API 标志；把 NOTICE 随源码或发行包一起保留即可。
- Apache-2.0 不授予商标使用权：可以如实说明“基于 302API Developer Kit”，但不能暗示获得 302API 官方合作或背书。

API 调用费用、第三方 SDK 和客户端的许可另行适用。更多说明见 [LICENSING.md](LICENSING.md)。此前 MIT / PolyForm / 自定义许可版本已授予的权利不受影响。

---

### English

302API Developer Kit is an open-source (Apache-2.0) toolkit for calling Claude, GPT and Gemini through one API key at [302api.com](https://302api.com). It includes a zero-dependency setup checker (`tools/doctor.py`), runnable Python / Node.js / cURL examples (chat, streaming, tool calling, vision, prompt caching), ready-made configs for Claude Code, Codex CLI, Cline and Cherry Studio, and an offline billing calculator whose results match the console charge for each request. Base URL: `https://api.302api.com/v1` (OpenAI-compatible) or `https://api.302api.com` (Anthropic native).
