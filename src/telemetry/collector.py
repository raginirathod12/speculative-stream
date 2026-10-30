import json
import time
from pathlib import Path

LOG_FILE = Path("telemetry.jsonl")

def record_telemetry(original_tokens, compressed_tokens, ttft, tps, cache_hit, agent):
    tokens_saved = original_tokens - compressed_tokens
    cost_saved = (tokens_saved / 1_000_000) * 0.20

    event = {
        "timestamp": time.time(),
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "tokens_saved": tokens_saved,
        "cost_saved_usd": cost_saved,
        "ttft_s": ttft,
        "tps": tps,
        "cache_hit": cache_hit,
        "agent": agent
    }

    with LOG_FILE.open("a") as f:
        f.write(json.dumps(event) + "\n")