import json
from statistics import mean
from pathlib import Path
from src.client.nebius_client import stream_completion
from config.settings import TARGET_MODEL, MAX_TOKENS, NUM_REQUESTS

PROMPTS = [
    "Write a Python function that merges two sorted lists.",
    "Explain why speculative decoding speeds up inference.",
    "Implement binary search iteratively and explain edge cases.",
]

RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)


def measure_one(prompt: str, use_self_hosted: bool = False):
    tokens = []
    char_count = 0
    ttft = None
    for evt in stream_completion(TARGET_MODEL, prompt, MAX_TOKENS,
                                 use_self_hosted=use_self_hosted):
        ttft = evt["ttft"]
        tokens.append(evt["t"])
        char_count += len(evt["token"])
    if len(tokens) < 2:
        return None
    decode_time = tokens[-1] - tokens[0]
    approx_tokens = char_count / 4.0     # rough chars-to-tokens
    tps = (approx_tokens - 1) / decode_time if decode_time > 0 else 0.0
    return {"ttft_s": ttft, "tps": tps, "n_tokens": int(approx_tokens)}

if __name__ == "__main__":
    print("Running baseline against managed Nebius endpoint…")
    results = []
    for i in range(NUM_REQUESTS):
        for p in PROMPTS:
            r = measure_one(p, use_self_hosted=False)
            if r:
                results.append(r)
                print(f"  req {len(results):02d}: "
                      f"TTFT={r['ttft_s']:.3f}s  TPS={r['tps']:.1f}  "
                      f"tokens={r['n_tokens']}")

    summary = {
        "mode": "baseline",
        "n": len(results),
        "ttft_mean_s": mean(r["ttft_s"] for r in results),
        "tps_mean": mean(r["tps"] for r in results),
    }
    print("\n=== Baseline summary ===")
    print(f"  N requests   : {summary['n']}")
    print(f"  TTFT (mean)  : {summary['ttft_mean_s']:.3f} s")
    print(f"  TPS  (mean)  : {summary['tps_mean']:.2f} tok/s")

    (RESULTS_DIR / "baseline.json").write_text(json.dumps(summary, indent=2))
    print(f"\nSaved to {RESULTS_DIR / 'baseline.json'}")