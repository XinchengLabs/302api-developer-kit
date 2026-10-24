"""Use an enabled Anthropic-native model; not every model accepts this protocol."""
import os
from anthropic import Anthropic


def main():
    key = os.environ["API_302API_KEY"]
    model = os.environ["ANTHROPIC_MODEL_ID"]
    if not key.strip() or not model.strip():
        raise SystemExit("Set API_302API_KEY and ANTHROPIC_MODEL_ID first.")
    client = Anthropic(
        api_key=key,
        base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.302api.com"),
        max_retries=0,
    )
    result = client.messages.create(
        model=model,
        max_tokens=256,
        messages=[{"role": "user", "content": "请用一句话解释 API。"}],
    )
    for block in result.content:
        if block.type == "text":
            print(block.text)


if __name__ == "__main__":
    main()
