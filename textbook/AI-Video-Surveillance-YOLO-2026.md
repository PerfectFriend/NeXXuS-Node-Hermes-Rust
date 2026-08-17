# AI Video Surveillance with YOLO 2026 — [NEW]

## 📚 Sources
- [ForaSoft: YOLO & ByteTrack 2026](https://www.forasoft.com/blog/article/ai-video-surveillance-yolo-deepsort-guide) — July 16, 2026
- [SharpAI/DeepCamera](https://github.com/SharpAI/DeepCamera) — AI NVR, local VLM (Qwen, DeepSeek, SmolVLM, LLaVA, YOLO26)
- [PhazerTech/yolo-rtsp-security-cam](https://github.com/PhazerTech/yolo-rtsp-security-cam)
- [foschmitz/yolo-python-rtsp](https://github.com/foschmitz/yolo-python-rtsp)
- [YOLOv11 Defense Surveillance](https://doi.org/10.3390/computers15010062) — Jan 2026

## 🎯 YOLO 2026 Status
- **YOLO26** (Ultralytics, Jan 2026) — NMS-free by default, small-target-aware
- **YOLOv11** — Used in defense hybrid RTSP-WebRTC architectures
- **DeepCamera** — LLM-powered agentic security camera (watches, understands, remembers, guards)

## 🛠️ Production Stack Options

| Stack | Components | Best For |
|-------|------------|----------|
| **DeepCamera** | Qwen/DeepSeek/SmolVLM/LLaVA + YOLO26 + Telegram/Discord/Slack | Full agentic NVR |
| **Custom Python** | Ultralytics YOLO + OpenCV RTSP + ByteTrack | Lightweight, controllable |
| **Multi-Cam Panel** | YOLO + RTSP multicam dashboard | Monitoring multiple feeds |

## 🔧 SuperGuard Integration
- **Current**: YOLOv11n + ONNX Runtime DirectML on AMD 780M
- **Upgrade Path**: YOLO26 (NMS-free, better small targets)
- **Agentic Layer**: Add VLM (Qwen/SmolVLM) for scene understanding
- **Alerting**: Telegram bot via MCP or direct API

## 📊 Key Metrics for Surveillance
- MOTA (Multiple Object Tracking Accuracy) — DeepCamera beats ByteTrack on crowded scenes
- Latency — RTSP-WebRTC hybrid for low-latency defense
- False alarm reduction — VLM understanding + YOLO detection

## 🔗 Related in Textbook
- [LLM Inference Optimization 2026](LLM-Inference-Optimization-2026.md) — 🔴 [NEW]
- [ROCm AMD 780M Setup](ROCm-AMD-780M-Local-LLM-Setup-2026.md) — 🔴 [NEW]
- [MCP Model Context Protocol](MCP-Model-Context-Protocol-2026.md) — 🔴 [NEW]

---
*Added: 2026-08-17 | Status: 🔴 NEW | Source: ForaSoft, GitHub repos, academic papers*