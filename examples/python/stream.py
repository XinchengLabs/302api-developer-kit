"""Server-side SSE example. A text chunk does not establish final billed usage."""
import os
from openai import OpenAI


def main():
    key, model = os.environ["API_302API_KEY"], os.environ["MODEL_ID"]
    if not key.strip() or not model.strip():
        raise SystemExit("Set API_302API_KEY and MODEL_ID first.")
    client = OpenAI(
        api_key=key,
        base_url=os.getenv("API_302API_BASE_URL", "https://api.302api.com/v1"),
        max_retries=0,
    )
    with client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "用三句话介绍流式输出。"}],
        stream=True,
        stream_options={"include_usage": True},
    ) as stream:
        for chunk in stream:
            if chunk.choices:
                print(chunk.choices[0].delta.content or "", end="", flush=True)
            if chunk.usage:
                print("\nReported usage:", chunk.usage.model_dump())
    print()


if __name__ == "__main__":
    main()
