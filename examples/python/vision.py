"""看图（图片输入）：把本地生成的一张小图片发给支持视觉的模型。

不依赖外部图片地址：程序用标准库现场生成一张 64×64 的 PNG（左红右蓝），再以 base64 data URL 发送。
运行会产生少量费用。需要 API_302API_KEY 和 MODEL_ID（选支持看图的模型，例如 Claude 或 GPT 系列）。
"""
import base64
import os
import struct
import zlib

from openai import OpenAI


def make_png(width=64, height=64) -> bytes:
    rows = b"".join(b"\x00" + b"".join(b"\xe0\x30\x30" if x < width // 2 else b"\x30\x50\xe0" for x in range(width))
                    for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def main():
    key, model = os.environ.get("API_302API_KEY", ""), os.environ.get("MODEL_ID", "")
    if not key.strip() or not model.strip():
        raise SystemExit("先设置 API_302API_KEY 和 MODEL_ID")
    client = OpenAI(api_key=key, base_url=os.getenv("API_302API_BASE_URL", "https://api.302api.com/v1"), max_retries=0)
    data_url = "data:image/png;base64," + base64.b64encode(make_png()).decode()
    result = client.chat.completions.create(
        model=model,
        max_tokens=100,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": "这张图片左右两半分别是什么颜色？用一句话回答。"},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]}],
    )
    print(result.choices[0].message.content)
    print(f"用量：输入 {result.usage.prompt_tokens}（含图片）/ 输出 {result.usage.completion_tokens} Token")


if __name__ == "__main__":
    main()
