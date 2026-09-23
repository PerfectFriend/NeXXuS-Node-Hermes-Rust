# HOT
# LLM Inference Optimization 2026 — [DEPLOYED]

## 📚 Sources
- [vLLM vs SGLang vs TGI Benchmark 2026](https://llm-academy.dev/inference/vllm-vs-sglang/) — H100 benchmarks
- [vLLM vs SGLang vs TensorRT-LLM vs Ollama](https://aicraftguide.com/article/vllm-sglang-tensorrt-llm-ollama-self-hosted-2026) — Decision matrix
- [Inference Radar Newsletter](https://www.runanywhere.ai/newsletter/2026-W20) — llama.cpp MTP mainstream
- [vLLM 0.24.0+](https://github.com/vllm-project/vllm) — MTP speculative decoding, tool calls fix

## 🎯 Engine Comparison 2026

| Engine | Best For | Key Features 2026 |
|--------|----------|-------------------|
| **vLLM** | High-throughput serving | PagedAttention, continuous batching, n-gram/EAGLE/DFlash speculative decoding, chunked prefill |
| **SGLang** | Structured generation, prefix cache | Radix attention, structured output, prefix-cache reuse |
| **TGI** | HuggingFace integration, ease | Optimized for HF models, good defaults |
| **TensorRT-LLM** | NVIDIA GPU max perf | FP8, tensor parallelism, in-flight batching |
| **llama.cpp / Ollama** | Local, CPU/AMD/Apple Silicon | MTP speculative decoding, GGUF, wide hardware support |
| **MAX (Modular)** | Production, multi-hardware | Graph compiler, Mojo kernels |

## 🚀 Speculative Decoding 2026 Status
- **MTP (Multi-Token Prediction)** — Now mainstream: llama.cpp, SGLang, vLLM, Ollama, MLX, TensorRT-Edge-LLM
- **vLLM**: n-gram, suffix, EAGLE, DFlash — v0.18.0+ supports chunked prefill coexistence
- **llama.cpp**: MTP works better than vLLM per community reports
- **Draft-free speculative decoding** — Emerging (no separate draft model needed)

## 📊 Decision Matrix (Self-Hosted)
| Factor | Choose |
|--------|--------|
| AMD GPU (780M) | Ollama ROCm / llama.cpp Vulkan / vLLM ROCm |
| NVIDIA GPU max perf | TensorRT-LLM / vLLM |
| Structured output | SGLang |
| Ease + HF models | TGI / Ollama |
| Local dev / privacy | Ollama / llama.cpp |

## 🔧 Living Code Application
- **SuperGuard**: vLLM/SGLang on AMD 780M via ROCm for YOLO + LLM inference
- **Elemental Life**: llama.cpp GGUF for local game AI
- **GodModeCoder**: Ollama local models (qwen3, deepseek-coder, nemotron3.5) for agent loops
- **ParanoidX**: Local inference only (sovereign requirement)

## 🔗 Related in Textbook
- [ROCm PyTorch Audio Stack](ROCm-PyTorch-Audio-Stack.md) — 🟢
- [Ollama AMD GPU Deployment](Ollama-AMD-GPU-Deployment.md) — 🟢
- [vLLM Inference Optimization](vLLM-Inference-Optimization.md) — 🔴 [NEW]

---
*Added: 2026-08-17 | Status: 🟢 DEPLOYED | Source: Benchmarks, vLLM releases, community reports*"