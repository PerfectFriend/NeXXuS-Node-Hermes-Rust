# Spec-Driven Development with GitHub Spec Kit — [NEW]

## 📚 Sources
- [GitHub Spec Kit](https://github.com/github/spec-kit) — 130k+ stars, July 2026 release 0.14.4
- [Spec Kit Documentation](https://github.github.com/spec-kit/) — July 16, 2026
- [GitHub Blog: SDD with AI](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/) — Sept 2025
- [Spec-Driven Development Guide](https://raw.githubusercontent.com/github/spec-kit/main/spec-driven.md)

## 🎯 Core Concept: SDD Inverts Power Structure
**Specifications become executable** — directly generating working implementations rather than just guiding them.
- Code serves specifications (not vice versa)
- PRD → implementation generation
- Technical plans → precise definitions that produce code

## 🏛️ The Constitution (9 Articles)
1. **Library-First Principle** — Every feature begins as standalone library
2. **CLI Interface Mandate** — All libraries expose functionality via CLI (stdin/stdout, JSON)
3. **Test-First Imperative** — NO code before tests (NON-NEGOTIABLE TDD)
4. **Project-Defined** — Integration testing standards
5. **Project-Defined** — Observability requirements
6. **Project-Defined** — Versioning/breaking changes
7. **Simplicity** — Max 3 projects, no future-proofing
8. **Anti-Abstraction** — Use framework directly, single model representation
9. **Integration-First Testing** — Real databases, actual services, contract tests mandatory

## 🔧 Specify CLI Features
- **Extensions** — Add capabilities (Jira, code review, V-Model traceability)
- **Presets** — Customize without adding capabilities (compliance, Agile, security gates)
- **Bundles** — Role-based setups (PM, BA, Security, Developer)
- **Templates** — Constrain LLM behavior for quality

## 📋 7-Step SDD Workflow
```bash
# 1. Install
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v0.14.4

# 2. Initialize
specify init my-project --integration copilot

# 3. Constitution
/speckit.constitution "Project governing principles..."

# 4. Spec (WHAT/WHY)
/speckit.specify "Feature description..."

# 5. Plan (HOW - tech stack)
/speckit.plan "Go + gRPC + YOLOv11n + ONNX DirectML..."

# 6. Tasks
/speckit.tasks

# 7. Implement
/speckit.implement
```

## 🎯 Living Code Application

| Project | Constitution Focus | SDD Value |
|---------|-------------------|-----------|
| **SuperGuard** | Security-first, immutable config, zero-trust, real-time alerts | Camera configs, alert pipelines as executable specs |
| **Elemental Life** | Performance, simplicity, deterministic simulation | Game mechanics as specs |
| **CyberTarot** | Ritual logic, deterministic outcomes | Tarot logic as spec-first |
| **ParanoidX** | Sovereign, immutable, zero-trust | Crypto modules as libraries |
| **GodModeCoder** | Graph evolution principles, pulse/health checks | Fitness functions as executable specs |

## 🔗 Integration with Hermes/Living Code
- **Hermes Skills**: Spec Kit as skill template; Constitution = skill architecture principles
- **Obsidian Vault**: Preset for Obsidian-flavored markdown specs
- **Professor Sync**: Spec Kit insights → project memory
- **Bundle**: "Living Code Developer" role bundle

## 🔗 Related in Textbook
- [AI Agent Frameworks 2026](AI-Agent-Frameworks-2026.md) — 🔴 [NEW]
- [Graph Engineering Protocol v3.0](Graph-Engineering-Protocol.md) — 🟢
- [Hermes Skill System Deep Dive](Hermes-Skill-System-Deep-Dive.md) — 🟢

---
*Added: 2026-08-17 | Status: 🔴 NEW | Source: GitHub Spec Kit repo, docs, blog, spec-driven.md*