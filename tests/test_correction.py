import re
import tempfile
import unittest
from pathlib import Path

from correction import (
    CorrectionConfig,
    CustomTerm,
    RegexRule,
    FillerFilter,
    load_config,
    save_config,
)


class CustomTermTests(unittest.TestCase):
    def test_roundtrip(self):
        term = CustomTerm(term="数智办公", hint="项目名称")
        data = term.to_dict()
        restored = CustomTerm.from_dict(data)
        self.assertEqual(restored.term, "数智办公")
        self.assertEqual(restored.hint, "项目名称")

    def test_empty_hint(self):
        term = CustomTerm(term="API")
        self.assertEqual(term.hint, "")


class RegexRuleTests(unittest.TestCase):
    def test_applies_replacement(self):
        rule = RegexRule(pattern=r"\bA P I\b", replacement="API")
        self.assertEqual(rule.apply("使用 A P I 接口"), "使用 API 接口")

    def test_disabled_rule_does_nothing(self):
        rule = RegexRule(pattern=r"\bA P I\b", replacement="API", enabled=False)
        self.assertEqual(rule.apply("使用 A P I 接口"), "使用 A P I 接口")

    def test_invalid_pattern_raises(self):
        with self.assertRaises(re.error):
            RegexRule(pattern=r"[invalid", replacement="x")

    def test_roundtrip(self):
        rule = RegexRule(pattern=r"嗯", replacement="", description="清除语气词")
        data = rule.to_dict()
        restored = RegexRule.from_dict(data)
        self.assertEqual(restored.pattern, r"嗯")
        self.assertEqual(restored.replacement, "")
        self.assertTrue(restored.enabled)


class FillerFilterTests(unittest.TestCase):
    def test_filters_fillers(self):
        ff = FillerFilter(words=["嗯", "啊"])
        self.assertEqual(ff.filter("嗯 大家好 啊"), "大家好")

    def test_disabled_does_nothing(self):
        ff = FillerFilter(enabled=False, words=["嗯", "啊"])
        self.assertEqual(ff.filter("嗯 大家好 啊"), "嗯 大家好 啊")

    def test_empty_text(self):
        ff = FillerFilter()
        self.assertEqual(ff.filter(""), "")


class CorrectionConfigTests(unittest.TestCase):
    def test_build_initial_prompt_with_terms(self):
        config = CorrectionConfig(custom_terms=[
            CustomTerm("数智办公", "项目名称"),
            CustomTerm("K8s", "集群管理"),
        ])
        prompt = config.build_initial_prompt()
        self.assertIn("数智办公", prompt)
        self.assertIn("K8s", prompt)

    def test_build_initial_prompt_empty_terms(self):
        config = CorrectionConfig(custom_terms=[])
        prompt = config.build_initial_prompt()
        self.assertIn("中文会议录音", prompt)

    def test_apply_runs_all_steps(self):
        config = CorrectionConfig.default()
        # "嗯" removed by filler filter, extra space collapsed by regex
        result = config.apply("嗯 大家好  这是 A P I 测试")
        self.assertNotIn("嗯", result)
        self.assertIn("API", result)

    def test_default_config_has_common_rules(self):
        config = CorrectionConfig.default()
        self.assertTrue(any(r.pattern == r"\bA\s+P\s+I\b" for r in config.regex_rules))
        self.assertTrue(config.filler_filter.enabled)

    def test_roundtrip_json(self):
        config = CorrectionConfig.default()
        config.custom_terms.append(CustomTerm("测试术语", "测试"))
        data = config.to_dict()
        restored = CorrectionConfig.from_dict(data)
        self.assertEqual(len(restored.custom_terms), 1)
        self.assertEqual(restored.custom_terms[0].term, "测试术语")


class ConfigFileTests(unittest.TestCase):
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            config = CorrectionConfig.default()
            config.custom_terms.append(CustomTerm("测试", "提示"))
            save_config(path, config)
            loaded = load_config(path)
            self.assertEqual(len(loaded.custom_terms), 1)
            self.assertEqual(loaded.custom_terms[0].term, "测试")

    def test_load_missing_returns_default(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "nonexistent.json"
            config = load_config(path)
            self.assertIsInstance(config, CorrectionConfig)

    def test_load_corrupt_returns_default(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.json"
            path.write_text("not json{{{", encoding="utf-8")
            config = load_config(path)
            self.assertIsInstance(config, CorrectionConfig)


if __name__ == "__main__":
    unittest.main()
