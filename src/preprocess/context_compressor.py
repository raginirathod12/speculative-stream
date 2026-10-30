import re
import tiktoken

enc = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(enc.encode(text))

def compress_context(prompt: str) -> tuple[str, int, int]:
    original_tokens = count_tokens(prompt)
    cleaned = re.sub(r'\s+', ' ', prompt).strip()
    
    fillers = ["please", "kindly", "I want you to", "Can you", "Could you"]
    for filler in fillers:
        cleaned = re.sub(rf'(?i)\b{filler}\b', '', cleaned)
    
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    new_tokens = count_tokens(cleaned)
    
    return cleaned, original_tokens, new_tokens