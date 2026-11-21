"""工具调用（function calling）完整往返：模型请求调用工具 → 本地执行 → 把结果交回模型生成最终回答。

运行会产生少量费用。需要 API_302API_KEY 和 MODEL_ID（选支持工具调用的对话模型，例如 Claude、GPT 系列）。
"""
import json
import os

from openai import OpenAI

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_exchange_rate",
        "description": "查询两种货币之间的汇率",
        "parameters": {
            "type": "object",
            "properties": {
                "base": {"type": "string", "description": "原币种代码，例如 USD"},
                "quote": {"type": "string", "description": "目标币种代码，例如 CNY"},
            },
            "required": ["base", "quote"],
        },
    },
}]


def get_exchange_rate(base: str, quote: str) -> dict:
    # 演示用的固定数据；真实项目在这里调用你自己的服务
    table = {("USD", "CNY"): 7.1, ("EUR", "CNY"): 7.7}
    return {"base": base, "quote": quote, "rate": table.get((base.upper(), quote.upper()))}


def main():
    key, model = os.environ.get("API_302API_KEY", ""), os.environ.get("MODEL_ID", "")
    if not key.strip() or not model.strip():
        raise SystemExit("先设置 API_302API_KEY 和 MODEL_ID")
    client = OpenAI(api_key=key, base_url=os.getenv("API_302API_BASE_URL", "https://api.302api.com/v1"), max_retries=0)
    messages = [{"role": "user", "content": "100 美元是多少人民币？请先查汇率再计算。"}]

    first = client.chat.completions.create(model=model, messages=messages, tools=TOOLS)
    reply = first.choices[0].message
    if not reply.tool_calls:
        print("模型没有调用工具，直接回答：", reply.content)
        return
    messages.append(reply.model_dump(exclude_none=True))
    for call in reply.tool_calls:
        args = json.loads(call.function.arguments or "{}")
        result = get_exchange_rate(**args)
        print(f"模型调用 {call.function.name}({args}) → {result}")
        messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, ensure_ascii=False)})

    final = client.chat.completions.create(model=model, messages=messages, tools=TOOLS)
    print("最终回答：", final.choices[0].message.content)
    for name, resp in (("第一次", first), ("第二次", final)):
        print(f"{name}请求用量：输入 {resp.usage.prompt_tokens} / 输出 {resp.usage.completion_tokens} Token")


if __name__ == "__main__":
    main()
