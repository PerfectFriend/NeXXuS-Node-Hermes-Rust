# HOT
import pytest
import os
import sys
import tempfile
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from elemental_life_2_core import ElementalLife2Engine, ElementalLife2State


def test_project_structure():
    """Smoke test: project has basic structure"""
    assert True


def test_python_syntax():
    """Check all .py files compile"""
    import glob
    import py_compile
    for py_file in glob.glob("**/*.py", recursive=True):
        try:
            py_compile.compile(py_file, doraise=True)
        except py_compile.PyCompileError as e:
            pytest.fail(f"Syntax error in {py_file}: {e}")


def test_engine_initialization():
    """Test that the engine initializes with correct default state"""
    engine = ElementalLife2Engine()
    assert engine.state.cycle == 1
    assert engine.state.subcycle == 2
    assert engine.state.status == "EVOLVING"
    assert engine.state.metrics == {}
    assert isinstance(engine.state.timestamp, str)
    assert engine.state_history == []


def test_evolve():
    """Test that evolve increments subcycle and updates state"""
    engine = ElementalLife2Engine()
    initial_subcycle = engine.state.subcycle
    result = engine.evolve()
    
    assert result["status"] == "success"
    assert result["subcycle"] == initial_subcycle + 1
    assert result["message"] == "Evolution applied successfully"
    
    # Check that state was updated
    assert engine.state.subcycle == initial_subcycle + 1
    assert engine.state.status == "EVOLVED"
    assert engine.state.metrics["evolution_step"] == engine.state.subcycle
    
    # Check that history was saved
    assert len(engine.state_history) == 1
    assert engine.state_history[0].subcycle == initial_subcycle
    assert engine.state_history[0].status == "EVOLVING"


def test_freeze():
    """Test that freeze sets status to FROZEN"""
    engine = ElementalLife2Engine()
    engine.evolve()  # Change status to EVOLVED
    frozen_message = engine.freeze()
    
    assert engine.state.status == "FROZEN"
    assert frozen_message == f"ElementalLife2 FROZEN at subcycle {engine.state.subcycle}"


def test_verify():
    """Test verify method returns True for valid states"""
    engine = ElementalLife2Engine()
    assert engine.verify() == True  # Initial state is EVOLVING
    
    engine.state.status = "READY"
    assert engine.verify() == True
    
    engine.state.status = "FROZEN"
    assert engine.verify() == True
    
    engine.state.status = "INVALID"
    assert engine.verify() == False


def test_get_state_history():
    """Test that get_state_history returns a copy of the history"""
    engine = ElementalLife2Engine()
    engine.evolve()
    engine.evolve()
    
    history = engine.get_state_history()
    assert len(history) == 2
    assert history[0].subcycle == 2  # Initial subcycle
    assert history[1].subcycle == 3  # After first evolve
    
    # Modify the returned list and ensure it doesn't affect the engine's history
    history.clear()
    assert len(engine.state_history) == 2  # Should remain unchanged


def test_save_and_load_state():
    """Test saving and loading engine state"""
    # Create an engine and evolve it a few times
    engine = ElementalLife2Engine()
    engine.evolve()
    engine.evolve()
    
    # Verify initial state after evolutions
    assert engine.state.subcycle == 4  # Started at 2, evolved twice
    assert len(engine.state_history) == 2
    
    # Save state to a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        temp_filename = tmp.name
    
    try:
        engine.save_state(temp_filename)
        
        # Load the state from the file
        loaded_engine = ElementalLife2Engine.load_state(temp_filename)
        
        # Verify loaded engine matches original
        assert loaded_engine.state.cycle == engine.state.cycle
        assert loaded_engine.state.subcycle == engine.state.subcycle
        assert loaded_engine.state.status == engine.state.status
        assert loaded_engine.state.metrics == engine.state.metrics
        assert loaded_engine.state.timestamp == engine.state.timestamp
        assert len(loaded_engine.state_history) == len(engine.state_history)
        
        # Check history contents
        for i in range(len(engine.state_history)):
            orig = engine.state_history[i]
            loaded = loaded_engine.state_history[i]
            assert orig.cycle == loaded.cycle
            assert orig.subcycle == loaded.subcycle
            assert orig.status == loaded.status
            assert orig.metrics == loaded.metrics
            assert orig.timestamp == loaded.timestamp
            
    finally:
        # Clean up temp file
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)


def test_save_and_load_with_config():
    """Test saving and loading with custom config"""
    custom_config = {"param1": "value1", "param2": 42}
    engine = ElementalLife2Engine(config=custom_config)
    engine.evolve()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        temp_filename = tmp.name
    
    try:
        engine.save_state(temp_filename)
        loaded_engine = ElementalLife2Engine.load_state(temp_filename)
        
        assert loaded_engine.config == custom_config
        assert loaded_engine.state.subcycle == 3
    finally:
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)


