"""用提示词生成一张 PNG，保存在当前目录。运行会产生一次生图调用费用。"""
import argparse
import base64
import binascii
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from openai import OpenAI


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="?", default="画一张等距视角的微缩书店插画，暖黄色灯光，薄荷绿背景。")
    args = parser.parse_args()
    if not args.prompt.strip():
        parser.error("请输入提示词")
    key = os.getenv("API_302API_KEY", "").strip()
    if not key:
        parser.exit(1, "请先设置环境变量 API_302API_KEY。\n")

    client = OpenAI(
        api_key=key,
        base_url=os.getenv("API_302API_BASE_URL", "https://api.302api.com/v1"),
        max_retries=0,
    )
    result = client.images.generate(
        model=os.getenv("IMAGE_MODEL_ID") or "gpt-image-2.6-flare",
        prompt=args.prompt,
        size="1024x1024",
        quality="low",
        output_format="png",
        n=1,
    )
    if not result.data or not result.data[0].b64_json:
        raise SystemExit("响应中缺少图片数据，请在控制台查看这次调用记录。")
    try:
        image = base64.b64decode(result.data[0].b64_json, validate=True)
    except (ValueError, binascii.Error):
        raise SystemExit("返回的图片数据无法解码，请在控制台查看这次调用记录。")
    if not image.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SystemExit("返回的图片格式与请求的 PNG 不符。")
    with NamedTemporaryFile(dir=Path.cwd(), prefix="302api-", suffix=".png", delete=False) as output:
        output.write(image)
    print(f"图片已保存到 {output.name}")


if __name__ == "__main__":
    main()
