"""Server-side Chat Completions example. Running it can incur usage charges."""
import os
from openai import OpenAI


def main():
    key = os.environ["API_302API_KEY"]
    model = os.environ["MODEL_ID"]
    if not key.strip() or not model.strip():
        raise SystemExit("Set API_302API_KEY and MODEL_ID first.")
    client = OpenAI(
        api_key=key,
        base_url=os.getenv("API_302API_BASE_URL", "https://api.302api.com/v1"),
        max_retries=0,
    )
    result = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "请用一句话解释 API。"}],
    )
    print(result.choices[0].message.content or "")


if __name__ == "__main__":
    main()