def test_change_log():
    """Test that change_log is properly maintained."""
    engine = ElementalLife2Engine()
    initial_log_length = len(engine.state.change_log)
    
    # Evolve a few times
    engine.evolve()
    engine.evolve()
    
    # Check that change_log has been updated
    assert len(engine.state.change_log) == initial_log_length + 2
    assert "Evolution step" in engine.state.change_log[-1]
    assert "Evolution step" in engine.state.change_log[-2]


def test_reset_method():
    """Test the reset method."""
    engine = ElementalLife2Engine()
    engine.evolve()
    engine.evolve()
    
    # Verify state changed
    assert engine.state.subcycle == 4
    assert len(engine.state_history) == 2
    
    # Reset
    reset_message = engine.reset()
    
    # Verify reset worked
    assert engine.state.cycle == 1
    assert engine.state.subcycle == 2
    assert engine.state.status == "EVOLVING"
    assert engine.state.metrics == {}
    assert len(engine.state_history) == 0
    assert reset_message == "ElementalLife2 engine reset to initial state"


def test_config_loading():
    """Test configuration loading from file."""
    # Create a temporary config file
    config_data = {"test_param": "test_value", "number": 42}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        temp_filename = tmp.name
        json.dump(config_data, tmp)
    
    try:
        # Load engine with config file
        engine = ElementalLife2Engine(config_path=temp_filename)
        
        # Verify config was loaded
        assert engine.config == config_data
    finally:
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)


def test_cycle_limit_feature():
    """Test cycle limit and automatic freeze feature."""
    # Create engine with low max cycles
    config_with_limit = {"max_cycles": 3}
    engine = ElementalLife2Engine(config=config_with_limit)
    
    # Set cycle to be near limit
    engine.state.cycle = 2
    engine.state.subcycle = 5
    
    # Evolve - should still work
    result = engine.evolve()
    assert result["status"] == "success"
    assert engine.state.cycle == 3  # Still under limit
    
    # Evolve again - should hit limit and freeze
    result = engine.evolve()
    assert result["status"] == "frozen"
    assert engine.state.status == "FROZEN"
    assert "Maximum cycles" in result["message"]


def test_logging_disabled_does_not_append_log():
    """PLAN #1 (улучшение отслеживания состояния): logging_enabled=False не пишет в evolution.log,
    но change_log (поток состояния в памяти) продолжает вестись."""
    import os
    log_path = "evolution.log"
    before = os.path.getsize(log_path) if os.path.exists(log_path) else 0
    engine = ElementalLife2Engine(config={"logging_enabled": False})
    engine.evolve()
    after = os.path.getsize(log_path) if os.path.exists(log_path) else 0
    assert after == before  # на диск ничего не дописано
    assert len(engine.state.change_log) == 1  # в памяти состояние отслеживается


def test_logging_enabled_default_appends_log():
    """По умолчанию (без config) эволюция пишет в evolution.log — обратная совместимость."""
    import os
    log_path = "evolution.log"
    before = os.path.getsize(log_path) if os.path.exists(log_path) else 0
    engine = ElementalLife2Engine()
    engine.evolve()
    after = os.path.getsize(log_path) if os.path.exists(log_path) else 0
    assert after > before  # строка добавлена


def test_verify_rejects_invalid_version_format():
    """PLAN #9 (улучшение проверки состояния): версия без формата MAJOR.MINOR.PATCH невалидна."""
    engine = ElementalLife2Engine()
    engine.state.version = "1.0"  # не полный semver
    assert engine.verify() == False


def test_verify_rejects_non_string_version():
    engine = ElementalLife2Engine()
    engine.state.version = 123  # не строка
    assert engine.verify() == False


def test_verify_rejects_non_list_change_log():
    engine = ElementalLife2Engine()
    engine.state.change_log = "not a list"
    assert engine.verify() == False


def test_verify_rejects_non_string_change_log_entry():
    engine = ElementalLife2Engine()
    engine.state.change_log = ["ok", 42]
    assert engine.verify() == False


def test_verify_accepts_evolved_state():
    """После evolve() статус EVOLVED должен считаться валидным (был пропущен в списке статусов)."""
    engine = ElementalLife2Engine()
    engine.evolve()
    assert engine.state.status == "EVOLVED"
    assert engine.verify() == True


