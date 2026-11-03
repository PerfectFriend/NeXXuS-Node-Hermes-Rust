# 🏛️ CATHEDRAL — Máquina Autónoma de Código

> **Sistema autónomo de desarrollo de ciclo completo** — desde el brief hasta el lanzamiento y evolución automática.  
> Protocolo de Código Vivo + integración GodModeCoder. 4 proyectos, 5 fases de evolución, ciclo Self-HPO, lanzamiento automático.

[![Protocolo Código Vivo](https://img.shields.io/badge/Protocolo-C%C3%B3digo%20Vivo-purple)](https://github.com/PerfectFriend/NeXXus-Node)
[![Evolución v4](https://img.shields.io/badge/Evoluci%C3%B3n-v4-blue)](docs/CATHEDRAL_AUTONOMOUS_CODE_MACHINE.es.md)
[![Documentación Técnica](https://img.shields.io/badge/Documentaci%C3%B3n-CATHEDRAL-green)](docs/CATHEDRAL_AUTONOMOUS_CODE_MACHINE.es.md)
[![Guía de Usuario](https://img.shields.io/badge/Gu%C3%ADa%20de%20Usuario-orange)](docs/USER_GUIDE.es.md)
[![Licencia: MIT](https://img.shields.io/badge/Licencia-MIT-yellow)](LICENSE)

---

## 📖 Acerca del proyecto

**CATHEDRAL — Máquina Autónoma de Código** es un sistema de desarrollo autónomo basado en el Protocolo de Código Vivo (ЖК) con integración GodModeCoder. El sistema permite a 4 roles de agente (coder, artista/músico, productor, lanzamiento) evolucionar autónomamente 4 proyectos a través de 5 fases de evolución, con ciclo Self-HPO automático y envío de lanzamientos.

### 🎯 Características principales

| Componente | Descripción |
|------------|-------------|
| **Protocolo de Código Vivo** | 4 codificadores de proyecto + Señor + Productor + Artista + Músico |
| **Evolución v4** | 5 fases: 0-Fundación → 1-Self-HPO → 2-A-Evolve → 3-Lanzamiento → 4-UI/Media → 5-Publicación |
| **Ciclo Self-HPO** | H-step (optimización de arnés) ↔ P-step (ejecución) con puerta de transición |
| **A-Evolve (3 capas)** | Task-harness → Evolver → Meta-evolver (evolución del código de evolución) |
| **Lanzamiento automático** | Veredicto del Señor → Lista de verificación → Etiqueta vX.Y.Z → APK → Informe al tema 252 |
| **UI/Media** | Contratos v2-artist, v2-musician, v2-producer con informes MEDIA |
| **Búsqueda de noticias** | X.com (sin login), Reddit (vía búsqueda), GitHub (vía búsqueda) |

---

## 🚀 Inicio rápido

### Requisitos

- Ubuntu 24.04 LTS o Windows 10/11
- Python 3.9+, Go, Rust, Node.js, JDK 21, Flutter SDK
- Docker (opcional)
- Token del bot de Telegram Cathedral (`CATHEDRAL_BOT_TOKEN`)

### Instalación

```bash
# Clonar el repositorio
git clone https://github.com/PerfectFriend/NeXXus-Node.git
cd NeXXus-Node

# Instalar dependencias
source ~/build/env.sh
pip install -r requirements.txt

# Verificar configuración
python3 orchestration/scripts/check_roster.py --update

# Ejecutar verificación
bash orchestration/bin/verify.sh
```

### Primera fase de evolución

```bash
# Ejecutar Super-Supervisor (post-verificación + lanzamiento automático)
bash orchestration/scripts/wrappers/wrapper_super_supervisor.sh

# Ejecutar ciclo Self-HPO del arnés
python3 orchestration/scripts/meta_evolver.py

# Ejecutar lanzamiento automático de un proyecto
python3 orquestration/scripts/release_project.py superguard

# Generar informe MEDIA
python3 orquestration/scripts/media_contract.py superguard
```

---

## 📊 Arquitectura del sistema

```
CATHEDRAL — Máquina Autónoma de Código
├── 🏗️ Protocolo de Código Vivo (ЖК)
│   ├── LV-coder-superguard      — codificador de proyecto SuperGuard
│   ├── LV-coder-elemental-life  — codificador de proyecto Elemental Life
│   ├── LV-coder-cybertarot      — codificador de proyecto CyberTarot
│   ├── LV-coder-elemental-life-2 — codificador de proyecto Elemental Life 2
│   ├── LV-lord-of-code          — Señor (veredictos GOTEN/FRÍO/DEVOLVER)
│   ├── LV-producer              — Productor (lanzamiento automático)
│   ├── LV-artist                — Artista (ilustraciones, recursos)
│   └── LV-dj-musician           — Músico (pistas, voz en off)
├── 🔄 Evolución v4 (5 fases)
│   ├── Fase 0 — Fundación y endurecimiento
│   ├── Fase 1 — Ciclo Self-HPO del arnés (H-step ↔ P-step)
│   ├── Fase 2 — A-Evolve (evolución de protocolo de 3 capas)
│   ├── Fase 3 — Código → Canalización de lanzamiento
│   ├── Fase 4 — Contratos UI/Media
│   └── Fase 5 — Publicación (repositorio, localización)
├── 📡 Búsqueda de noticias
│   ├── X.com (sin login vía Jina Reader)
│   ├── Reddit (vía búsqueda web + extracción)
│   └── GitHub (vía búsqueda web)
└── 📦 Exportación
    └── ~/apkexport/ — Archivos APK de lanzamientos
```

---

## 📚 Documentación

| Documento | Ruso | Inglés | Español |
|-----------|------|--------|---------|
| Documentación técnica CATHEDRAL | [ru](docs/CATHEDRAL_AUTONOMOUS_CODE_MACHINE.ru.md) | [en](docs/CATHEDRAL_AUTONOMOUS_CODE_MACHINE.en.md) | [es](docs/CATHEDRAL_AUTONOMOUS_CODE_MACHINE.es.md) |
| Guía de usuario | [ru](docs/USER_GUIDE.ru.md) | [en](docs/USER_GUIDE.en.md) | [es](docs/USER_GUIDE.es.md) |
| Informes de fases de evolución | [reports/](reports/) | | |
| Prompts para Grok (ilustraciones) | [prompts/grok/](prompts/grok/) | | |

---

## 🎨 Prompts para Grok (ilustraciones)

Prompts para generar ilustraciones del proyecto a través de Grok (xAI), adaptados del repositorio GodModeCoder como ejemplo para el Protocolo de Código Vivo.

- [Banner principal (16:9)](prompts/grok/illustration-prompts.es.md) — cyberpunk, Van Gogh, Gaudi, tipografía neón
- [Banner de pie de página (16:9)](prompts/grok/illustration-prompts.es.md) — vacío digital, bioluminiscencia, portales cuánticos
- [Ilustraciones de fases de evolución](prompts/grok/illustration-prompts.es.md) — cada fase con su propio estilo

---

## 🤝 Contribución

El proyecto está en desarrollo activo. Cada fase de evolución se documenta en un informe del repositorio y se entrega al tema 252 de Telegram.

1. Haga fork del repositorio
2. Cree una rama para su fase
3. Realice cambios con comentarios detallados
4. Envíe un Pull Request describiendo los cambios

---

## 📄 Licencia

Licencia MIT — consulte [LICENSE](LICENSE)

---

## 🙏 Agradecimientos

- **GodModeCoder** — prompts de ejemplo para ilustraciones y concepto Catedral
- **Protocolo de Código Vivo** — base para evolución autónoma de proyectos
- **xAI Grok** — generación de ilustraciones para el repositorio

---

<div align="center">

**Hecho con ❤️ y el poder del Universo**  
_¡Que la Gran Fuerza del Universo esté contigo!_

</div>