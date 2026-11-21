"""单次调用的账单自己算：发一次请求 → 拿到用量和请求编号 → 用本仓库的离线验算器按公开价格算出应扣金额。

算出来的金额应与控制台“调用记录”里这条请求的扣费一致（控制台按你的账户汇率显示人民币）。
运行会产生少量费用。需要 API_302API_KEY 和 MODEL_ID；可选 EXCHANGE_RATE（如 7.1）同时折算人民币。
用 --prices 指定本地价格快照；不指定时读取公开价格目录的当前价格。
"""
import argparse
import datetime
import json
import os
import sys
import urllib.request
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "billing-calculator"))
from calculator import calculate, load_json  # noqa: E402

CATALOG = "https://dashboard.302api.com/api/public/models"
CN = datetime.timezone(datetime.timedelta(hours=8))


def clean_usage(usage: dict) -> dict:
    """只保留验算器认识的标准字段（服务端可能附带额外的诊断字段）。"""
    out = {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens") if k in usage}
    details = usage.get("prompt_tokens_details") or {}
    kept = {k: details[k] for k in ("cached_tokens", "cache_write_tokens") if details.get(k)}
    if kept:
        out["prompt_tokens_details"] = kept
    return out


def main():
    parser = argparse.ArgumentParser(description="调用一次并离线验算这次的费用")
    parser.add_argument("--prices", help="本地价格快照，例如 billing-calculator/public-prices-2026-11-22.json")
    parser.add_argument("--prompt", default="请用一句话介绍你自己。")
    args = parser.parse_args()
    key, model = os.environ.get("API_302API_KEY", ""), os.environ.get("MODEL_ID", "")
    if not key.strip() or not model.strip():
        raise SystemExit("先设置 API_302API_KEY 和 MODEL_ID")

    if args.prices:
        catalog = load_json(Path(args.prices).read_text(encoding="utf-8"))
    else:
        with urllib.request.urlopen(CATALOG, timeout=15) as resp:
            catalog = load_json(resp.read().decode())
        catalog.setdefault("_metadata", {"schema_version": 1, "currency": "USD", "price_unit": "USD_per_million_tokens"})

    client = OpenAI(api_key=key, base_url=os.getenv("API_302API_BASE_URL", "https://api.302api.com/v1"), max_retries=0)
    started = datetime.datetime.now(CN).isoformat(timespec="seconds")
    raw = client.chat.completions.with_raw_response.create(
        model=model, messages=[{"role": "user", "content": args.prompt}], max_tokens=200)
    result = raw.parse()
    usage = clean_usage(result.usage.model_dump(exclude_none=True))
    request = {"model_id": model, "request_started_at": started, "usage_format": "openai-chat",
               "input_modality": "text", "usage": usage}
    if usage.get("prompt_tokens_details", {}).get("cache_write_tokens"):
        request["cache_write_ttl"] = "5m"  # 网关自动缓存用 5 分钟缓存；自行设置 1 小时缓存时改成 "1h"
    if os.getenv("EXCHANGE_RATE"):
        request["exchange_rate"] = os.environ["EXCHANGE_RATE"]
    quote = calculate(load_json(json.dumps(request)), catalog)

    print("回复：", (result.choices[0].message.content or "").strip()[:80])
    print("请求编号：", raw.headers.get("x-302api-request-id", "—"))
    print("用量：", json.dumps(usage, ensure_ascii=False))
    names = {"input_uncached": "普通输入", "cache_read": "缓存命中", "cache_write": "缓存写入",
             "cache_write_5m": "缓存写入（5 分钟）", "cache_write_1h": "缓存写入（1 小时）", "output": "输出"}
    for item in quote["charges"]:
        if item["tokens"]:
            print(f"  {names.get(item['category'], item['category'])}：{item['tokens']} Token × ${item['unit_price_usd_per_million']}/百万"
                  f"{'' if item['multiplier'] == '1' else ' × ' + item['multiplier']} = ${item['amount_usd_unrounded']}")
    print(f"应扣：${quote['amount_usd']}" + (f"（约 ¥{quote['cny']['amount']}）" if quote.get("cny") else ""))
    print("到控制台“调用记录”按请求编号找到这条，扣费应与上面一致。")


if __name__ == "__main__":
    main()