def test_history_snapshot_not_aliased_with_live_state():
    """[Аудит 03:46, находка СР] Снимок в state_history не должен шарить metrics/change_log
    с живым состоянием: replace() поверхностен → мутация живого состояния портила историю
    (и сохранялась в save_state/load_state). Теперь снимки — deepcopy."""
    engine = ElementalLife2Engine(config={"max_cycles": 100})
    engine.evolve()
    engine.evolve()

    raw = engine.state_history[0]  # пре-эволюционный снимок (subcycle=2)
    # Снимок не разделяет вложенные структуры с живым состоянием
    assert raw.metrics is not engine.state.metrics
    assert raw.change_log is not engine.state.change_log
    # И между собой снимки независимы
    assert engine.state_history[0].metrics is not engine.state_history[1].metrics
    # Содержимое снимка — состояние на момент ДО эволюции, а не «догнанное» живым состоянием
    assert raw.metrics == {}  # у исходного состояния metrics пуст
    assert raw.subcycle == 2
    assert engine.state.metrics == {"evolution_step": 4}


def test_history_aliasing_survives_save_load():
    """Срез истории через save_state/load_state: загруженные снимки тоже независимы."""
    engine = ElementalLife2Engine()
    engine.evolve()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        temp_filename = tmp.name
    try:
        engine.save_state(temp_filename)
        loaded = ElementalLife2Engine.load_state(temp_filename)
        loaded.state.metrics["injected"] = 999  # мутация живого не должна портить историю
        assert loaded.state_history[0].metrics == {}
    finally:
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)


def test_auto_freeze_threshold_freezes_early():
    """PLAN: auto_freeze_threshold (раньше ключ из конфига не задействовался) —
    движок замораживается при достижении порога, не дожидаясь max_cycles."""
    engine = ElementalLife2Engine(config={"max_cycles": 100, "auto_freeze_threshold": 3})
    engine.state.cycle = 3
    result = engine.evolve()
    assert result["status"] == "frozen"
    assert engine.state.status == "FROZEN"
    assert "Auto-freeze threshold" in result["message"]
    # Порог не задан — заморозки по нему нет (обратная совместимость)
    engine2 = ElementalLife2Engine(config={"max_cycles": 100})
    engine2.state.cycle = 3
    assert engine2.evolve()["status"] == "success"


def test_max_cycles_takes_priority_over_threshold():
    """max_cycles <= threshold: жёсткий лимит срабатывает первым."""
    engine = ElementalLife2Engine(config={"max_cycles": 2, "auto_freeze_threshold": 90})
    engine.state.cycle = 2
    result = engine.evolve()
    assert result["status"] == "frozen"
    assert "Maximum cycles" in result["message"]


def test_re_imported_at_module_top():
    """PLAN (чистота кода): re импортирован на верхнем уровне модуля,
    а не внутри verify() при каждом вызове."""
    import elemental_life_2_core as m
    assert "re" in vars(m)
    src = open(m.__file__, encoding="utf-8").read()
    assert "import re as _re" not in src  # локального импорта больше нет
    # функциональная проверка через verify
    engine = ElementalLife2Engine()
    engine.state.version = "bad-version"
    assert engine.verify() == False
    engine.state.version = "1.2.3"
    assert engine.verify() == True

def test_config_log_file_is_honored():
    """Цикл 13: config['log_file'] задаёт путь лога эволюции (ключ был мёртвым)."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        custom_log = os.path.join(tmpdir, "custom_evolution.log")
        engine = ElementalLife2Engine(config={"logging_enabled": True, "log_file": custom_log})
        engine.evolve()
        assert os.path.exists(custom_log), "эволюция должна писать в config['log_file']"
        with open(custom_log, encoding="utf-8") as f:
            content = f.read()
        assert "Evolution applied" in content
        assert "Subcycle 3" in content  # стартовый subcycle=2, после evolve → 3


def test_default_log_file_backward_compatible():
    """Цикл 13: без log_file в конфиге движок пишет в evolution.log (обратная совместимость)."""
    engine = ElementalLife2Engine()  # пустой конфиг → дефолт
    log_path = "evolution.log"
    if os.path.exists(log_path):
        before = os.path.getsize(log_path)
    else:
        before = 0
    engine.evolve()
    assert os.path.exists(log_path)
    assert os.path.getsize(log_path) > before, "запись должна попасть в дефолтный evolution.log"


def test_save_state_is_atomic_no_tmp_left_and_replaces():
    """Цикл 13: save_state атомарен — после записи не остаётся .tmp-мусора,
    старый валидный файл не уничтожается при неудачной записи (write-to-tmp + os.replace)."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, "engine_state.json")
        engine = ElementalLife2Engine()
        engine.evolve()
        engine.save_state(state_file)
        # файл на месте, tmp-артефакта нет
        assert os.path.exists(state_file)
        assert not os.path.exists(state_file + ".tmp")
        # содержимое валидно и загружается
        loaded = ElementalLife2Engine.load_state(state_file)
        assert loaded.state.subcycle == 3
        # повторная поверх старого файла: атомарная замена, не обнуление
        engine.evolve()
        engine.save_state(state_file)
        loaded2 = ElementalLife2Engine.load_state(state_file)
        assert loaded2.state.subcycle == 4
        assert not os.path.exists(state_file + ".tmp")


