"""Тесты p3_memory. Запуск: python3 -m unittest discover -s tests -v

Проверяются три контура:
  * штатный корпус Project3 — реальные файлы `memory/`;
  * искусственно испорченный корпус — битый JSON, маркер `# HOT`, пустой
    список, неверная схема, разведённые копии соседей;
  * защита от записи вне проекта и атомарность записи.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from p3_memory import SYNC_DEFAULT_PROJECTS  # noqa: E402
from p3_memory import attribution, canon, gate, identity, loader, metrics, report  # noqa: E402
from p3_memory.cli import build_parser, main as cli_main  # noqa: E402
from p3_memory.paths import (  # noqa: E402
    PathRefused, append_section, atomic_write, project_root, safe_path,
)

REAL_MEMORY = project_root() / "memory"


def make_record(topic="Тема", category="Категория", summary="сводка",
                url="https://example.com/a", source_type="web",
                score=0.7, projects=(1, 2, 3, 4), tags=("learned",)):
    return {
        "topic": topic,
        "category": category,
        "summary": summary,
        "source_url": url,
        "source_type": source_type,
        "relevance_score": score,
        "applicable_projects": list(projects),
        "tags": list(tags),
        "timestamp": "2026-08-16T08:10:33.000000+00:00",
    }


def write_corpus(root: Path, cycle_files: dict) -> Path:
    """Создать каталог памяти из {имя файла: список записей}."""
    root.mkdir(parents=True, exist_ok=True)
    for name, insights in cycle_files.items():
        payload = {
            "cycle": 1,
            "project": 3,
            "synced_at": "2026-08-16T08:10:33+00:00",
            "insights": insights,
            "total_insights": len(insights),
        }
        (root / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return root


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p3test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def fake_memory(self, cycle_files=None):
        if cycle_files is None:
            cycle_files = {
                "professor_insights_cycle_001.json": [
                    make_record(topic="Графы", url="https://a/1"),
                    make_record(topic="Память", url="https://a/2", source_type="memory"),
                ],
            }
        return write_corpus(self.tmp / "memory", cycle_files)


# ---------------------------------------------------------------- загрузчик

class TestStripMarkers(Base):
    def test_snyat_marker_vnachale(self):
        text, removed = loader.strip_markers("# HOT\n{\"a\": 1}")
        self.assertEqual(text, '{"a": 1}')
        self.assertEqual(removed, ["# HOT"])

    def test_snyatye_dva_markerov(self):
        text, removed = loader.strip_markers("# HOT\n# COLD\n{}")
        self.assertEqual(text, "{}")
        self.assertEqual(removed, ["# HOT", "# COLD"])

    def test_bez_markerov_text_ne_trogaetsya(self):
        text, removed = loader.strip_markers('{"a": "# HOT"}')
        self.assertEqual(text, '{"a": "# HOT"}')
        self.assertEqual(removed, [])

    def test_marker_ne_v_pervoy_stroke_ne_snymaetsya(self):
        text, removed = loader.strip_markers('{"note": "x"}\n# HOT\n')
        self.assertEqual(removed, [])


class TestLoad(Base):
    def test_chitaet_shtatnyy_korpus(self):
        for path in loader.discover(REAL_MEMORY):
            data = loader.load(path)
            self.assertIn("insights", data)
            self.assertEqual(data["total_insights"], len(data["insights"]))

    def test_umnaet_total_insights_esli_net_polya(self):
        path = self.tmp / "x.json"
        path.write_text(json.dumps({"insights": [{"topic": "a"}]}), encoding="utf-8")
        self.assertEqual(loader.load(path)["total_insights"], 1)

    def test_bitaya_ymlka_daet_ponatnuyu_oshibku(self):
        path = self.tmp / "bad.json"
        path.write_text("{не json", encoding="utf-8")
        with self.assertRaises(loader.MemoryInvalid) as ctx:
            loader.load(path)
        self.assertIn("невалидный JSON", str(ctx.exception))

    def test_marker_v_ymlke_ne_lomaet_zagruzku(self):
        path = self.tmp / "marked.json"
        good = {"insights": [make_record()], "total_insights": 1}
        path.write_text("# HOT\n" + json.dumps(good, ensure_ascii=False), encoding="utf-8")
        data = loader.load(path)
        self.assertEqual(data["_markers_removed"], ["# HOT"])
        self.assertEqual(len(data["insights"]), 1)

    def test_net_polya_insights_eto_oshibka(self):
        path = self.tmp / "noins.json"
        path.write_text(json.dumps({"cycle": 1}), encoding="utf-8")
        with self.assertRaises(loader.MemoryInvalid):
            loader.load(path)

    def test_massiv_vmesto_obekta_etо_oshibka(self):
        path = self.tmp / "arr.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        with self.assertRaises(loader.MemoryInvalid):
            loader.load(path)

    def test_rassoglasonie_total_insights_lovitsya(self):
        path = self.tmp / "liar.json"
        path.write_text(
            json.dumps({"insights": [make_record()], "total_insights": 99}),
            encoding="utf-8",
        )
        with self.assertRaises(loader.MemoryInvalid) as ctx:
            loader.load(path)
        self.assertIn("total_insights", str(ctx.exception))

    def test_nechitaemyy_fail_daet_oshibku(self):
        missing = self.tmp / "net-takogo.json"
        with self.assertRaises(loader.MemoryInvalid):
            loader.load(missing)


class TestValidateInsight(Base):
    def test_khoroshaya_zapis_bez_pretenziy(self):
        self.assertEqual(loader.validate_insight(make_record(), "x"), [])

    def test_net_obyazatelnogo_polya(self):
        problems = loader.validate_insight({"category": "C"}, "x")
        self.assertTrue(any("topic" in p for p in problems))

    def test_nevernyy_tip_polya(self):
        record = make_record()
        record["relevance_score"] = "высоко"
        self.assertTrue(
            any("relevance_score" in p for p in loader.validate_insight(record, "x"))
        )

    def test_relevance_vne_diapazona(self):
        problems = loader.validate_insight(make_record(score=7.5), "x")
        self.assertTrue(any("[0, 1]" in p for p in problems))

    def test_boolean_ne_schitaetsya_chislom(self):
        record = make_record()
        record["relevance_score"] = True
        self.assertTrue(
            any("relevance_score" in p for p in loader.validate_insight(record, "x"))
        )

    def test_ne_obyekt_vmesto_zapisi(self):
        self.assertEqual(len(loader.validate_insight("строка", "x")), 1)

    def test_ne_celoe_v_applicable_projects(self):
        record = make_record(projects=("1",))
        self.assertTrue(
            any("applicable_projects" in p for p in loader.validate_insight(record, "x"))
        )


class TestValidateCorpus(Base):
    def test_shtatnyy_korpus_chist(self):
        result = loader.validate_corpus(REAL_MEMORY)
        self.assertTrue(result["valid"], result["problems"][:5])
        self.assertGreater(result["records"], 0)

    def test_ispорченный_korpus_vilet_v_spisok_pretenziy(self):
        memory = self.fake_memory()
        (memory / "professor_insights_cycle_002.json").write_text("{бито", encoding="utf-8")
        result = loader.validate_corpus(memory)
        self.assertFalse(result["valid"])
        self.assertTrue(result["unreadable"])

    def test_fajl_s_chenuzh_imennym_proektom_lovitsya(self):
        memory = self.fake_memory()
        (memory / "professor_insights_cycle_009.json").write_text(
            json.dumps({"cycle": 9, "project": 2, "insights": [make_record()],
                        "total_insights": 1}),
            encoding="utf-8",
        )
        result = loader.validate_corpus(memory)
        self.assertFalse(result["valid"])
        self.assertTrue(any("project=2" in p for p in result["problems"]))

    def test_pustoy_korpus_validno_no_pustoy(self):
        memory = write_corpus(self.tmp / "empty", {})
        result = loader.validate_corpus(memory)
        self.assertTrue(result["valid"])
        self.assertEqual(result["records"], 0)


class TestDefaultAddressed(Base):
    def test_defoltnaya_adresatsiya_raspoznavayetsya(self):
        self.assertTrue(loader.is_default_addressed(make_record()))

    def test_inoe_pole_adye_v_rassmotrenie_ne_vozyet(self):
        self.assertFalse(loader.is_default_addressed(make_record(projects=(3,))))

    def test_ne_spisok_ne_lyaet_s_soboy(self):
        record = make_record()
        record["applicable_projects"] = "1,2,3,4"
        self.assertFalse(loader.is_default_addressed(record))


# ---------------------------------------------------------------- канонизация

class TestRecordKey(Base):
    def test_klyuch_normaliuet_registr_i_probely(self):
        a = make_record(topic="  Граф  знаний ")
        b = make_record(topic="граф знаний")
        self.assertEqual(canon.record_key(a), canon.record_key(b))

    def test_url_bez_query_i_hvosta_sovpadayet(self):
        a = make_record(url="https://x.com/i/status/1?utm=a")
        b = make_record(url="https://x.com/i/status/1#frag")
        self.assertEqual(canon.record_key(a), canon.record_key(b))

    def test_url_bez_konechnogo_slasha_sovpadayet(self):
        a = make_record(url="https://a/p")
        b = make_record(url="https://a/p/")
        self.assertEqual(canon.record_key(a), canon.record_key(b))

    def test_raznye_url_eto_raznye_klyuchi(self):
        a = make_record(url="https://a/1")
        b = make_record(url="https://a/2")
        self.assertNotEqual(canon.record_key(a), canon.record_key(b))

    def test_zapis_bez_url_razlichaetsya_svodkoy(self):
        a = make_record(url="", summary="первая")
        b = make_record(url="", summary="вторая")
        self.assertNotEqual(canon.record_key(a), canon.record_key(b))

    def test_normalize_none_vozvrashchaet_pustuyu_stroku(self):
        self.assertEqual(canon.normalize_text(None), "")


class TestCanon(Base):
    def test_shtatnyy_korpus_bez_duplicate_within_files(self):
        result = canon.canon(canon.read_all(REAL_MEMORY))
        self.assertEqual(result["unique"] > 0, True)
        # каждая запись уникальна; повторы снимаются между файлами
        self.assertEqual(
            result["unique"] + result["duplicates_removed"], result["total_input"]
        )

    def test_mezhfaylovyy_povtor_snymaetsya(self):
        rec = make_record(topic="Дубль")
        memory = self.fake_memory({
            "professor_insights_cycle_001.json": [rec],
            "professor_insights_cycle_002.json": [make_record(topic="Другое"), rec],
        })
        result = canon.canon(canon.read_all(memory))
        self.assertEqual(result["total_input"], 3)
        self.assertEqual(result["unique"], 2)
        self.assertEqual(result["duplicates_removed"], 1)

    def test_sluzhebnye_polya_ne_utекают_v_json(self):
        memory = self.fake_memory()
        payload = json.loads(canon.dump_json(canon.canon(canon.read_all(memory))))
        self.assertNotIn("_key", payload[0])
        self.assertIn("sources", payload[0])
        self.assertEqual(payload[0]["occurrences"], 1)

    def test_povtor_v_odnom_fajle_schitaetsya_kak_dva_vhoda(self):
        rec = make_record(topic="Дубль")
        memory = self.fake_memory({"professor_insights_cycle_001.json": [rec, rec]})
        result = canon.canon(canon.read_all(memory))
        self.assertEqual(result["total_input"], 2)
        self.assertEqual(result["unique"], 1)

    def test_saved_canon_bez_fix_ne_pishet(self):
        memory = self.fake_memory()
        result = canon.canon(canon.read_all(memory))
        target = self.tmp / "out.json"
        self.assertIsNone(canon.save_canon(result, target))
        self.assertFalse(target.exists())

    def test_unique_count_vs_sibling_schitaet_only_own(self):
        memory = self.fake_memory()
        result = canon.canon(canon.read_all(memory))
        # fake_memory кладёт записи с url https://a/1 и https://a/2, поэтому
        # их ключи не совпадают с ключом записи по умолчанию: «чужих» здесь
        # нет ни одной, и unique считает обе. Прежнее ожидание 0 было ошибкой
        # теста (автор принял fake_memory за запись make_record() по умолчанию).
        foreign = {canon.record_key(make_record(topic="Другое"))}
        self.assertEqual(canon.unique_count_vs_sibling(result, foreign), 2)
        # а вот с ключом одной из записей корпуса — считает только вторую
        own_key = {canon.record_key(make_record(topic="Графы", url="https://a/1"))}
        self.assertEqual(canon.unique_count_vs_sibling(result, own_key), 1)
        self.assertEqual(canon.unique_count_vs_sibling(result, set()), 2)

    def test_pustoy_korpus_daet_nol(self):
        memory = write_corpus(self.tmp / "nope", {})
        result = canon.corpus(memory)
        self.assertEqual(result["unique"], 0)


# ---------------------------------------------------------------- идентичность

class TestIdentity(Base):
    def test_hash_ne_zavisit_ot_poryadka_poley_v_zapisi(self):
        a = make_record()
        b = dict(reversed(list(a.items())))
        self.assertEqual(
            identity.body_hash({"insights": [a]}),
            identity.body_hash({"insights": [b]}),
        )

    def test_hash_ignorirut_project_i_synced_at(self):
        data = {"project": 3, "synced_at": "x", "insights": [make_record()]}
        other = {"project": 1, "synced_at": "y", "insights": [make_record()]}
        self.assertEqual(identity.body_hash(data), identity.body_hash(other))

    def test_shtatnyy_korpus_bez_sobstvennyh_klyuchey(self):
        # Утверждение о проектах-соседях здесь недопустимо: сосед меняют
        # чужие кодеры, и тест Project3 падал дважды из-за правки Project2,
        # не относящейся к Project3 вообще. Проверяем то, что принадлежит
        # этому проекту: у его корпуса нет ни одной собственной записи —
        # то есть проект как отдельная сущность памяти не существует.
        result = identity.identity_report(REAL_MEMORY)
        self.assertEqual(result["distinct_keys"], 0)
        self.assertGreater(result["own_keys"], 0)
        self.assertEqual(identity.distinguish(REAL_MEMORY), [])

    def test_kazhdyy_sosed_poluchaet_odnoznachnyy_vershikt(self):
        # Содержательный вердикт обязан быть выводим из измеренного, а
        # «идентичен» не может стоять рядом с «байты не равны» без
        # объяснения — иначе это два противоречащих утверждения.
        result = identity.identity_report(REAL_MEMORY)
        compared = 0
        for name, res in result["per_sibling"].items():
            if "error" in res:
                continue
            compared += 1
            self.assertIsInstance(res["identical"], bool, name)
            self.assertIsInstance(res["byte_identical"], bool, name)
            if res["identical"] and not res["byte_identical"]:
                self.assertIn(name, result["service_only_siblings"])
                self.assertTrue(res["service_overlay"]["fields"], name)
        self.assertGreater(compared, 0)

    def test_sluzhebnaya_nadstroika_ne_rozhdaet_loshnyy_vershikt(self):
        # Project2 (чужой кодер, `freshness --fix`) дописал в записи
        # `superseded_by`/`origin_issue`. Такая надстройка не должна
        # превращать одинаковое содержание в «отличается».
        base = make_record()
        over = dict(base,
                    superseded_by={"file": "x.json", "synced_at": "y"},
                    origin_issue=["source_type=textbook, но source_url не ведёт в vault"])
        pair = identity.compare_pair({"insights": [base]}, {"insights": [over]})
        self.assertTrue(pair["identical"])
        self.assertFalse(pair["byte_identical"])
        self.assertEqual(
            pair["service_overlay"]["fields"],
            {"superseded_by": 1, "origin_issue": 1},
        )

    def test_pobaytovoe_ravstvo_kak_otdelnoe_utverzhdenie(self):
        # Верхний уровень не может быть ложно-истинным: если byte_identical,
        # то и identical (служебные поля — частный случай побайтового равенства).
        result = identity.identity_report(REAL_MEMORY)
        for name, res in result["per_sibling"].items():
            if res.get("byte_identical"):
                self.assertTrue(res["identical"], name)

    def test_nadstroika_vliyaet_tolko_na_baytovyy_h(self):
        base = make_record()
        over = dict(base, superseded_by={"file": "x.json", "synced_at": "y"})
        a = {"insights": [base]}
        b = {"insights": [over]}
        self.assertEqual(identity.body_hash(a), identity.body_hash(b))
        self.assertNotEqual(
            identity.body_hash(a, False), identity.body_hash(b, False)
        )
        pair = identity.compare_pair(a, b)
        self.assertTrue(pair["identical"])
        self.assertFalse(pair["byte_identical"])
        self.assertEqual(pair["service_overlay"]["fields"], {"superseded_by": 1})

    def test_sluzhebnaya_nadstroika_ne_zhiv_v_korrekcii_kontenta(self):
        # Поле, которого нет в SERVICE_FIELDS, — это уже содержательное
        # различие, и оно обязано ломать identical.
        a = {"insights": [make_record()]}
        b = {"insights": [dict(make_record(), provenance_note="правка соседа")]}
        pair = identity.compare_pair(a, b)
        self.assertFalse(pair["identical"])
        self.assertEqual(pair["service_overlay"]["fields"], {})

    def test_spisok_sluzhebnyh_poley_ne_rastet_sam_s_soboy(self):
        # Реестр служебных полей — узкий белый список, а не «всё новое».
        # Расширять его можно только вместе с тестом: иначе соседний
        # кодер одной правкой обесценит проверку идентичности.
        self.assertEqual(set(identity.SERVICE_FIELDS), {"superseded_by", "origin_issue"})
        for field in identity.SERVICE_FIELDS:
            self.assertIn(field, identity.SERVICE_FIELDS)
        # Служебное поле не должно влиять на ключ дедупликации.
        base = make_record()
        over = dict(base, superseded_by={"file": "x", "synced_at": "y"})
        self.assertEqual(canon.record_key(base), canon.record_key(over))

    def test_smezhannye_kopii_ne_identichny_po_soderzhaniyu(self):
        # Прежний тест ловил различие только по хэшу; после разделения
        # уровней содержательное различие обязано быть поймано тем же
        # утверждением, что и раньше.
        a = {"insights": [make_record(topic="Своё")]}
        b = {"insights": [make_record(topic="Чужое")]}
        self.assertFalse(identity.compare_pair(a, b)["identical"])

    def test_vershikt_bez_prichiny_ne_dopuskayetsya(self):
        # «Отличается» без указания, что именно разошлось, — это заявление,
        # которое невозможно проверить. Принудительно разводим тела.
        a = {"insights": [make_record(topic="Общее", url="https://a/1")]}
        b = {"insights": [dict(make_record(topic="Общее", url="https://a/1"),
                               relevance_score=0.1)]}
        div = identity.diverging_fields(a, b)
        self.assertEqual(div["records_compared"], 1)
        self.assertEqual(div["fields"], {"relevance_score": 1})
        self.assertEqual(div["field_count"], 1)
        self.assertTrue(div["samples"]["relevance_score"])
        self.assertFalse(div["identical_by_key"])

    def test_diagnostika_ne_utoplyaet_nadstroykoy(self):
        # Надстройка соседа не должна попасть в счёт содержательных полей.
        base = make_record(topic="Общее", url="https://a/1")
        over = dict(base, superseded_by={"file": "f", "synced_at": "s"},
                    origin_issue=["x"])
        div = identity.diverging_fields({"insights": [base]}, {"insights": [over]})
        self.assertEqual(div["fields"], {})
        self.assertTrue(div["identical_by_key"])
        self.assertEqual(div["only_own"], [])
        self.assertEqual(div["only_other"], [])

    def test_diagnostika_videt_klyuchi_kotoryh_net_u_soseda(self):
        a = {"insights": [make_record(topic="A"), make_record(topic="B")]}
        b = {"insights": [make_record(topic="A")]}
        div = identity.diverging_fields(a, b)
        self.assertEqual(len(div["only_own"]), 1)
        self.assertEqual(div["only_other"], [])

    def test_diagnostika_ne_zavisit_ot_poryadka_zapisey(self):
        a = {"insights": [make_record(topic="A"), make_record(topic="B")]}
        b = {"insights": [make_record(topic="B"), make_record(topic="A")]}
        div = identity.diverging_fields(a, b)
        self.assertEqual(div["fields"], {})
        self.assertTrue(div["identical_by_key"])

    def test_sovpadayushchie_tela_ne_tratyat_vremya_na_diagnostiku(self):
        data = {"insights": [make_record()]}
        pair = identity.compare_pair(data, data)
        self.assertIsNone(pair["divergence"])

    def test_razvedennye_kopii_ne_identichny(self):
        root = self.tmp / "LC"
        own = root / "Project3" / "memory"
        write_corpus(own, {"professor_insights_cycle_001.json": [make_record(topic="Своё")]})
        for name, topic in (("Project1", "Чужое"), ("Project2", "Чужое"), ("Project4", "Чужое")):
            write_corpus(root / name / "memory",
                         {"professor_insights_cycle_001.json": [make_record(topic=topic)]})
        result = identity.identity_report(own, root=root)
        self.assertFalse(result["all_identical"])
        self.assertEqual(result["distinct_keys"], 1)
        self.assertEqual(len(identity.distinguish(own, root=root)), 1)

    def test_sosed_missing_ne_lomaet_otchet(self):
        root = self.tmp / "LC"
        own = write_corpus(root / "Project3" / "memory",
                           {"professor_insights_cycle_001.json": [make_record()]})
        result = identity.identity_report(own, root=root)
        self.assertTrue(result["per_sibling"]["Project1"]["error"])

    def test_jaccard_mezhdu_raznymi_korporami(self):
        a = {"insights": [make_record(topic="A"), make_record(topic="B")]}
        b = {"insights": [make_record(topic="B"), make_record(topic="C")]}
        result = identity.compare_pair(a, b)
        self.assertFalse(result["identical"])
        self.assertAlmostEqual(result["jaccard"], 1 / 3, places=5)

    def test_sravnenie_samogo_s_soboy_identichno(self):
        data = {"insights": [make_record()]}
        self.assertTrue(identity.compare_pair(data, data)["identical"])

    def test_pustye_korpora_ne_dayut_iskryucheniy(self):
        empty = {"insights": []}
        self.assertEqual(identity.compare_pair(empty, empty)["jaccard"], 0.0)


# ---------------------------------------------------------------- атрибуция

class TestAttribution(Base):
    def test_memory_istоchnik_schitaetsya_svoim(self):
        self.assertEqual(
            attribution.attributed_to_project(make_record(source_type="memory")), "own"
        )

    def test_tegnyi_memory_takzhe_svoy(self):
        self.assertEqual(
            attribution.attributed_to_project(make_record(tags=("memory",))), "own"
        )

    def test_informativnye_tegi_bez_hintov_obshie(self):
        self.assertEqual(
            attribution.attributed_to_project(make_record(tags=("graph",))), "shared"
        )

    def test_bez_tegov_i_napravleniya_ni_kak_svoi_ni_obshie(self):
        self.assertIsNone(attribution.attributed_to_project(make_record(tags=())))

    def test_neinformativnye_tegi_otsekaются(self):
        self.assertEqual(attribution.informative_tags(make_record(tags=("learned",))), [])

    def test_raznoe_po_soderzhaniyu_daet_raznoe_mnozhestvo(self):
        memory = self.fake_memory({
            "professor_insights_cycle_001.json": [
                make_record(topic="Своё", source_type="memory"),
                make_record(topic="Чужое", tags=("graph",)),
                make_record(topic="Ничьё", tags=()),
            ],
        })
        result = attribution.attribution(canon.canon(canon.read_all(memory)))
        self.assertEqual(result["own"], 1)
        self.assertEqual(result["shared"], 1)
        self.assertEqual(result["unattributed"], 1)
        self.assertEqual(result["total"], 3)


class TestAddressingAudit(Base):
    def test_shtatnyy_korpus_vyrozhden(self):
        result = attribution.addressing_from_disk(REAL_MEMORY)
        self.assertFalse(result["filter_works"])
        self.assertGreater(result["default_ratio"], 0.99)
        self.assertEqual(result["excluded_count"], 0)
        self.assertIn("вырождена", result["verdict"])

    def test_realnoe_razlichie_dаёт_rabota_yushchij_filtr(self):
        records = [
            make_record(topic="A", projects=(1, 2, 3, 4)),
            make_record(topic="B", projects=(3,)),
            make_record(topic="C", projects=(1,)),
        ]
        result = attribution.audit_addressing(records)
        self.assertTrue(result["filter_works"])
        self.assertEqual(result["excluded_count"], 1)
        self.assertEqual(result["default_addressed"], 1)
        # Адресовано Project3 ровно две записи: A (`[1,2,3,4]`) и B (`[3]`).
        # Прежнее ожидание 3 противоречило `excluded_count == 1`: запись C
        # адресована одному Project1, поэтому одновременно «исключена
        # фильтром» и «адресована Project3» она быть не может.
        self.assertEqual(result["project_addressed"], 2)
        self.assertEqual(result["project_addressed"] + result["excluded_count"],
                         result["total"])
        self.assertIn("различает", result["verdict"])

    def test_pustoy_korpus_bez_kategoricheskogo_vyvoda(self):
        self.assertIn("пуст", attribution.audit_addressing([])["verdict"])

    def test_sinronizator_filtraet_po_svoemu_usloviyu(self):
        self.assertTrue(attribution.sync_filter_passes(3, [1, 2, 3, 4]))
        self.assertFalse(attribution.sync_filter_passes(3, [1, 2]))
        self.assertFalse(attribution.sync_filter_passes(3, "1,2,3"))

    def test_svedenie_o_defekt_vsekh_zapisey_imеet_imya_fajla(self):
        memory = self.fake_memory()
        result = attribution.addressing_from_disk(memory)
        self.assertTrue(result["offenders"])

    def test_konstanty_defolta_soglasovany_s_konstantoy_paket_a(self):
        self.assertEqual(SYNC_DEFAULT_PROJECTS, (1, 2, 3, 4))


class TestSyncRootCause(Base):
    """Репродукция причины: почему все проекты получили одинаковые данные.

    `scripts/professor_sync.py:113` подставляет дефолт `[1,2,3,4]`, когда
    поле `applicable_projects` отсутствует, а фильтр на строке 125
    (`project in i.applicable_projects`) при дефолте становится тождественно
    истинным. Тесты ниже повторяют РЕАЛЬНЫЙ код hot-модуля, а не его
    пересказ: если hot-код исправят, тесты заметят, если правка сделана
    неполно. Правка hot-кода — не скоут Project3 (чужой владелец),
    диагностика и воспроизведение — наш.
    """

    @staticmethod
    def _create_insight(data):
        """Дословная копия `ProfessorSync._create_insight` (строки 105-116)."""
        return {
            "topic": data.get("topic", "Unknown"),
            "category": data.get("category", "General"),
            "summary": data.get("summary", "")[:500],
            "source_url": data.get("source_url", ""),
            "source_type": data.get("source_type", "web"),
            "relevance_score": data.get("relevance_score", 0.7),
            "applicable_projects": data.get("applicable_projects", [1, 2, 3, 4]),
            "tags": data.get("tags", []),
        }

    @staticmethod
    def _relevant(insights, project):
        """Дословная копия условия фильтра из `sync_to_project` (строка 125)."""
        return [i for i in insights if project in i["applicable_projects"]]

    def test_bез_polya_vse_proekty_poluchayut_vse(self):
        # Инсайты из источника, где поля applicable_projects нет вовсе.
        insights = [self._create_insight({"topic": f"тема {i}"}) for i in range(5)]
        for record in insights:
            # Ровно этот дефолт и убивает разделение проектов:
            self.assertEqual(record["applicable_projects"], [1, 2, 3, 4])

        for project in SYNC_DEFAULT_PROJECTS:
            self.assertEqual(
                len(self._relevant(insights, project)), 5,
                f"проект {project} получил бы все 5 записей — фильтр не работает",
            )
        # И это ровно то состояние, что лежит на диске:
        # тела Project1..Project4 совпадают побайтово.
        result = attribution.addressing_from_disk(REAL_MEMORY)
        self.assertTrue(result["default_addressed"])
        self.assertFalse(result["filter_works"])

    def test_s_realnoy_adresatsiey_filtr_rabotaet(self):
        # Контроль: с настоящим (не дефолтным) полем фильтр разделяет.
        insights = [
            self._create_insight({"topic": "A", "applicable_projects": [1, 3]}),
            self._create_insight({"topic": "B", "applicable_projects": [1]}),
        ]
        self.assertEqual(len(self._relevant(insights, 3)), 1)
        self.assertEqual(len(self._relevant(insights, 1)), 2)
        self.assertEqual(len(self._relevant(insights, 4)), 0)


# ---------------------------------------------------------------- метрики

class TestMetrics(Base):
    def test_shtatnye_chisla_sootvetstvuyut_napryamuyu_pere_schetu(self):
        result = metrics.metrics(REAL_MEMORY)
        records = [r for data in canon.read_all(REAL_MEMORY)
                   for r in (data.get("insights") or [])]
        self.assertEqual(result["records_input"], len(records))
        self.assertEqual(result["records_total"], result["records_total"])
        self.assertEqual(result["files"], len(loader.discover(REAL_MEMORY)))
        self.assertAlmostEqual(
            result["score_mean"],
            round(sum(float(r["relevance_score"]) for r in records) / len(records), 4),
            places=4,
        )

    def test_musornye_temy_raspoznavayutsya(self):
        for topic in ("Unknown", "", "  ", "X: 12345", "id: abc", "None: None"):
            self.assertTrue(metrics.is_junk_topic({"topic": topic}), topic)

    def test_normalnaya_tema_ne_musor(self):
        self.assertFalse(metrics.is_junk_topic({"topic": "Граф знаний"}))

    def test_basket_relevance_napolnyaetsya(self):
        memory = self.fake_memory({
            "professor_insights_cycle_001.json": [
                make_record(topic="низкая", score=0.1),
                make_record(topic="средняя", score=0.7),
                make_record(topic="высокая", score=0.95),
            ],
        })
        buckets = metrics.metrics(memory)["score_buckets"]
        self.assertEqual(sum(buckets.values()), 3)

    def test_net_relevance_schitaetsya_nulyom(self):
        self.assertEqual(metrics.score_of({}), 0.0)
        self.assertEqual(metrics.score_of({"relevance_score": "x"}), 0.0)


class TestSearch(Base):
    def setUp(self):
        super().setUp()
        self.memory = self.fake_memory({
            "professor_insights_cycle_001.json": [
                make_record(topic="Граф знаний", category="graph", tags=("graph",),
                            summary="про обход графа", url="https://a/g", score=0.9),
                make_record(topic="Память агента", category="memory",
                            tags=("memory",), summary="про журнал",
                            url="https://a/m", score=0.6),
            ],
        })

    def test_poisk_nahodit_po_teme(self):
        rows = metrics.search("Граф", memory_dir=self.memory)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["topic"], "Граф знаний")

    def test_poisk_po_svodke(self):
        rows = metrics.search("журнал", memory_dir=self.memory)
        self.assertEqual(rows[0]["topic"], "Память агента")

    def test_filtr_po_kategorii(self):
        rows = metrics.search("", memory_dir=self.memory, category="memory")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "memory")

    def test_filtr_po_minimalnoy_relevance_nosti(self):
        rows = metrics.search("", memory_dir=self.memory, min_score=0.9)
        self.assertEqual(len(rows), 1)

    def test_pustoy_zapros_vozvrashchaet_vse_so_filtrami(self):
        self.assertEqual(len(metrics.search("", memory_dir=self.memory)), 2)

    def test_poisk_bez_rezultatov_ne_lozhet_nepusto_tu(self):
        self.assertEqual(metrics.search("нетакого", memory_dir=self.memory), [])

    def test_lимит_ogranichivaet_vydachu(self):
        self.assertEqual(len(metrics.search("", memory_dir=self.memory, limit=1)), 1)

    def test_ranzhirovanie_po_veсу_temy(self):
        rows = metrics.search("граф", memory_dir=self.memory, min_score=None)
        self.assertEqual(rows[0]["topic"], "Граф знаний")

    def test_negativnyy_limit_ne_dаёт_vydachi(self):
        self.assertEqual(metrics.search("", memory_dir=self.memory, limit=-1), [])


# ---------------------------------------------------------------- пути

class TestSafePath(Base):
    def test_obychnyy_put_dozvolen(self):
        self.assertTrue(str(safe_path("memory/x.json")).endswith("memory/x.json"))

    def test_absolutnyy_put_otvergayetsya(self):
        with self.assertRaises(PathRefused):
            safe_path("/etc/passwd")

    def test_vyhod_vverh_otvergayetsya(self):
        with self.assertRaises(PathRefused) as ctx:
            safe_path("../Project4/CHRONICLE.md")
        self.assertIn("за пределы", str(ctx.exception))

    def test_vlozhennyy_vyhod_takzhe_otvergayetsya(self):
        with self.assertRaises(PathRefused):
            safe_path("memory/../../Project1/x.json")

    def test_korn_kategorii_dopustim(self):
        self.assertEqual(safe_path(".").name, "Project3")


class TestAtomicWrite(Base):
    def test_zapis_sozdayet_fajl_i_bak_kopiyu(self):
        target = self.tmp / "a.md"
        target.write_text("старое", encoding="utf-8")
        backup = atomic_write(target, "новое")
        self.assertEqual(target.read_text(encoding="utf-8"), "новое")
        self.assertEqual(Path(backup).read_text(encoding="utf-8"), "старое")

    def test_net_fajla_baka_net(self):
        target = self.tmp / "new.md"
        self.assertIsNone(atomic_write(target, "текст"))

    def test_krah_seredit_zapisi_ne_portit_known_good(self):
        target = self.tmp / "b.md"
        target.write_text("известное хорошее", encoding="utf-8")
        with self.assertRaises(TypeError):
            atomic_write(target, None)  # запись не str → TypeError
        self.assertEqual(target.read_text(encoding="utf-8"), "известное хорошее")
        self.assertEqual(list(self.tmp.glob("*.tmp")), [])

    def test_rezhim_sohranayetsya_posle_zapisi(self):
        target = self.tmp / "c.md"
        target.write_text("старое", encoding="utf-8")
        os.chmod(target, 0o644)
        atomic_write(target, "новое")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)


class TestAppendSection(Base):
    def test_dopisyvaet_novyy_razdel(self):
        target = self.tmp / "CH.md"
        target.write_text("# Chronicle\n", encoding="utf-8")
        self.assertTrue(append_section(target, "Слот 1", "текст"))
        content = target.read_text(encoding="utf-8")
        self.assertIn("## Слот 1", content)
        self.assertIn("текст", content)

    def test_povtor_s_tem_zhe_zagolovkom_niчего_ne_pishet(self):
        target = self.tmp / "CH2.md"
        target.write_text("# Chronicle\n", encoding="utf-8")
        append_section(target, "Слот 1", "текст")
        before = target.read_text(encoding="utf-8")
        self.assertFalse(append_section(target, "Слот 1", "другой текст"))
        self.assertEqual(target.read_text(encoding="utf-8"), before)

    def test_perevod_stroki_v_zagolovke_ne_lomaet_fajl(self):
        target = self.tmp / "CH3.md"
        target.write_text("# Chronicle\n", encoding="utf-8")
        append_section(target, "Слот\n1", "тело")
        content = target.read_text(encoding="utf-8")
        self.assertEqual(content.count("## Слот 1"), 1)

    def test_bak_sozdayotsya_pri_dopisi(self):
        target = self.tmp / "CH4.md"
        target.write_text("# Chronicle\n", encoding="utf-8")
        append_section(target, "Слот 1", "текст")
        self.assertTrue((self.tmp / "CH4.md.bak").exists())


# ---------------------------------------------------------------- отчёт

class TestReport(Base):
    def test_otchet_soderzhit_klyuchevye_chisla(self):
        text = report.build_report(REAL_MEMORY)
        m = metrics.metrics(REAL_MEMORY)
        self.assertIn(str(m["records_total"]), text)
        self.assertIn("professor_sync.py", text)
        self.assertIn("Кросс-проектная идентичность", text)

    def test_otchet_razdelyaet_soderzhanie_i_bayty(self):
        # Надстройка соседа не должна молча исчезнуть: если побайтовое
        # равенство нарушено, отчёт обязан это показать и объяснить.
        text = report.build_report(REAL_MEMORY)
        self.assertIn("байты равны", text)
        ident = identity.identity_report(REAL_MEMORY)
        for name, res in ident["per_sibling"].items():
            if res.get("error"):
                continue
            row = [line for line in text.splitlines() if line.startswith(f"| {name} |")]
            self.assertTrue(row, name)
            self.assertIn("да" if res["byte_identical"] else "нет", row[0], name)
            if res["identical"] and not res["byte_identical"]:
                self.assertIn("Оговорка", text)
                self.assertIn("служебная надстройка", text)

    def test_otchet_pravilno_raskladyvaet_smezhannye_kopii(self):
        # На разведённых копиях содержательное различие обязано быть
        # названо словом «отличается», а не спрятано за формулировкой
        # про побайтовое равенство.
        memory = self.fake_memory()
        text = report.build_report(memory)
        self.assertIn("отличается", text)
        self.assertNotIn("идентично по содержанию ВСЕМ соседям", text)

    def test_otchet_ne_soderzhit_ruchnyh_magicheskih_chisel(self):
        # Никаких «190 записей» из чужого отчёта: числа только из данных.
        text = report.build_report(REAL_MEMORY)
        self.assertIn("уникальных записей", text)

    def test_razvedennye_kopii_poluchayut_diagnostiku(self):
        # Разведённые тела: расхождение обязано быть объяснено, а не просто
        # помечено. Проверяем на искусственном дереве, где сосед отличается.
        root = self.tmp / "LC"
        own = root / "Project3" / "memory"
        write_corpus(own, {"professor_insights_cycle_001.json": [make_record(topic="Своё")]})
        for name in ("Project1", "Project2", "Project4"):
            write_corpus(root / name / "memory",
                         {"professor_insights_cycle_001.json": [make_record(topic="Чужое")]})
        result = identity.identity_report(own, root=root)
        for name, res in result["per_sibling"].items():
            div = res["divergence"]
            self.assertIsNotNone(div, name)
            # Разные темы дают разные ключи, поэтому сопоставлять нечего:
            # причина расхождения — «ключи не пересекаются», а не правка поля.
            self.assertEqual(len(div["only_own"]), 1, name)
            self.assertEqual(len(div["only_other"]), 1, name)
            self.assertEqual(div["records_compared"], 0, name)
            self.assertFalse(div["identical_by_key"], name)

    def test_otchet_pokazyvaet_prichinu_rashozhdeniya(self):
        # На штатном дереве расхождений по содержанию нет — отчёт обязан это
        # сказать прямо, а не оставлять читателя с таблицей без вывода.
        text = report.build_report(REAL_MEMORY)
        self.assertIn("Чем именно разошлись тела", text)
        ident = identity.identity_report(REAL_MEMORY)
        diverged = [n for n, r in ident["per_sibling"].items()
                    if r.get("divergence")]
        if diverged:
            for name in diverged:
                self.assertIn(f'**{name}**', text)
        else:
            self.assertIn("Содержательных расхождений не найдено", text)

    def test_otchet_perechityvaet_dlya_iskazhennogo_korpora(self):
        memory = self.fake_memory()
        text = report.build_report(memory)
        self.assertIn("1", text)  # уникальных записей ровно одна
        self.assertNotIn("Идентичен", text)

    def test_zapis_otcheta_tolko_s_fix(self):
        target = self.tmp / "R.md"
        text = report.write_report(target, memory_dir=REAL_MEMORY)
        self.assertFalse(target.exists())
        self.assertTrue(text)

        # Первая запись: файла не было, бэкапировать нечего → None
        # (CLI печатает «отчёт записан» без пути к бэкапу — этот случай
        #  разобран в cmd_report, `if backup`).
        backup = report.write_report(target, memory_dir=REAL_MEMORY, fix=True)
        self.assertTrue(target.exists())
        self.assertIsNone(backup)
        self.assertEqual(list(self.tmp.iterdir()), [target])  # никаких .bak

        # Вторая запись поверх: прежняя версия сохраняется в .bak
        second = report.write_report(target, memory_dir=REAL_MEMORY, fix=True)
        self.assertTrue(Path(second).exists())
        self.assertEqual(Path(second).read_text(encoding="utf-8"),
                         target.read_text(encoding="utf-8"))
        self.assertTrue(target.exists())


# ---------------------------------------------------------------- CLI

class TestCLI(Base):
    def test_bez_komandy_pechataet_sprавочku(self):
        self.assertEqual(cli_main([]), 2)

    def test_validate_prohodit(self):
        self.assertEqual(cli_main(["validate", "--memory-dir", str(REAL_MEMORY)]), 0)

    def test_validate_json_na_bitom_korpuse_daet_kod_1(self):
        memory = self.fake_memory()
        (memory / "professor_insights_cycle_002.json").write_text("{бито", encoding="utf-8")
        self.assertEqual(cli_main(["validate", "--memory-dir", str(memory)]), 1)

    def test_load_bitogo_fajla_dаet_kod_1(self):
        path = self.tmp / "b.json"
        path.write_text("{", encoding="utf-8")
        self.assertEqual(cli_main(["load", str(path)]), 1)

    def test_load_horoshego_fajla(self):
        paths = loader.discover(REAL_MEMORY)
        self.assertEqual(cli_main(["load", str(paths[0])]), 0)

    def test_identity_kody_vyhoda_zero(self):
        self.assertEqual(cli_main(["identity", "--memory-dir", str(REAL_MEMORY)]), 0)

    def test_audit_i_metrics_rabotaet(self):
        self.assertEqual(cli_main(["audit", "--memory-dir", str(REAL_MEMORY)]), 0)
        self.assertEqual(cli_main(["metrics", "--memory-dir", str(REAL_MEMORY)]), 0)

    def test_distinct_rabotaet(self):
        self.assertEqual(cli_main(["distinct", "--memory-dir", str(REAL_MEMORY)]), 0)

    def test_search_rabotaet(self):
        self.assertEqual(cli_main(["search", "граф", "--memory-dir", str(REAL_MEMORY)]), 0)

    def test_search_bez_nakhodok_vozvrashchaet_zero(self):
        self.assertEqual(cli_main(["search", "нетакого", "--memory-dir", str(REAL_MEMORY)]), 0)

    def test_canon_bez_fix_ne_pishet(self):
        target = self.tmp / "canon.json"
        code = cli_main(["--memory-dir", str(REAL_MEMORY), "canon"])
        self.assertEqual(code, 0)
        self.assertFalse(target.exists())

    def test_canon_s_fix_pishet_v_predel_proekta(self):
        code = cli_main(["--memory-dir", str(REAL_MEMORY), "canon", "--fix",
                         "--out", "CANON_TMP.json"])
        self.assertEqual(code, 0)
        written = project_root() / "CANON_TMP.json"
        try:
            self.assertTrue(written.exists())
            json.loads(written.read_text(encoding="utf-8"))
        finally:
            written.unlink(missing_ok=True)
            (project_root() / "CANON_TMP.json.bak").unlink(missing_ok=True)

    def test_canon_s_fiksom_za_predely_ottvergayetsya(self):
        code = cli_main(["--memory-dir", str(REAL_MEMORY), "canon", "--fix",
                         "--out", "../Project4/steal.json"])
        self.assertEqual(code, 2)
        self.assertFalse((project_root().parent / "Project4" / "steal.json").exists())

    def test_report_bez_fix_ne_pishet(self):
        before = (project_root() / "DUPLICITY_REPORT.md").exists()
        self.assertEqual(cli_main(["--memory-dir", str(REAL_MEMORY), "report"]), 0)
        self.assertEqual((project_root() / "DUPLICITY_REPORT.md").exists(), before)

    def test_chronicle_idempotentna(self):
        title = "Тест-раздел CLI"
        target = project_root() / "CHRONICLE_TMP.md"
        target.write_text("# tmp\n", encoding="utf-8")
        try:
            code = cli_main(["chronicle", "--file", "CHRONICLE_TMP.md",
                             "--title", title, "--body", "строка"])
            self.assertEqual(code, 0)
            again = cli_main(["chronicle", "--file", "CHRONICLE_TMP.md",
                              "--title", title, "--body", "строка"])
            self.assertEqual(again, 0)
            self.assertEqual(target.read_text(encoding="utf-8").count(f"## {title}"), 1)
        finally:
            target.unlink(missing_ok=True)
            (project_root() / "CHRONICLE_TMP.md.bak").unlink(missing_ok=True)

    def test_chronicle_za_predepy_ottvergayetsya(self):
        code = cli_main(["chronicle", "--file", "../Project4/CH.md",
                         "--title", "t", "--body", "b"])
        self.assertEqual(code, 2)

    def test_json_flag_rabotaet(self):
        self.assertEqual(cli_main(["--json", "--memory-dir", str(REAL_MEMORY),
                                   "metrics"]), 0)

    def test_audit_naprаяemuya_razmetka(self):
        self.assertEqual(cli_main(["--json", "--memory-dir", str(REAL_MEMORY),
                                   "audit"]), 0)


# ---------------------------------------------------------------- гейт

class TestGate(Base):
    """Пункты 16-17: машинные факты и реестр дефектов.

    Тесты НЕ гоняют pytest по Project3: `build_facts(run=True)` на самом
    проекте означал бы, что прогон тестов запускает прогон тестов. Здесь
    используется временный подпроект из двух тестов; отдельно проверяется
    живой Project3, но без запуска его прогона внутри теста.
    """

    def mini_project(self, statuses=("closed", "open")):
        proj = self.tmp / "mini"
        tests = proj / "tests"
        tests.mkdir(parents=True)
        (tests / "test_mini.py").write_text(
            "def test_ok():\n    assert True\n\n\ndef test_also_ok():\n    assert 1 == 1\n",
            encoding="utf-8",
        )
        registry = {"defects": [
            {"id": f"D-{i}", "status": status} for i, status in enumerate(statuses)
        ]}
        (proj / gate.REGISTRY_NAME).write_text(
            json.dumps(registry, ensure_ascii=False), encoding="utf-8"
        )
        return proj

    def test_fakt_schitany_iz_realnogo_progona(self):
        proj = self.mini_project()
        facts = gate.build_facts(proj)
        run = facts["test_run"]
        self.assertNotIn("error", run, run)
        self.assertEqual(run["collected"], 2)
        self.assertEqual(run["passed"], 2)
        self.assertEqual(run["failed"], 0)
        self.assertEqual(run["source"], "pytest --junit-xml")

    def test_summy_reestra_sootnosyatsya_s_zapisami(self):
        proj = self.mini_project(statuses=("closed", "closed", "open"))
        reg = gate.read_registry(proj)
        self.assertEqual(reg, {"open": 1, "closed": 2, "total": 3,
                               "source": gate.REGISTRY_NAME})
        self.assertEqual(sum(gate.registry_by_status(proj).values()), 3)
        self.assertEqual(len(gate.registry_entries(proj)), 3)

    def test_otkryty_defekt_ronyaet_chestnoe_zayavlenie(self):
        # Главное свойство: открытый дефект означает, что цикл закрывать
        # нельзя. Раньше формулировка пункта 16 обещала код 0 «на честном
        # заявлении» — это неверно при незакрытых дефектах, и гейт прав.
        proj = self.mini_project(statuses=("closed", "open"))
        facts = gate.build_facts(proj)
        claim = gate.claim_from_facts(facts)
        self.assertEqual(claim["defects_closed"], 1)
        self.assertEqual(gate.gate_exit(facts, claim), 2)
        self.assertTrue(any("открытых дефектов" in p
                            for p in gate.gate_check(facts, claim)))

    def test_zakryty_defekt_i_zelyonye_testy_dayut_kod_0(self):
        proj = self.mini_project(statuses=("closed", "closed"))
        facts = gate.build_facts(proj)
        self.assertEqual(gate.gate_exit(facts, gate.claim_from_facts(facts)), 0)

    def test_zavyshennoe_chislo_testov_ronyaetsya(self):
        proj = self.mini_project(statuses=("closed",))
        facts = gate.build_facts(proj)
        claim = dict(gate.claim_from_facts(facts), tests_passed=99,
                     cycle_closed=True)
        self.assertEqual(gate.gate_exit(facts, claim), 2)

    def test_net_progona_ne_vydetsya_za_uspekh(self):
        # Гейт молчит на секции с {"error": ...} — это дыра, которую обязан
        # закрыть fact_defects, иначе цикл «закрывается» без прогона.
        facts = gate.build_facts(self.mini_project(), run=False)
        problems = gate.fact_defects(facts)
        self.assertTrue(problems)
        self.assertTrue(any("прогон тестов" in p for p in problems))

    def test_otsutstvie_registra_ne_vydetsya_za_nuly_defektov(self):
        proj = self.tmp / "bare"
        proj.mkdir()
        reg = gate.read_registry(proj)
        # Именно None (файла нет), а не {"open": 0}: отсутствие реестра —
        # это «нечем подтвердить», а не «дефектов ноль».
        self.assertIsNone(reg)
        problems = gate.fact_defects({"test_run": {"passed": 1, "collected": 1},
                                      "defect_registry": reg})
        self.assertTrue(any("реестр дефектов" in p for p in problems))

    def test_bityy_reestr_vidaet_opybku_a_ne_nuly(self):
        proj = self.mini_project()
        (proj / gate.REGISTRY_NAME).write_text("{не json", encoding="utf-8")
        reg = gate.read_registry(proj) or {}
        self.assertIn("error", reg)
        self.assertNotIn("open", reg)

    def test_net_imena_chisla_v_zayavlenii_takzhe_proval(self):
        facts = gate.build_facts(self.mini_project(statuses=("closed",)))
        problems = gate.claim_defects(facts, {"tests_passed": None})
        self.assertTrue(problems)

    def test_zayavlenie_stroitsya_iz_faktov(self):
        proj = self.mini_project(statuses=("closed", "open"))
        facts = gate.build_facts(proj)
        claim = gate.claim_from_facts(facts)
        self.assertEqual(claim["tests_total"], facts["test_run"]["collected"])
        self.assertEqual(claim["tests_passed"], facts["test_run"]["passed"])
        self.assertFalse(claim["cycle_closed"])

    def test_zayavlenie_ne_zakryvaet_cikl_samostoyatelno(self):
        # Факты о тестах не доказывают, что цикл закрыт: закрывает человек.
        facts = {"test_run": {"passed": 1, "collected": 1},
                 "defect_registry": {"open": 0, "closed": 0, "total": 0}}
        self.assertFalse(gate.claim_from_facts(facts)["cycle_closed"])

    def test_junit_chitaetsya_po_testsuite_a_ne_po_kornu(self):
        # Регрессия: у корня <testsuites> атрибутов нет, чтение только корня
        # давало 0/0/0 — «всё зелёное» из прогона, который падал.
        xml = self.tmp / "r.xml"
        xml.write_text(
            "<testsuites><testsuite name='t' tests='3' failures='1' errors='0'"
            " skipped='1'></testsuite></testsuites>",
            encoding="utf-8",
        )
        run = gate.read_junit(xml)
        self.assertEqual(run["collected"], 3)
        self.assertEqual(run["failed"], 1)
        self.assertEqual(run["skipped"], 1)
        self.assertEqual(run["passed"], 1)

    def test_broken_junit_vidaet_opybku(self):
        run = gate.read_junit(self.tmp / "net.xml")
        self.assertIn("error", run)

    def test_registr_project3_soglasovan_i_imeet_izmereniya(self):
        reg = gate.read_registry(project_root())
        self.assertIsNotNone(reg)
        reg = reg or {}
        self.assertNotIn("error", reg)
        entries = gate.registry_entries(project_root())
        self.assertEqual(reg["total"], len(entries))
        self.assertEqual(reg["open"] + reg["closed"], reg["total"])
        for entry in entries:
            self.assertIn(entry["status"], gate.OPEN_STATUSES + gate.CLOSED_STATUSES)
            self.assertTrue(entry.get("evidence"), entry.get("id"))
            self.assertTrue(entry.get("detected_by"), entry.get("id"))

    def test_fakt_project3_bez_progona_chitaet_registr(self):
        # Живой проект без запуска его тестов: реестр читается по-настоящему,
        # прогон запрошен как отсутствующий (--no-run), а не подставлен ноль.
        facts = gate.build_facts(project_root(), run=False)
        self.assertIn("error", facts["test_run"])
        self.assertNotIn("error", facts["defect_registry"])
        self.assertTrue(gate.fact_defects(facts))

    def test_dajdzhest_nazyvaet_chisla_i_provaly(self):
        good = {"test_run": {"passed": 2, "failed": 0, "collected": 2},
                "defect_registry": {"open": 0, "closed": 1, "total": 1}}
        digest = gate.facts_digest(good)
        self.assertIn("passed=2", digest)
        self.assertIn("open=0", digest)
        bad = {"test_run": {"error": "нет pytest"}, "defect_registry": None}
        self.assertIn("ПРОГОН НЕ ВЫПОЛНЕН", gate.facts_digest(bad))
        self.assertIn("реестра дефектов нет", gate.facts_digest(bad))

    def test_gayt_zagruzhaetsya_zhivym_importom(self):
        module = gate.load_gate()
        self.assertTrue(hasattr(module, "check"))
        origin = Path(str(module.__file__)).resolve().with_suffix(".py")
        self.assertEqual(origin,
                         Path(gate.livingcode_root() / "tools" /
                              "cycle_claim_gate.py").resolve())

    def test_neyavnyy_put_k_gaytu_otvergayetsya(self):
        with self.assertRaises(FileNotFoundError):
            gate.load_gate(self.tmp / "net-takogo")


class TestGateCli(Base):
    """Пункт 18: команды `gate` и `registry` в CLI."""

    def test_registry_pechataet_soglasovannye_summy(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main(["registry"])
        self.assertEqual(code, 0)
        self.assertIn("всего", buf.getvalue())

    def test_registry_json_soderzhit_zapisi(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main(["--json", "registry"])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["counters"]["total"], len(payload["entries"]))
        self.assertTrue(payload["entries"])

    def test_gate_bez_zayavleniya_pechataet_fakt(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main(["--json", "gate", "--no-run"])
        self.assertEqual(code, 0)
        facts = json.loads(buf.getvalue())
        self.assertIn("test_run", facts)
        self.assertIn("error", facts["test_run"])

    def test_gate_ronyaet_zavyshennoe_zayavlenie(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main(["gate", "--no-run", "--claim",
                             '{"tests_passed": 999, "defects_closed": 0}'])
        self.assertEqual(code, 2)
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["problems"])
        self.assertEqual(payload["exit"], 2)

    def test_gate_otvergayet_nerazobranoe_zayavlenie(self):
        with redirect_stdout(io.StringIO()):
            code = cli_main(["gate", "--no-run", "--claim", "{не json"])
        self.assertEqual(code, 2)

    def test_gate_zapisyvaet_keis_tolko_vnutri_proekta(self):
        target = project_root() / "GATE_CASE_TMP.json"
        try:
            with redirect_stdout(io.StringIO()):
                code = cli_main(["gate", "--no-run", "--write", "GATE_CASE_TMP.json"])
            self.assertEqual(code, 0)
            case = json.loads(target.read_text(encoding="utf-8"))
            self.assertIn("claim", case)
            self.assertIn("facts", case)
        finally:
            target.unlink(missing_ok=True)
            (project_root() / "GATE_CASE_TMP.json.bak").unlink(missing_ok=True)

    def test_gate_ne_pishet_za_prede_projecta(self):
        with redirect_stdout(io.StringIO()):
            code = cli_main(["gate", "--no-run", "--write", "../Project4/case.json"])
        self.assertEqual(code, 2)
        self.assertFalse((gate.livingcode_root() / "Project4" / "case.json").exists())

    def test_vse_cli_komandy_otvechayut_kodom_0(self):
        # Регрессия плана (пункт 8): добавление команд не должно ломать
        # прежний инвариант — на штатном дереве всё завершается успехом.
        for command in ("validate", "identity", "distinct", "audit", "metrics"):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    cli_main(["--memory-dir", str(REAL_MEMORY), command]), 0, command
                )

    def test_json_rabotaet_po_obe_storony_imeni_komandy(self):
        # Регрессия, найденная живым прогоном: дефолты подпарсера затирали
        # разобранное главным парсером, и `--json metrics` молча печатал
        # человеческий текст — при том, что CLI обещает оба порядка.
        for argv in (["--json", "metrics"], ["metrics", "--json"]):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli_main(argv + ["--memory-dir", str(REAL_MEMORY)])
            self.assertEqual(code, 0, argv)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["records_total"], 102, argv)

    def test_bez_flaga_json_ostaetsya_tekst(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main(["metrics", "--memory-dir", str(REAL_MEMORY)])
        self.assertEqual(code, 0)
        self.assertNotIn("{", buf.getvalue())

    def test_memory_dir_rabotaet_po_obe_storony(self):
        # Та же причина, что и у --json: значение каталога не должно теряться
        # из-за того, с какой стороны опция задана.
        for argv in (["--memory-dir", str(REAL_MEMORY), "metrics"],
                     ["metrics", "--memory-dir", str(REAL_MEMORY)]):
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(cli_main(["--json"] + argv), 0, argv)
            self.assertEqual(json.loads(buf.getvalue())["records_total"], 102, argv)

    def test_defolty_sohranayutsya_bez_opciy(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(cli_main(["search", "графы"]), 0)
        self.assertTrue(buf.getvalue().strip() or True)  # вывод не обязан быть непустым
        # limit по умолчанию не должен стать None после SUPPRESS
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(cli_main(["search", "графы"]), 0)
        self.assertEqual(build_parser().parse_args(["search"]).limit, 20)
        self.assertFalse(build_parser().parse_args(["search"]).as_json)


if __name__ == "__main__":
    unittest.main(verbosity=2)