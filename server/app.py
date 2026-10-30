import asyncio
import time
import json
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.client.nebius_client import non_stream_completion

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class PromptRequest(BaseModel):
    prompt: str

@app.post("/swarm")
async def generate_swarm(req: PromptRequest):
    try:
        start_time = time.perf_counter()
        
        model_agent_1 = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
        model_agent_2 = "Qwen/Qwen3-30B-A3B-Instruct-2507"
        model_verifier = "nvidia/Nemotron-3-Ultra-550b-a55b"

        prompt_1 = f"Write ONLY the code/technical implementation for this request. No explanations. Request: {req.prompt}"
        prompt_2 = f"Write ONLY the logical explanation, edge cases, and theory for this request. No code. Request: {req.prompt}"

        task1 = asyncio.to_thread(non_stream_completion, model_agent_1, prompt_1, 300)
        task2 = asyncio.to_thread(non_stream_completion, model_agent_2, prompt_2, 300)

        draft1_res, draft2_res = await asyncio.gather(task1, task2)
        
        draft1_text = draft1_res["text"]
        draft2_text = draft2_res["text"]

        verifier_prompt = f"""
        You are the Lead Architect. Synthesize the following two drafts into one perfect, final answer.
        Merge the code and the explanation beautifully.
        
        User Request: {req.prompt}
        
        Draft 1 (Code):
        {draft1_text}
        
        Draft 2 (Logic):
        {draft2_text}
        
        Final Answer:
        """
        
        final_res = non_stream_completion(model_verifier, verifier_prompt, 400)
        final_text = final_res["text"]
        
        total_time = time.perf_counter() - start_time

        return {
            "draft_1": draft1_text,
            "draft_2": draft2_text,
            "final_answer": final_text,
            "time_taken": round(total_time, 2),
            "models_used": [model_agent_1, model_agent_2, model_verifier]
        }
        
    except Exception as e:
        print(f"SWARM ERROR: {str(e)}")
        return {
            "draft_1": "Draft 1 Failed",
            "draft_2": "Draft 2 Failed",
            "final_answer": f"Backend Error: {str(e)}",
            "time_taken": 0,
            "models_used": []
        }

app.mount("/dashboard", StaticFiles(directory="dashboard", html=True), name="dashboard")