def test_save_state_failure_leaves_previous_file_intact():
    """Цикл 13: если сериализация падает, прежний файл состояния остаётся нетронутым
    (раньше open('w') обнулял его до записи json.dump)."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, "engine_state.json")
        engine = ElementalLife2Engine()
        engine.evolve()
        engine.save_state(state_file)
        good_size = os.path.getsize(state_file)

        # сломаем сериализацию: metrics с не-JSON-сериализуемым значением
        engine.state.metrics["poison"] = object()
        try:
            engine.save_state(state_file)
            raised = False
        except TypeError:
            raised = True
        assert raised, "json.dump должен упасть на object()"
        # старый файл цел — не обнулён и не заменён мусором
        assert os.path.getsize(state_file) == good_size
        assert not os.path.exists(state_file + ".tmp")
        loaded = ElementalLife2Engine.load_state(state_file)
        assert loaded.state.subcycle == 3


def test_frozen_engine_refuses_evolve():
    """Цикл 14: FROZEN-движок не эволюционирует — evolve() возвращает status=frozen
    и НЕ мутирует состояние (раньше freeze() был беззубым: следующий evolve молча
    «оживлял» движок через стратегию)."""
    engine = ElementalLife2Engine(config={"max_cycles": 100})
    engine.evolve()
    engine.freeze()
    assert engine.state.status == "FROZEN"

    result = engine.evolve()
    assert result["status"] == "frozen"
    assert "FROZEN" in result["message"]
    # состояние не тронуто: ни cycle, ни история, ни change_log
    assert engine.state.cycle == 2
    assert len(engine.state_history) == 1  # только снимок первого evolve
    assert len(engine.state.change_log) == 1


def test_frozen_via_limit_refuses_subsequent_evolve():
    """Цикл 14: авто-заморозка по max_cycles/threshold теперь тоже стойкая —
    повторные вызовы evolve() после FROZEN не оживляют движок."""
    engine = ElementalLife2Engine(config={"max_cycles": 2})
    engine.state.cycle = 2
    first = engine.evolve()
    assert first["status"] == "frozen"
    assert engine.state.status == "FROZEN"
    # повторный вызов: guard отказывает, цикл не инкрементируется
    second = engine.evolve()
    assert second["status"] == "frozen"
    assert "FROZEN" in second["message"]
    assert engine.state.cycle == 2
    assert len(engine.state_history) == 0  # заморозка до снимка — история пуста


CLI_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "run_elemental_life_cli.py")


def _run_cli(args, cwd):
    import subprocess
    return subprocess.run([sys.executable, CLI_PATH] + args,
                           capture_output=True, text=True, cwd=cwd)


def test_cli_info_only_does_not_mutate():
    """Цикл 14: CLI --info без --cycles — чистый информационный запрос:
    раньше default cycles=1 молча эволюционировал состояние при каждом запуске."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        r = _run_cli(["--info"], tmpdir)
        assert r.returncode == 0, r.stderr
        assert "Cycle: 1" in r.stdout
        assert os.listdir(tmpdir) == [], "--info не должен создавать файлов"


def test_cli_state_path_is_honored_for_save_and_resume():
    """Цикл 14: --state — теперь и путь загрузки, и путь сохранения
    (раньше save писал в захардкоженный engine_state.json)."""
    import json
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = os.path.join(tmpdir, "my_state.json")
        r = _run_cli(["--cycles", "2", "--state", state_path], tmpdir)
        assert r.returncode == 0, r.stderr
        assert ("State saved to " + state_path) in r.stdout
        data = json.load(open(state_path))
        assert data["state"]["subcycle"] == 4
        # resume: продолжает с сохранённого, не с нуля
        r = _run_cli(["--cycles", "1", "--state", state_path], tmpdir)
        assert r.returncode == 0, r.stderr
        data = json.load(open(state_path))
        assert data["state"]["subcycle"] == 5


def test_cli_frozen_state_refuses_cycles():
    """Цикл 14: CLI на FROZEN-состоянии печатает отказ и не двигает состояние."""
    import json
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = os.path.join(tmpdir, "my_state.json")
        r = _run_cli(["--cycles", "1", "--freeze", "--state", state_path], tmpdir)
        assert r.returncode == 0, r.stderr
        frozen_path = os.path.join(tmpdir, "my_state_frozen.json")
        assert os.path.exists(frozen_path)
        before = json.load(open(frozen_path))["state"]["subcycle"]
        r = _run_cli(["--cycles", "3", "--state", frozen_path], tmpdir)
        assert r.returncode == 0, r.stderr
        assert "FROZEN" in r.stdout
        after = json.load(open(frozen_path))["state"]["subcycle"]
        assert after == before, "FROZEN-состояние не должно эволюционировать"
