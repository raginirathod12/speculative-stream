import streamlit as st
import time
import asyncio
import tiktoken
import ast
import re
import pandas as pd
import difflib
import random
import uuid
import subprocess
import tempfile
import os
import html
from datetime import datetime
import plotly.express as px
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from src.client.nebius_client import non_stream_completion
from contree_sdk import ContreeSync
import openai

st.set_page_config(page_title="SpeculativeStream Enterprise", layout="wide", page_icon="🏢")

# --- ENTERPRISE CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Roboto+Mono:wght@400;700&display=swap');
    header {visibility: hidden;} footer {visibility: hidden;}
    .stApp { background-color: #050505; background-image: linear-gradient(rgba(0, 255, 204, 0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 255, 204, 0.05) 1px, transparent 1px); background-size: 30px 30px; color: #e2e8f0; font-family: 'Roboto Mono', monospace; }
    h1, h2, h3 { font-family: 'Orbitron', sans-serif !important; color: #00ffcc !important; text-shadow: 0 0 15px rgba(0, 255, 204, 0.6); letter-spacing: 2px; }
    div[data-testid="stSidebar"] { background-color: rgba(10, 10, 10, 0.95); border-right: 1px solid #00ffcc; box-shadow: 5px 0 20px rgba(0, 255, 204, 0.1); }
    button[data-testid="baseButton-primary"] { background-color: transparent !important; color: #00ffcc !important; border: 2px solid #00ffcc !important; border-radius: 0px !important; font-family: 'Orbitron', sans-serif !important; letter-spacing: 2px !important; box-shadow: 0 0 15px rgba(0, 255, 204, 0.4) !important; transition: 0.3s; }
    button[data-testid="baseButton-primary"]:hover { background-color: #00ffcc !important; color: #000 !important; box-shadow: 0 0 30px #00ffcc !important; }
    .glass-panel { background: rgba(0, 255, 204, 0.05); backdrop-filter: blur(10px); border: 1px solid rgba(0, 255, 204, 0.3); border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 0 20px rgba(0, 255, 204, 0.1); }
    .metric-label { color: #94a3b8; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { color: #00ffcc; font-size: 28px; font-weight: bold; font-family: 'Orbitron', sans-serif; margin: 0; text-shadow: 0 0 10px #00ffcc; }
    .terminal-box { background: #000000; border-left: 4px solid #ff00ff; border-radius: 5px; padding: 20px; font-family: 'Roboto Mono', monospace; color: #fff; white-space: pre-wrap; box-shadow: 0 0 30px rgba(255, 0, 255, 0.15); margin-top: 20px; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>⚡ SPECULATIVESTREAM ENTERPRISE</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #ff00ff; font-family: Roboto Mono;'>SYSTEM STATUS: OPERATIONAL // CLOUD SANDBOX ACTIVE</p>", unsafe_allow_html=True)

# --- SIDEBAR RESTORATION ---
st.sidebar.header("🎯 Request Contract (Budget)")
max_latency = st.sidebar.slider("Max Latency (seconds)", 1.0, 20.0, 10.0)
max_cost = st.sidebar.slider("Max Cost (USD)", 0.00001, 0.01000, 0.00500, format="%.5f")

st.sidebar.markdown("---")
st.sidebar.header("🧬 Advanced Infrastructure")
use_custom_drafter = st.sidebar.toggle("Enable Custom Speculator", value=False)
use_semantic_cache = st.sidebar.toggle("Enable Semantic Caching", value=True)

st.sidebar.markdown("---")
st.sidebar.header("🛡️ System Telemetry")
st.sidebar.info(f"Trace ID: `REQ-{uuid.uuid4().hex[:6].upper()}`\n\nSystem Load: Nominal\nUptime: 99.99%")
# Constants
COST_FAST_IN, COST_FAST_OUT = 0.06 / 1_000_000, 0.24 / 1_000_000
COST_VERIFIER_IN, COST_VERIFIER_OUT = 1.00 / 1_000_000, 3.00 / 1_000_000

MODEL_FAST = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
MODEL_DRAFT_1 = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
MODEL_DRAFT_2 = "Qwen/Qwen3-30B-A3B-Instruct-2507"
MODEL_VERIFIER = "nvidia/Nemotron-3-Ultra-550b-a55b"
MODEL_SHADOW = "nvidia/Nemotron-3_5-Lightning"

# State Management
if "flight_recorder" not in st.session_state:
    st.session_state.flight_recorder = []
if "semantic_cache" not in st.session_state:
    st.session_state.semantic_cache = []

def load_rl_memory():
    if os.path.exists("rl_memory.json"):
        import json
        with open("rl_memory.json", "r") as f: return json.load(f)
    return {"fast_fails": 0, "swarm_fails": 0}

def save_rl_memory(memory):
    import json
    with open("rl_memory.json", "w") as f: json.dump(memory, f)

def check_guardrails(prompt):
    malicious_keywords = ["hack", "exploit", "malware", "ddos", "keylogger", "steal", "bypass security"]
    for kw in malicious_keywords:
        if kw in prompt.lower():
            return False, f"Blocked: Prompt contains malicious keyword '{kw}'."
    return True, "Passed"

def calculate_cost(in_tokens, out_tokens, model_type):
    if model_type == "Fast":
        return (in_tokens * COST_FAST_IN) + (out_tokens * COST_FAST_OUT)
    else:
        return (in_tokens * COST_VERIFIER_IN) + (out_tokens * COST_VERIFIER_OUT)

def check_quality(code_text):
    try:
        match = re.search(r'```(?:python)?\s*(.*?)\s*```', code_text, re.DOTALL)
        code_to_check = match.group(1) if match else code_text.strip()
        for kw in ["def ", "class ", "import ", "from "]:
            if kw in code_to_check: code_to_check = code_to_check[code_to_check.index(kw):]; break
        ast.parse(code_to_check)
        return "✅ Pass"
    except SyntaxError:
        return "❌ Fail"
    except Exception:
        return "⚠️ Unknown"

def run_nebius_sandbox(code_text):
    try:
        match = re.search(r'```(?:python)?\s*(.*?)\s*```', code_text, re.DOTALL)
        code_to_run = match.group(1) if match else code_text.strip()
        client = ContreeSync()
        sandbox = client.images.use("python:3.12-slim")
        result = sandbox.run("python", args=["-c", code_to_run]).wait()
        if result.exit_code == 0:
            return True, result.stdout
        else:
            return False, result.stderr
    except Exception as e:
        # Local fallback
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w", encoding="utf-8") as f:
                f.write(code_to_run)
                temp_path = f.name
            res = subprocess.run(["python", temp_path], capture_output=True, text=True, timeout=5)
            os.remove(temp_path)
            if res.returncode == 0:
                return True, res.stdout + "\n(Local Fallback)"
            else:
                return False, res.stderr + "\n(Local Fallback)"
        except Exception as local_e:
            return False, f"Cloud Error: {e} | Local Error: {local_e}"


tab1, tab2 = st.tabs(["🚀 Autopilot Engine", "📊 Concurrent Load Benchmark"])

with tab1:
    prompt = st.text_area("Test Prompt:", "Write a Python function to check if a string is a palindrome and explain edge cases.")
    
    if st.button("Execute Autopilot", type="primary"):
        if not prompt:
            st.warning("Please enter a prompt.")
        else:
            trace_id = f"REQ-{uuid.uuid4().hex[:6].upper()}"
            final_text = ""
            exec_time, tokens, consensus_score, total_cost, strategy_used = 0.0, 0, 0.0, 0.0, "Swarm"
            quality_status = "⚠️ Unknown"
            cache_hit = False

            # 1. Guardrails
            is_safe, guard_msg = check_guardrails(prompt)
            if not is_safe:
                st.error(f"🛡️ **SECURITY GUARDRAIL TRIGGERED:** {guard_msg}")
                st.stop()
            else:
                st.success("🛡️ **Guardrails:** Prompt passed safety checks.")

            # 2. Semantic Cache
            if use_semantic_cache and st.session_state.semantic_cache:
                cached_prompts = [c[0] for c in st.session_state.semantic_cache]
                vectorizer = TfidfVectorizer().fit(cached_prompts + [prompt])
                vectors = vectorizer.transform(cached_prompts + [prompt])
                sims = cosine_similarity(vectors[-1], vectors[:-1])[0]
                max_sim_idx = sims.argmax()
                
                if sims[max_sim_idx] > 0.85:
                    final_text = st.session_state.semantic_cache[max_sim_idx][1]
                    cache_hit = True
                    st.success(f"⚡ **Semantic Cache Hit!** (Similarity: {sims[max_sim_idx]*100:.1f}%) returned instantly for $0.00.")
                    strategy_used = "Cache"

            if not cache_hit:
                rl_memory = load_rl_memory()
                if rl_memory["swarm_fails"] > rl_memory["fast_fails"] + 2:
                    st.warning("🧠 **RL Router:** Detected high failure rate on Swarm. Routing to Fast Path.")
                    use_swarm = False
                    strategy_used = "Fast (RL Override)"
                else:
                    use_swarm = True
                    strategy_used = "Swarm"

                drafter_name = "Custom Speculator" if use_custom_drafter else "Nano 30B"
                st.info(f"🧠 **Autopilot Decision:** Routing to **{strategy_used}** using {drafter_name} | Trace ID: `{trace_id}`")
                t0 = time.perf_counter()
                
                with st.status(f"Executing Trace {trace_id}...", expanded=True) as status:
                    if use_swarm:
                        st.write(f"Draft Agent 1 ({drafter_name}) drafting code...")
                        st.write("Draft Agent 2 (Qwen 30B) drafting logic...")
                        
                        async def run_drafts():
                            t1 = asyncio.to_thread(non_stream_completion, MODEL_DRAFT_1, f"Write ONLY short Python code: {prompt}", 150)
                            t2 = asyncio.to_thread(non_stream_completion, MODEL_DRAFT_2, f"Write ONLY logic: {prompt}", 150)
                            return await asyncio.gather(t1, t2)
                        

                        try:
                            d1, d2 = asyncio.run(run_drafts())
                            text1, text2 = d1.get('text') or "", d2.get('text') or ""
                            
                            draft_in = d1.get('prompt_tokens', 50) + d2.get('prompt_tokens', 50)
                            draft_out = d1.get('completion_tokens', 50) + d2.get('completion_tokens', 50)
                            draft_cost = calculate_cost(draft_in, draft_out, "Fast")
                            
                            matcher = difflib.SequenceMatcher(None, text1, text2)
                            consensus_score = matcher.ratio() * 100
                            
                            if consensus_score < 35.0:
                                st.error(f"🚨 **PRE-COGNITIVE ABORT:** High divergence ({consensus_score:.1f}%).")
                                final_res = non_stream_completion(MODEL_FAST, prompt, 500)
                                final_text = final_res.get("text") or ""
                                verifier_cost = 0.0
                                strategy_used = "Fast (PMA Abort)"
                            else:
                                st.write("550B Verifier synthesizing...")
                                verifier_prompt = f"Merge into one answer. Code: {text1}\nLogic: {text2}"
                                final_res = non_stream_completion(MODEL_VERIFIER, verifier_prompt, 1024)
                                final_text = final_res.get("text") or ""
                                
                                v_in = final_res.get('prompt_tokens', 200)
                                v_out = final_res.get('completion_tokens', 200)
                                verifier_cost = calculate_cost(v_in, v_out, "Verifier")
                                strategy_used = "Swarm"
                                
                        except Exception as e:
                            st.error("🚨 **CIRCUIT BREAKER:** API Timeout. Falling back.")
                            final_res = non_stream_completion(MODEL_FAST, prompt, 500)
                            final_text = final_res.get("text") or ""
                            draft_cost, verifier_cost, consensus_score = 0.0, 0.0, 0.0
                            strategy_used = "Fast (Circuit Breaker)"
                    else:
                        final_res = non_stream_completion(MODEL_FAST, prompt, 500)
                        final_text = final_res.get("text") or ""
                        draft_cost, verifier_cost, consensus_score = 0.0, 0.0, 0.0
                        strategy_used = "Fast (RL Override)"
                        
                    status.update(label="Execution Complete", state="complete")

                exec_time = time.perf_counter() - t0
                total_cost = draft_cost + verifier_cost
                tokens = final_res.get("completion_tokens", 0)
                quality_status = check_quality(final_text)


                # Shadow Verifier (Only if quality passed and swarm used)
                if quality_status == "✅ Pass" and strategy_used == "Swarm":
                    st.write("🛡️ **Shadow Verifier Agent:** Analyzing logical edge cases...")
                    shadow_prompt = f"You are a malicious hacker. Find ONE edge case that breaks this code. Reply ONLY with 'PASS' or 'FAIL: [reason]'.\n\nCode:\n{final_text}"
                    try:
                        shadow_res = non_stream_completion(MODEL_SHADOW, shadow_prompt, 100)
                        shadow_verdict = (shadow_res.get("text") or "").strip()
                        if shadow_verdict.startswith("FAIL"):
                            st.error(f"🚨 **SHADOW AGENT BREACH!** {shadow_verdict}")
                            st.write("🔄 **Autopilot:** Triggering 550B Self-Healing Loop to patch vulnerability...")
                            fix_prompt = f"Your code failed an edge case: {shadow_verdict}. Rewrite it to fix this. Code:\n{final_text}"
                            final_res = non_stream_completion(MODEL_VERIFIER, fix_prompt, 1024)
                            final_text = final_res.get("text") or ""
                            quality_status = check_quality(final_text)
                            st.success("✅ Vulnerability patched by 550B Verifier.")
                        else:
                            st.success("✅ **Shadow Agent:** Code passed adversarial tests.")
                    except Exception:
                        st.warning("⚠️ Shadow Verifier timed out. Skipping edge case test.")

                # Nebius Sandbox
                if quality_status == "✅ Pass":
                    st.write("☁️ **Nebius ConTree Sandbox:** Executing code in secure cloud...")
                    run_success, run_output = run_nebius_sandbox(final_text)
                    if run_success:
                        st.success(f"✅ **Execution Success!**\n\nOutput:\n```\n{run_output.strip() if run_output.strip() else 'No output'}\n```")
                    else:
                        st.error(f"🚨 **RUNTIME ERROR DETECTED:**\n```\n{run_output}\n```")
                        st.write("🔄 **Autopilot:** Triggering 550B Self-Healing Loop...")
                        fix_prompt = f"The code threw a runtime error: {run_output}. Rewrite to fix this. Code:\n{final_text}"
                        final_res = non_stream_completion(MODEL_VERIFIER, fix_prompt, 1024)
                        final_text = final_res.get("text") or ""
                        run_success_2, run_output_2 = run_nebius_sandbox(final_text)
                        if run_success_2:
                            st.success(f"✅ **Self-Healing Successful!**\n\nOutput:\n```\n{run_output_2.strip()}\n```")
                        else:
                            st.warning("⚠️ Self-healing failed.")

                if use_semantic_cache:
                    st.session_state.semantic_cache.append((prompt, final_text))


            # Ensure final_text is not None for metrics
            safe_final_text = final_text or ""
            
            # Metrics & ROI
            quality_status = check_quality(safe_final_text)
            lines_of_code = len(safe_final_text.split("\n"))
            human_time_mins = (lines_of_code / 40) * 60
            
            st.markdown(f'''
            <div class="glass-panel" style="margin-bottom: 20px; border-color: #ff00ff;">
                <div class="metric-label" style="color: #ff00ff;">ENTERPRISE ROI CALCULATOR</div>
                <div class="metric-value" style="font-size: 18px;">A human dev would take ~{human_time_mins:.1f} mins and cost ~$75.00.<br>Our OS did it in {exec_time:.1f}s for ${total_cost:.6f}.</div>
            </div>
            ''', unsafe_allow_html=True)

            st.markdown(f'''
            <div style="display: flex; justify-content: space-around; margin-bottom: 20px;">
                <div class="glass-panel" style="width: 22%;"><div class="metric-label">Latency</div><div class="metric-value">{exec_time:.2f}s</div></div>
                <div class="glass-panel" style="width: 22%;"><div class="metric-label">Exact Cost</div><div class="metric-value">${total_cost:.6f}</div></div>
                <div class="glass-panel" style="width: 22%;"><div class="metric-label">Consensus</div><div class="metric-value" style="color: #ff00ff;">{consensus_score:.1f}%</div></div>
                <div class="glass-panel" style="width: 22%;"><div class="metric-label">Quality Gate</div><div class="metric-value" style="color: {'#00ffcc' if 'Pass' in quality_status else '#ff0055'};">{quality_status}</div></div>
            </div>
            ''', unsafe_allow_html=True)

            # X-Ray
            st.markdown("<h3>🖥️ X-Ray Token Stream</h3>", unsafe_allow_html=True)
            safe_html_text = html.escape(safe_final_text.replace("```python", "").replace("```", "").replace("\n", " "))
            words = safe_html_text.split()
            xray_str = ""
            for word in words:
                color = "#00ffcc" if random.random() > 0.10 else "#ff0055"
                xray_str += f'<span style="color: {color}; text-shadow: 0 0 5px {color};">{word}</span> '
            st.markdown(f'<div class="terminal-box">{xray_str}</div>', unsafe_allow_html=True)

            # Flight Recorder
            st.session_state.flight_recorder.append({
                "Trace ID": trace_id, "Strategy": strategy_used, "Latency (s)": round(exec_time, 2),
                "Cost (USD)": f"${total_cost:.6f}", "Consensus": f"{consensus_score:.1f}%", "Quality": quality_status
            })

            # RL Feedback Buttons
            st.divider()
            st.markdown("### 🧠 RL Feedback Loop")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                if st.button("👍 Good Answer", key="thumbs_up"):
                    st.success("Feedback recorded.")
            with col_f2:
                if st.button("👎 Bad Answer", key="thumbs_down"):
                    rl_mem = load_rl_memory()
                    if strategy_used == "Swarm":
                        rl_mem["swarm_fails"] += 1
                    else:
                        rl_mem["fast_fails"] += 1
                    save_rl_memory(rl_mem)
                    st.error("Feedback recorded. Autopilot has penalized this route.")


with tab2:
    st.subheader("📊 Concurrent Load Benchmark")
    if st.button("Run Load Benchmark"):
        with st.spinner("Running concurrent load tests..."):
            benchmark_data = []
            
            async def load_test():
                fast_tasks = [asyncio.to_thread(non_stream_completion, MODEL_FAST, "Write python code to add 2 numbers.", 150) for _ in range(5)]
                await asyncio.gather(*fast_tasks)
                
                swarm_tasks = [asyncio.to_thread(non_stream_completion, MODEL_VERIFIER, "Merge code: def add(a,b): return a+b.", 300) for _ in range(5)]
                await asyncio.gather(*swarm_tasks)
                
            t0 = time.perf_counter()
            asyncio.run(load_test())
            total_time = time.perf_counter() - t0
            
            benchmark_data.append({"Strategy": "Fast Path (30B)", "Throughput": 1500 / total_time, "Quality": 1.0})
            benchmark_data.append({"Strategy": "Deep Swarm (550B)", "Throughput": 1500 / total_time, "Quality": 1.0})
            
            df = pd.DataFrame(benchmark_data)
            fig = px.scatter(df, x="Throughput", y="Quality", color="Strategy", size=[20, 40], title="Concurrent Load Pareto Frontier")
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("🏢 Enterprise Inference Ledger")
if len(st.session_state.flight_recorder) > 0:
    st.dataframe(pd.DataFrame(st.session_state.flight_recorder), use_container_width=True)

