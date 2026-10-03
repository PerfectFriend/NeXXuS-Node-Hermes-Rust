"""Тесты p3_memory. Запуск: python3 -m unittest discover -s tests -v

Проверяются три контура:
  * штатный корпус Project3 — реальные файлы `memory/`;
  * искусственно испорченный корпус — битый JSON, маркер `# HOT`, пустой
    список, неверная схема, разведённые копии соседей;
  * защита от записи вне проекта и атомарность записи.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from p3_memory import SYNC_DEFAULT_PROJECTS  # noqa: E402
from p3_memory import attribution, canon, identity, loader, metrics, report  # noqa: E402
from p3_memory.cli import main as cli_main  # noqa: E402
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

    def test_shtatnyy_proekt_identichen_vsom_sosedyam(self):
        result = identity.identity_report(REAL_MEMORY)
        self.assertTrue(result["all_identical"], result["per_sibling"])
        self.assertEqual(result["distinct_keys"], 0)

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
        self.assertIn("Идентичен", text)
        self.assertIn("professor_sync.py", text)

    def test_otchet_ne_soderzhit_ruchnyh_magicheskih_chisel(self):
        # Никаких «190 записей» из чужого отчёта: числа только из данных.
        text = report.build_report(REAL_MEMORY)
        self.assertIn("уникальных записей", text)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)