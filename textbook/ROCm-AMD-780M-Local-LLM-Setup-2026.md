# HOT
# ROCm AMD 780M Local LLM Setup 2026 — [DEPLOYED]

## 📚 Sources
- [MindStudio: Run Local AI on AMD](https://www.mindstudio.ai/blog/run-local-ai-amd-rocm-lm-studio-ollama-comfyui) — June 2026
- [Local AI Master: 96 tok/s on RX 7900 XTX](https://localaimaster.com/blog/amd-rocm-local-llm-setup) — June 2026
- [ROCm vs CUDA 2026](https://www.kunalganglani.com/blog/rocm-consumer-gpu-cuda-alternative-2026) — July 2026
- [johnsonfarmsus/ollama-rocm-gfx1103-ubuntu](https://github.com/johnsonfarmsus/ollama-rocm-gfx1103-ubuntu) — Native ROCm for 780M
- [likelovewant/ollama-for-amd](https://github.com/likelovewant/ollama-for-amd) — Wiki with gfx1103 guide
- [ataary: Ubuntu + Ollama ROCm on 780M](https://ataary.com/ubuntu-linux-with-ollama-rocm-on-amd-ryzen-780m-igpu/) — May 2026

## 🎯 Hardware: AMD Radeon 780M (gfx1103 / RDNA3)
- Integrated GPU in Ryzen 7040/8040/Phoenix series
- ~16 GiB usable memory (UMA + GTT shared)
- ROCm support: **improving but still inconsistent** on iGPU

## 🛠️ Working Setup Paths (2026)

### Path 1: Ollama with Native ROCm (Recommended for 780M)
```bash
# johnsonfarmsus one-command setup
curl -fsSL https://raw.githubusercontent.com/johnsonfarmsus/ollama-rocm-gfx1103-ubuntu/main/install.sh | bash
```
- Builds ollama-for-amd from source
- Applies 3 ml/device.go patches
- Installs Fedora 43's prebuilt gfx1103 Tensile kernels into rocBLAS

### Path 2: Ollama-for-AMD Installer (Easier)
```bash
# ByronLeeeee's installer - click to update/replace libs
# See: https://github.com/likelovewant/ollama-for-amd/wiki
```

### Path 3: llama.cpp with Vulkan (Fallback)
```bash
# If ROCm fails, Vulkan works on 780M
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build -DGGML_VULKAN=ON -DGGML_CUDA=OFF
cmake --build build --config Release
```

### Path 4: PyTorch ROCm (For Training/Fine-tuning)
```bash
# ROCm 7.x PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.3
# Or ROCm 7.2+ for newer support
```

## ⚠️ Known Issues & Workarounds
| Issue | Workaround |
|-------|------------|
| ROCm inconsistent on iGPU | Try Vulkan backend first |
| gfx1103 kernels missing | Use Fedora 43 Tensile kernels (johnsonfarmsus) |
| Ollama ROCm not detecting GPU | Set `HSA_OVERRIDE_GFX_VERSION=11.0.3` |
| OOM on 780M shared memory | Use smaller quant (Q4_K_M, Q3_K_L), limit context |

## 📊 Performance Expectations (780M iGPU)
| Model | Quant | Tok/s (est) | Notes |
|-------|-------|-------------|-------|
| Qwen3-8B | Q4_K_M | ~15-25 | Good balance |
| DeepSeek-Coder-6.7B | Q4_K_M | ~20-30 | Code optimized |
| Nemotron-3.5 | Q4_K_M | ~10-15 | Larger model |
| Llama-3.2-3B | Q4_K_M | ~30-45 | Fast, small |

## 🔗 Living Code Integration
- **GodModeCoder**: Ollama ROCm for agent loops (qwen3-8b-64k, deepseek-coder)
- **SuperGuard**: vLLM ROCm for YOLO + LLM inference pipeline
- **Elemental Life**: llama.cpp Vulkan for game AI
- **ParanoidX**: Local only — Ollama/llama.cpp

## 🔗 Related in Textbook
- [LLM Inference Optimization 2026](LLM-Inference-Optimization-2026.md) — 🔴 [NEW]
- [Ollama AMD GPU Deployment](Ollama-AMD-GPU-Deployment.md) — 🟢
- [ROCm PyTorch Audio Stack](ROCm-PyTorch-Audio-Stack.md) — 🟢

---
*Added: 2026-08-17 | Status: 🔴 NEW | Source: GitHub repos, community guides, benchmarks*