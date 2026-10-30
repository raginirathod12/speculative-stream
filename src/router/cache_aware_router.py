import hashlib
from collections import deque

class CacheAwareRouter:
    def __init__(self, max_cache_size=50):
        self.cache_history = deque(maxlen=max_cache_size)

    def get_prefix_hash(self, prompt: str) -> str:
        prefix = prompt[:500]
        return hashlib.sha256(prefix.encode()).hexdigest()

    def route(self, prompt: str) -> dict:
        p_hash = self.get_prefix_hash(prompt)
        is_cache_hit = p_hash in self.cache_history
        self.cache_history.append(p_hash)
        
        if "code" in prompt.lower() or "python" in prompt.lower():
            agent = "Code-Specialist-Draft"
        else:
            agent = "Logic-Specialist-Draft"

        return {
            "agent": agent,
            "cache_hit": is_cache_hit,
            "hash": p_hash[:8]
        }