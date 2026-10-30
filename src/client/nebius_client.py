import time
from openai import OpenAI
from config.settings import API_KEY, BASE_URL, SELF_HOSTED_BASE_URL

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

self_hosted_client = (
    OpenAI(api_key="local", base_url=SELF_HOSTED_BASE_URL)
    if SELF_HOSTED_BASE_URL else None
)


def stream_completion(model: str, prompt: str, max_tokens: int = 256,
                      use_self_hosted: bool = False):
    c = self_hosted_client if use_self_hosted else client
    if c is None:
        raise RuntimeError("SELF_HOSTED_BASE_URL not set in .env")

    start = time.perf_counter()
    first_token_time = None

    stream = c.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        stream=True,
    )

    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            now = time.perf_counter()
            if first_token_time is None:
                first_token_time = now
            yield {
                "token": chunk.choices[0].delta.content,
                "t": now,
                "ttft": first_token_time - start,
            }


def non_stream_completion(model: str, prompt: str, max_tokens: int = 256,
                           use_self_hosted: bool = False) -> dict:
    c = self_hosted_client if use_self_hosted else client
    if c is None:
        raise RuntimeError("SELF_HOSTED_BASE_URL not set in .env")

    start = time.perf_counter()
    resp = c.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    elapsed = time.perf_counter() - start
    usage = resp.usage
    return {
        "latency_s": elapsed,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "text": resp.choices[0].message.content,
    }