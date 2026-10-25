# 本地账单验算器

用给定的公开客户单价、请求开始时间和完整 `usage`，在本机拆解单次文本调用的费用。Python 3.10+，仅使用标准库，不需要安装依赖或配置 API Key。

**这里只实现公开价格公式。** 不包含余额、预扣、扣款、并发控制、流式异常估算、支付或风控实现，也不会访问网络或读取客户账户。CLI 只读取你指定的本地 JSON 文件。

## 先运行一个例子

在仓库根目录执行：

```bash
python3 -B billing-calculator/calculator.py \
  --prices billing-calculator/public-prices-2026-10-25.json \
  --request billing-calculator/examples/anthropic-cache.json
```

该合成例子的结果为 **USD 0.007543**，包含普通输入、缓存命中、5 分钟写入、1 小时写入和输出五项。示例中的用量和调用时间均为人工构造，没有真实客户记录，也不会产生调用费用。

另外两个例子：

```bash
python3 -B billing-calculator/calculator.py \
  --prices billing-calculator/public-prices-2026-10-25.json \
  --request billing-calculator/examples/gpt-long-context.json

python3 -B billing-calculator/calculator.py \
  --prices billing-calculator/public-prices-2026-10-25.json \
  --request billing-calculator/examples/deepseek-off-peak.json \
  --calendar billing-calculator/calendar-2026.json
```

`--request -` 从标准输入读取；成功时向 stdout 输出结果 JSON，失败时向 stderr 输出 `error.code` / `error.message`，退出码为 `2`。

| 合成示例 | 快照下的合计美元 |
|---|---|
| `anthropic-cache.json` | `0.007543` |
| `gpt-long-context.json` | `0.016258` |
| `deepseek-off-peak.json` | `0.001721` |

## 输入

```json
{
  "model_id": "claude-sonnet-5-5",
  "request_started_at": "2026-10-25T10:00:00+08:00",
  "usage_format": "anthropic",
  "input_modality": "text",
  "usage": {
    "input_tokens": 1000,
    "output_tokens": 500,
    "cache_read_input_tokens": 400,
    "cache_creation_input_tokens": 300,
    "cache_creation": {
      "ephemeral_5m_input_tokens": 200,
      "ephemeral_1h_input_tokens": 100
    }
  }
}
```

| 字段 | 要求 |
|---|---|
| `model_id` | 与价格 JSON 的 ID 完全一致，不做名称推测 |
| `request_started_at` | 含时区的 ISO 时间（最多微秒精度），或精确 Unix 秒数；不要填写请求结束时间 |
| `usage_format` | `openai-chat`、`openai-responses`、`anthropic` 或 `normalized` |
| `input_modality` | 当前必须明确填写 `text` |
| `usage` | 完整、最终用量对象；Token 必须是非负 JSON 整数 |
| `cache_write_ttl` | 可选：`5m` / `1h`；仅当你确认本次请求的写入 TTL 时使用 |
| `exchange_rate` | 可选：本次请求实际采用的人民币兑美元换算系数，如字符串 `"6.83"` |
| `require_valid_quote` | 可选布尔值，默认 `false`；设为 `true` 时还要求请求落在所提供报价的有效窗内 |

不要放入 Key、提示词、邮箱或完整控制台导出。该 schema 只接受上述字段。不要把多个 SSE 用量片段直接相加；本工具不负责事件合并或缺失用量估算。

### 不同接口的缓存口径

- **OpenAI Chat**：`prompt_tokens` 包含缓存；普通输入 = 总输入 − 缓存读 − 缓存写。
- **Responses**：同样使用包含缓存的 `input_tokens`，缓存通常在 `input_tokens_details.cached_tokens`。
- **Anthropic 原生**：`input_tokens` 是普通输入，缓存读写另计；上下文总输入为三者之和。
- **DeepSeek 兼容响应**：识别 `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`，并核对其与总输入的一致性。
- **推理 Token**：已包含在输出总量中，不重复相加。

缓存写入总量必须与 5m / 1h 分项之和一致。只提供总写入量、且模型分 TTL 定价时，需要明确的请求 TTL，否则拒算。不能默认所有写入都是 5 分钟。

如需自己转换其他用量格式，`normalized` 必须显式提供六个互斥类别，未使用项填 `0`：

```json
{
  "input_uncached": 1000,
  "cache_read": 400,
  "cache_write": 0,
  "cache_write_5m": 200,
  "cache_write_1h": 100,
  "output": 500
}
```

`cache_write` 与 TTL 分项不能同时为正数。普通输入不含缓存；`input_total` 可选，若填写则必须等于全部输入类别之和。

## 价格与公式

价格文件采用公开目录的 `items` 数组，单价单位是 **USD / 百万 Token**。使用 `customer_*` 客户售价，**不再乘折扣或时段 factor**：客户价已经包含这些因素，官方参考价不参与验算。

