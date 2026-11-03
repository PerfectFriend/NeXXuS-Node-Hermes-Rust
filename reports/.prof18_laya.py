import subprocess, sys

CANDS = [
    "Matthew Green: достаточно ли песочницы, чтобы удержать rogue-агентов (zero-day в Artifactory, admin на кластере)",
    "Transluce: агенты атаковали сайты правительств США и Канады, SQL-injection, 200000 запросов, утечек не найдено",
    "HiSentinel: дешёвый гейт до исполнения, ловит опасные действия агента до запуска",
    "Competing-Hazards: исход попытки агента не бинарный, continuation отдельный наблюдаемый исход, escape probability в retry-бюджете",
    "Worktrunk: git worktree по имени ветки для 5-10 параллельных агентов, wt switch/step/hook",
    "Cloudflare OS: управляемое агенто-рабочее пространство компании как сервис, а не набор кронов",
    "Harness Engineering как отдельная дисциплина: анатомия и эволюция харнесса кодинг-агентов",
    "COGNIT-Guard: калиброванные гарды именно на классе решающих моделей, дешёвый CPU-гейткипер",
    "Selective withdrawal: агенты не умеют останавливаться, нужно уметь отказаться от задачи",
    "Aletheia: тест минимальности прав агента перед выдачей доступов",
]

STATE = "Проекты Живого Кода: рой агентов-кодеров, локальные LLM, UI-гейты, самообучение роя"
BRIDGE = "/home/thomas/LivingCode/orchestration/scripts/laya_bridge.py"

out = []
for batch in (CANDS[:5], CANDS[5:]):
    p = subprocess.run([sys.executable, BRIDGE, "score", "--state-context", STATE],
                       input="\n".join(batch), capture_output=True, text=True, timeout=300)
    out.append(p.stdout + (p.stderr if p.returncode else ""))
    print(out[-1], flush=True)
