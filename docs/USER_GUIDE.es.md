# 📘 Guía de Usuario CATHEDRAL

> **Cómo usar el Protocolo de Código Vivo y el sistema Máquina Autónoma de Código**  
> Versión: 1.0  
> Idioma: Español

---

## Contenido

1. [Primer lanzamiento](#primer-lanzamiento)
2. [Trabajo con tareas cron](#tareas-cron)
3. [Cómo trabajar con veredictos del Señor](#veredictos)
4. [Cómo lanzar un proyecto](#lanzamiento)
5. [Cómo generar informe MEDIA](#informe-media)
6. [Cómo agregar un nuevo codificador](#nuevo-codificador)
7. [Cómo actualizar el prompt de un rol](#prompt-rol)
8. [Problemas comunes y su solución](#problemas)

---

## 1. Primer lanzamiento

```bash
# Activar entorno de desarrollo
source ~/build/env.sh

# Verificar configuración de roles
python3 ~/LivingCode/orchestration/scripts/check_roster.py --update

# Ejecutar verificación
bash ~/LivingCode/orchestration/bin/verify.sh

# Asegurarse de que muestra "нет проблем" (sin problemas)
```

Si todo pasa correctamente, ya puedes trabajar con el Protocolo de Código Vivo.

---

## 2. Trabajo con tareas cron

Todas las tareas están configuradas en `orchestration/jobs/jobs.json`. Cada tarea tiene:
- `name` — nombre del cron (ej. `LV-coder-superguard`)
- `schedule` — expresión cron (ej. `0 * * * *` para cada hora)
- `enabled` — si la tarea está activa
- `model` — modelo LLM (de la lista blanca)
- `script` — ruta al envoltorio (si es null, el agente se ejecuta vía Hermes)

### Verificar el estado de todas las tareas:
```bash
python3 ~/LivingCode/orchestration/scripts/check_roster.py --update
```

### Habilitar una tarea:
Editar `jobs.json`, establecer `enabled: true`, luego copiar a `~/.hermes/cron/jobs.json`.

---

## 3. Cómo trabajar con veredictos del Señor

El Señor del Código (`LV-lord-of-code`) emite veredictos en `journal.md`:

| Veredicto | Significado | Qué hacer |
|-----------|-------------|-----------|
| CALIENTE | Proyecto listo para lanzamiento | Ejecutar `release_project.py <proyecto>` |
| FRÍO | Proyecto en desarrollo | Continuar trabajo del codificador |
| DEVOLVER | Necesita correcciones | El codificador corrige errores |

### Ejemplo de registro en journal.md:
```
[TRIGGER_LORD] superguard — ВЕРДИКТ: superguard — ГОРЯЧИЙ
```

---

## 4. Cómo lanzar un proyecto

```bash
# Ejecutar lanzamiento automático de un proyecto
python3 ~/LivingCode/orchestration/scripts/release_project.py superguard

# Para otros proyectos:
python3 ~/LivingCode/orchestration/scripts/release_project.py elemental-life
python3 ~/LivingCode/orchestration/scripts/release_project.py cybertarot
python3 ~/LivingCode/orchestration/scripts/release_project.py elemental-life-2
```

El script hará:
1. Verificar veredicto del Señor (debe ser CALIENTE)
2. Verificar lista de verificación de lanzamiento (código frío, sin cambios sin commit, check_roster rc=0)
3. Determinar versión vX.Y.Z
4. Etiquetar y hacer push a GitHub
5. Exportar APK a `~/apkexport/`
6. Informe en `reports/`
7. Entrega al tema 252 (si está configurado CATHEDRAL_BOT_TOKEN)

---

## 5. Cómo generar informe MEDIA

```bash
# Informe multimedia para el proyecto (los tres roles: artista, músico, productor)
python3 ~/LivingCode/orchestration/scripts/media_contract.py superguard
```

El informe se guarda en `reports/media-{proj}-{ts}.md` y contiene:
- Número de activos del artista
- Número de archivos de audio del músico
- Número de APK del productor
- Información del log de recibos

---

## 6. Cómo agregar un nuevo codificador

1. Crear directorio del proyecto en `Projects/<nombre>/`
2. Agregar tarea a `jobs.json` con nombre `LV-coder-<nombre>`
3. Crear prompt en `scripts/wrappers/prompts/<nombre>.txt`
4. Ejecutar `check_roster.py --update` para verificar
5. Ejecutar `verify.sh` para verificación

---

## 7. Cómo actualizar el prompt de un rol

Los prompts de roles están en `scripts/wrappers/prompts/`. Para actualizar:
1. Editar el archivo del prompt
2. Agregar comentarios detallados (para codificadores nuevos no familiarizados con el proyecto)
3. Guardar cambios
4. Reiniciar el cron correspondiente

---

## 8. Problemas comunes y su solución

| Problema | Solución |
|----------|----------|
| `CATHEDRAL_BOT_TOKEN` no configurado | Agregar token al entorno: `export CATHEDRAL_BOT_TOKEN="..."` |
| Los informes no se entregan al tema 252 | Verificar `TELEGRAM_CRON_THREAD_ID=252` y token del bot |
| Cambios sin commit en proyectos | Hacer `git commit` en el directorio del proyecto antes del lanzamiento |
| Errores de check_roster | Corregir `jobs.json` y copiar a `~/.hermes/cron/jobs.json` |
| Tareas cron en pausa | Establecer `enabled: true` en `jobs.json` |
| Error de ruta de Windows en el código | Reemplazar `C:/...` por `/home/thomas/...` |

---

## 9. Obtener ayuda

Si algo no funciona:
1. Revisar logs en `~/.hermes/cron/errors.log`
2. Revisar informes en `reports/`
3. Revisar `journal.md` en busca de veredictos y disparadores
4. Asegurarse de que `verify.sh` muestra «sin problemas»

---

_¡Que la Gran Fuerza del Universo esté contigo!_