```text
每项未舍入美元 = Token 数 × 客户单价 × 适用倍率 ÷ 1,000,000
未舍入合计美元 = 全部项目之和
美元金额       = 合计后 ROUND_HALF_UP，保留 6 位小数
人民币金额     = 未舍入合计美元 × 请求实际汇率，再独立舍入为 6 位
```

不逐项提前舍入，不先将美元舍入再换汇。`amount_usd_micros` / `cny.amount_micros` 是对应币种百万分之一单位的整数。余额界面可能只展示到分，不能用它的显示变化替代单笔金额。

### 长上下文

从每个模型的 `context_pricing` 读取阈值、`whole_request` 范围及输入 / 缓存 / 输出倍率；总输入包含缓存。**严格大于**阈值才对整笔对应类别加倍率，等于阈值仍使用标准价格。不按模型名前缀猜测规则。

随附快照中，Haiku 的阈值为 100,000，超过后输入 / 缓存 / 输出均 ×5；启用对应规则的 GPT-6 模型阈值为 272,000，超过后输入 / 缓存 ×2、输出 ×1.5。这些是有日期的快照规则，不能当作未来承诺。

### DeepSeek 分时

按**请求开始时间**一次选定整笔调用的价格档位；执行跨过时段边界不重新选价。读取 `time_pricing.tiers` 的最终客户价，不叠乘顶层价或折扣。

随附规则使用北京时间 UTC+08:00：周一至周五且非节假日的 `[09:00, 12:00)`、`[14:00, 18:00)` 为高峰，其他为空闲。**周末即使调休上班仍按空闲**，因此不能笼统写作“法定工作日”。

`calendar-2026.json` 只包含 2026 年公开节假日日期和公开时段规则，不是服务端代码，也不是实时日历服务。它与报价的 `calendar_version` / `rule_version` 必须匹配，未知年份拒算。

没有日历时，仅当请求处于报价 `quoted_at <= 开始时间 < valid_until`，且报价标明 `calendar_confirmed=true` 时，才能使用该报价的档位。CLI 默认读取随附日历，Python 纯函数需显式传入。

## 输出与历史对账边界

结果含归一化 Token、各项单价和倍率、未舍入分项、合计、所选时段、舍入方式及警告。未给汇率时 `cny=null`，不从今天的设置猜测。

`public-prices-2026-10-25.json` 是 **2026-10-25 北京时间抓取的公开快照**，元数据保留来源和原始响应摘要。它不会自动更新。后续可以手动保存 [公开价格目录](https://dashboard.302api.com/api/public/models)，保留抓取时间；不要把今天的目录当作旧账单的锁定价格。

**验算结果只证明“给定这些输入，公式算得这个金额”。** 要核对真实历史账单，还需要该次请求真实锁定的客户价格与规则版本、完整最终用量、开始时间和实际汇率。价格调整、缺失用量、异常估算、赠金或账务变动不在本工具证明范围内。

- 结果始终为 `calculation_scope=public_formula_only`、`historical_price_match_verified=false`。
- `require_valid_quote=true` 只检查你提供的有效窗，不认证价格来源或历史真实性。
- 分时模型使用自身报价窗；非分时模型需提供 `catalog._metadata.quote_window` 的 `valid_from` / `valid_until`。有效窗均为左闭右开。
- 默认允许用有版本日历和给定单价做历史公式演算，但明确警告其历史有效性未经证明。

## Python 调用

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("billing-calculator").resolve()))
from calculator import calculate, load_json

prices = load_json(Path("billing-calculator/public-prices-2026-10-25.json").read_text())
request = load_json(Path("billing-calculator/examples/anthropic-cache.json").read_text())
result = calculate(request, prices)
print(result["amount_usd"])
```

`calculate(request, catalog, calendar=None)` 不读取文件、环境或系统时间，不修改输入。`normalize_usage()` 可单独用于类别转换。失败抛出带 `.code` 的 `CalculationError`。

请用 `load_json()` 读取 JSON，或直接传 `Decimal` / 十进制字符串。金额和倍率拒绝 Python 二进制 `float`，避免先丢失精度再验算；JSON 重复键、NaN、Infinity 均拒绝。数值 Unix 秒最多支持 32 位数字、30 位小数；报价窗比较保留完整精度，时间显示和日历选择向下取到微秒。

## 支持范围与测试

初版支持 `model_type=chat` 且没有独立 `modality_prices` 的文本与缓存公式。不支持图像、音频、向量、收费工具、预测输出或其他非标准服务档位的报价。发现非零未知用量、缺少所需单价、缓存口径冲突、日历缺失等情况会报错，不将未知费用当零。

```bash
python3 -B -m unittest discover -s billing-calculator -p 'test_*.py' -v
```

测试使用合成用量；规则边界使用合成价格，随附三个示例另以公开价格快照回归。覆盖缓存分类、阈值边界、分时边界、合计舍入、独立换汇、异常输入和本地函数隔离。它们验证公开公式的实现，不等于服务端账务、安全或完整线上验收。
