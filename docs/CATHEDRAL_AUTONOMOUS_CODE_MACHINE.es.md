# 🏛️ CATHEDRAL — Máquina Autónoma de Código

> **Documentación técnica del Protocolo de Código Vivo y concepto Catedral — Máquina Autónoma de Código**  
> Versión: 1.0 (Evolución v4)  
> Idioma: Español

---

## Contenido

1. [Visión general](#visión-general)
2. [Arquitectura del Protocolo de Código Vivo](#arquitectura)
3. [Roles de agentes](#roles)
4. [Plan de evolución v4 (5 fases)](#plan-evolución)
5. [A-Evolve: Evolución de 3 capas](#a-evolve)
6. [Ciclo Self-HPO del arnés](#self-hpo)
7. [Canalización «código → lanzamiento»](#canalización-lanzamiento)
8. [Contratos UI/Media](#contratos)
9. [Clonación en un nuevo host](#clonación)
10. [Configuración del entorno](#entorno)
11. [Búsqueda de noticias (X.com, Reddit, GitHub)](#noticias)
12. [Informes de Telegram en tema 252](#telegram)

---

## 1. Visión general

CATHEDRAL — Máquina Autónoma de Código es un sistema autónomo de desarrollo de ciclo completo basado en el Protocolo de Código Vivo (ЖК) con integración GodModeCoder (arquitectura Catedral).

El sistema permite a 4 roles de agente evolucionar autónomamente 4 proyectos a través de 5 fases de evolución, con ciclo Self-HPO automático, envío de lanzamientos y entrega de informes al tema 252 de Telegram.

**Cuatro proyectos:**
- `superguard` — sistema de videovigilancia FastAPI + YOLO + Tuya + React
- `elemental-life` — simulación de vida elemental (v1/v2)
- `cybertarot` / `cybertarot-full` — aplicación de tarot cibernético
- `elemental-life-2` — segunda versión de la simulación

---

## 2. Arquitectura del Protocolo de Código Vivo

ЖК está organizado como arquitectura Catedral: cada herramienta es una piedra en el cimiento, no un parche.

```
Protocolo de Código Vivo
├── LV-coder-*           — 4 codificadores de proyecto (slot cada hora)
├── LV-lord-of-code      — Señor (veredictos: CALIENTE / FRÍO / DEVOLVER)
├── LV-producer          — Productor (lanzamiento automático)
├── LV-harness-opt       — Optimizador de arnés (Self-HPO H-step)
├── LV-artist            — Artista (ilustraciones, recursos)
├── LV-dj-musician       — Músico (pistas, voz en off, contrato v2)
└── LV-super-supervisor  — Super-Supervisor (post-verificación, etiquetado de lanzamiento)
```

Cada agente tiene su propio prompt, modelo (de lista blanca), programación de cron y presupuesto de slot.

---

## 3. Roles de agentes

| Rol | Modelo | Responsabilidad |
|-----|--------|-----------------|
| LV-coder-superguard | nemotron-3.5-super-vl-120b-a12b | Código del proyecto SuperGuard |
| LV-coder-elemental-life | nemotron-3.5-super-vl-120b-a12b | Código del proyecto Elemental Life |
| LV-coder-cybertarot | nemotron-3.5-super-vl-120b-a12b | Código del proyecto CyberTarot |
| LV-coder-elemental-life-2 | nemotron-3.5-super-vl-120b-a12b | Código del proyecto Elemental Life 2 |
| LV-lord-of-code | nemotron-3.5-super-vl-120b-a12b | Veredictos: CALIENTE/FRÍO/DEVOLVER |
| LV-producer | nemotron-3.5-super-vl-120b-a12b | Lanzamiento automático en CALIENTE + stabilen |
| LV-harness-opt | nemotron-3.5-super-vl-120b-a12b | H-step Self-HPO (diario) |
| LV-artist | nemotron-3.5-super-vl-120b-a12b | Ilustraciones y recursos del proyecto |
| LV-dj-musician | nemotron-3.5-super-vl-120b-a12b | Pistas y voz en off (contrato v2) |
| LV-super-supervisor | nemotron-3.5-super-vl-120b-a12b | Post-verificación + etiquetado de lanzamiento (cada hora) |

---

## 4. Plan de evolución v4 (5 fases)

| Fase | Nombre | Estado | Descripción |
|------|--------|--------|-------------|
| 0 | Fundación y endurecimiento | ✅ Completado | Super-Supervisor, verificación de cron, limpieza git, veredictos |
| 1 | Ciclo Self-HPO del arnés | ✅ Completado | H-step diario, retroalimentación P-step, puerta de transición |
| 2 | A-Evolve (3 capas) | ✅ Completado | Task-harness, Evolver, Meta-evolver (rama meta-evolver-layer3) |
| 3 | Código → Canalización de lanzamiento | ✅ Completado | release_project.py, lista de verificación, etiqueta vX.Y.Z, exportación APK |
| 4 | Contratos UI/Media | ✅ Completado | media_contract.py, contratos v2-artist/musician/producer |
| 5 | Publicación | 🔄 En progreso | Repositorio GitHub, localización RU/EN/ES, prompts Grok |

---

## 5. A-Evolve: Evolución de 3 capas

### Capa 1 — Task-harness
`jobs.json`, `config.yaml`, prompts de roles, plantillas en `agents/templates/` — bajo control de versiones en `orchestration/`.

### Capa 2 — Evolver
`living_code_agent_wrapper.py` — motor con respaldo de modelos, reintentos, limitador de velocidad de Telegram.  
`check_roster.py` — puerta CI para el registro de roles.

### Capa 3 — Meta-evolver
`meta_evolver.py` — evolución del propio código de evolución. Analiza `living_code_agent_wrapper.py`, `cycle_close.py`, `l3_critic.py`, `check_roster.py` en busca de marcadores TEMP/FIXME, docstrings faltantes, rutas de Windows. Crea rama `meta-evolver-layer3` y commit para revisión del Señor.

---

## 6. Ciclo Self-HPO del arnés

H-step (`LV-harness-opt`) se ejecuta una vez al día (03:00):
1. Lee `journal.md` — notas de agentes de las últimas 24 horas
2. Analiza `attempt_*.json` — rc=75, stale/unresponsive, tiempos de espera
3. Lee `errors.log` — errores del programador
4. Analiza `l3_critic` — stabilen / regress / nuzhna_rabota
5. Retroalimentación P-step — verifica si se leyó el informe anterior
6. Realiza cambios en `jobs.json` y prompts
7. Puerta de transición: 0 stale/unresponsive, 4 crons verdes, ≥1 artefacto de lanzamiento

P-step: codificador/artista/músico trabajan según el prompt actual, el resultado se fija en el informe.

---

## 7. Canalización «código → lanzamiento»

`release_project.py` ejecuta el ciclo completo de lanzamiento:

1. **Veredicto del Señor** — verifica `journal.md` en busca de veredicto CALIENTE
2. **Lista de verificación** — código frío (sin [СР]), git limpio, check_roster rc=0, ui_gate
3. **Versión** — semántica vX.Y.Z (incremento de parche desde la última etiqueta)
4. **Etiquetado** — etiqueta anotada `{proj}-v{version}` + push a origin
5. **Exportación APK** — copia `*.apk` a `~/apkexport/`
6. **Informe** — `reports/release-{proj}-v{version}-{ts}.md`
7. **Entrega** — Telegram Bot API al tema 252

---

## 8. Contratos UI/Media

`media_contract.py` define contratos para tres roles:

| Rol | Contrato | Archivos de salida | Directorio |
|-----|----------|-------------------|------------|
| artist | v2-artist | png, jpg, svg, gif, mp4 | `<proj>/assets/` |
| dj-musician | v2-musician | mp3, wav, ogg, flac | `<proj>/audio/`, `music/` |
| producer | v2-producer | apk, informe multimedia | `<proj>/`, `reports/` |

El informe multimedia agrega los tres roles y se entrega al tema 252.

---

## 9. Clonación en un nuevo host

### Ubuntu (Linux)

```bash
# 1. Instalar herramientas de desarrollo
sudo apt update && sudo apt install -y git curl wget build-essential

# 2. Instalar ~/build con cadena de herramientas
mkdir -p ~/build
cd ~/build
# Python 3.9-3.14, uv, Go, Rust, Node, JDK, Gradle, Flutter, Android SDK, .NET, Docker

# 3. Activar entorno
source ~/build/env.sh

# 4. Clonar repositorio
git clone https://github.com/PerfectFriend/NeXXus-Node.git ~/LivingCode
cd ~/LivingCode

# 5. Configurar Hermes
mkdir -p ~/.hermes/cron ~/.hermes/profiles/default
cp orchestration/jobs/jobs.json ~/.hermes/cron/jobs.json
cp orchestration/hermes-config/config.yaml ~/.hermes/profiles/default/config.yaml

# 6. Instalar dependencias
pip install -r requirements.txt

# 7. Establecer variables de entorno
export CATHEDRAL_BOT_TOKEN="<tu_token>"
export TELEGRAM_CRON_THREAD_ID=252

# 8. Verificar instalación
python3 orchestration/scripts/check_roster.py --update
bash orchestration/bin/verify.sh
```

### Windows

```powershell
# 1. Instalar Chocolatey o winget
# 2. Instalar Git, Python, Go, Rust, Node.js, JDK 21, Flutter, Docker Desktop

# 3. Crear ~/build (o C:/build)
mkdir ~/build
# Extraer cadena de herramientas en ~/build

# 4. Activar entorno
source ~/build/env.sh

# 5. Clonar repositorio
git clone https://github.com/PerfectFriend/NeXXus-Node.git ~/LivingCode
cd ~/LivingCode

# 6. Configurar Hermes (igual que Linux)
# Las rutas de Windows se reemplazan con rutas de Linux vía WSL2 o Git Bash

# 7. Verificar
python3 orchestration/scripts/check_roster.py --update
bash orchestration/bin/verify.sh
```

**Importante:** Todas las rutas en el código están en formato Linux (`/home/thomas/...`). En Windows use WSL2 o Git Bash con rutas correspondientes.

---

## 10. Configuración del entorno

### Variables de entorno

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `CATHEDRAL_BOT_TOKEN` | Token del bot de Telegram para informes | `8883516682:AAH0...` |
| `TELEGRAM_CRON_THREAD_ID` | ID del tema para informes | `252` |
| `LIVING_CODE_ROLE` | Rol del agente actual | `Super-Supervisor` |
| `LIVING_CODE_CRON_BUDGET` | Presupuesto de slot en segundos | `3600` |

### Lista blanca de modelos

Solo los siguientes modelos están permitidos por el protocolo:
- `nvidia/nemotron-3.5-super-vl-120b-a12b` (principal)
- `mistralai/mistral-large-4-1t-a52b` (respaldo)

Prohibidos: `nemotron-3-ultra-550b-a55b`, `minimax-m3.1-flash`, `gpt-6.1-sol/agentrouter` y otros (HISTORICALLY_DEAD).

---

## 11. Búsqueda de noticias (X.com, Reddit, GitHub)

### X.com (sin login)
- Método: `web_search site:x.com <consulta>` → lectura a través de Jina Reader `https://r.jina.ai/https://x.com/...`
- Habilidad: `x-browse` (categoría web)
- Usado por el buscador para búsqueda de noticias IT/AI

### Reddit (sin login)
- Método: `web_search site:reddit.com <consulta>` → `web_extract` en publicaciones específicas
- Habilidad: `reddit-browse` (categoría web)
- Acceso directo y Jina Reader bloqueados (403)

### GitHub
- Método: `web_search site:x.com github` → lectura de publicaciones @github a través de Jina Reader
- Acceso completo a la API de GitHub — en desarrollo

---

## 12. Informes de Telegram en tema 252

Todos los informes de fases de evolución se entregan a través de Telegram Bot API:

- Chat ID: `-1004431090317`
- Message Thread ID: `252`
- Método: `curl -X POST /sendDocument` con el archivo del informe
- Requerido: `CATHEDRAL_BOT_TOKEN` en variables de entorno

---

## Licencia

Licencia MIT

---

## Agradecimientos

- **GodModeCoder** — concepto Catedral y prompts de ejemplo
- **Protocolo de Código Vivo** — base para evolución autónoma de proyectos
- **xAI Grok** — generación de ilustraciones para el repositorio

_¡Que la Gran Fuerza del Universo esté contigo!_