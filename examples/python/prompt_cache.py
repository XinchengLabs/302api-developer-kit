"""兼容接口自动缓存演示：用 OpenAI SDK 跟 Claude 进行 4 轮长对话，逐轮打印缓存写入 / 命中和按公开价格估算的输入费用。

客户端完全不用发 cache_control：本站网关会为 /v1/chat/completions 上的 Claude 多轮长对话自动加缓存标记
（第 1 轮不加，第 2 轮写入缓存，第 3 轮起命中）。响应头 X-302API-Compatibility 含 auto-prompt-cache 即表示本轮加了标记。

运行会产生少量费用（Sonnet 4 轮约 0.15 美元）。需要 API_302API_KEY；模型默认 claude-sonnet-5-5，可用 CACHE_MODEL_ID 改成其他 Claude 模型，
CACHE_TURNS 改轮数（默认 4）。
"""
import json
import os
import time
import urllib.request

from openai import OpenAI

CATALOG = "https://dashboard.302api.com/api/public/models"


def prices(model: str) -> dict:
    """从公开价格目录读本站单价（美元 / 百万 Token），读不到时只打印 Token 不估算费用。"""
    try:
        with urllib.request.urlopen(CATALOG, timeout=15) as resp:
            for item in json.load(resp)["items"]:
                if item["model_id"] == model:
                    return {k: float(item[k]) for k in ("customer_input_price", "customer_cached_input_price",
                                                         "customer_cache_write_price") if item.get(k) is not None}
    except (OSError, ValueError, KeyError):
        pass
    return {}


def main():
    key = os.environ.get("API_302API_KEY", "")
    if not key.strip():
        raise SystemExit("先设置 API_302API_KEY")
    model = os.getenv("CACHE_MODEL_ID", "claude-sonnet-5-5")
    turns = max(3, int(os.getenv("CACHE_TURNS", "4")))
    client = OpenAI(api_key=key, base_url=os.getenv("API_302API_BASE_URL", "https://api.302api.com/v1"), max_retries=0)
    p = prices(model)
    # 一份约 3 万 Token 的“参考资料”，模拟编程助手每轮都会重发的项目上下文
    stamp = str(int(time.time()))  # 每次运行不同，避免命中上一次运行留下的缓存
    doc = " ".join(f"第{i}条（{stamp}）：这是一段固定的参考资料，用来演示长上下文在多轮对话中的缓存效果。" for i in range(700))
    messages = [{"role": "system", "content": "你是简洁的助手。参考资料：" + doc}]
    total_plain = total_actual = 0.0
    print(f"模型 {model}，每轮都重发约 3 万 Token 的上下文\n")
    for turn in range(1, turns + 1):
        messages.append({"role": "user", "content": f"第 {turn} 个问题：只回复“收到 {turn}”。"})
        raw = client.chat.completions.with_raw_response.create(model=model, messages=messages, max_tokens=20)
        result = raw.parse()
        usage = result.usage
        details = (usage.model_dump().get("prompt_tokens_details") or {})
        cached = details.get("cached_tokens") or 0
        written = details.get("cache_write_tokens") or 0
        plain = usage.prompt_tokens - cached - written
        tag = "已加缓存标记" if "auto-prompt-cache" in (raw.headers.get("x-302api-compatibility") or "") else "未加标记"
        line = f"第 {turn} 轮 [{tag}] 输入 {usage.prompt_tokens}：普通 {plain} · 写入 {written} · 命中 {cached}"
        if p:
            no_cache = usage.prompt_tokens * p["customer_input_price"] / 1e6
            actual = (plain * p["customer_input_price"] + written * p.get("customer_cache_write_price", 0)
                      + cached * p.get("customer_cached_input_price", 0)) / 1e6
            total_plain, total_actual = total_plain + no_cache, total_actual + actual
            line += f"  → 输入费用 ${actual:.5f}（不缓存需 ${no_cache:.5f}）"
        print(line + f"  请求编号 {raw.headers.get('x-302api-request-id', '—')}")
        messages.append({"role": "assistant", "content": result.choices[0].message.content or ""})
    if p and total_plain:
        print(f"\n{turns} 轮合计输入费用 ${total_actual:.5f}，不缓存需 ${total_plain:.5f}，节省 {1 - total_actual / total_plain:.0%}；轮数越多省得越多。")
    print("每一轮的写入 / 命中 Token 和扣费都能在控制台调用记录里按请求编号核对。")


if __name__ == "__main__":
    main()
