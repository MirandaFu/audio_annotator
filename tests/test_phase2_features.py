"""Tests for pinyin-based homophone correction and confidence marking."""
import re
import unittest

from correction import (
    PinyinCorrector,
    WordConfidence,
    SegmentConfidence,
    CorrectionConfig,
)


class PinyinCorrectorTests(unittest.TestCase):
    def test_disabled_passes_through(self):
        corrector = PinyinCorrector(enabled=False)
        self.assertEqual(corrector.correct("你好世界"), "你好世界")

    def test_non_chinese_unchanged(self):
        corrector = PinyinCorrector()
        self.assertEqual(corrector.correct("hello world 123"), "hello world 123")

    def test_chinese_characters_preserved(self):
        corrector = PinyinCorrector()
        # Most common characters should be preserved (no homophone pressure)
        result = corrector.correct("今天天气很好")
        self.assertIn("今", result)
        self.assertIn("天", result)
        self.assertIn("很", result)

    def test_empty_string(self):
        corrector = PinyinCorrector()
        self.assertEqual(corrector.correct(""), "")

    def test_none_input(self):
        corrector = PinyinCorrector()
        self.assertEqual(corrector.correct(None), "")

    def test_mixed_chinese_english(self):
        corrector = PinyinCorrector()
        result = corrector.correct("使用 API 接口")
        self.assertIn("A", result)
        self.assertIn("P", result)
        self.assertIn("I", result)

    def test_threshold_stored(self):
        corrector = PinyinCorrector(threshold=0.9)
        self.assertEqual(corrector.threshold, 0.9)

    def test_roundtrip_json(self):
        corrector = PinyinCorrector(enabled=False, threshold=0.7)
        data = corrector.to_dict()
        restored = PinyinCorrector.from_dict(data)
        self.assertFalse(restored.enabled)
        self.assertEqual(restored.threshold, 0.7)

    def test_pinyin_corrector_has_cache(self):
        corrector = PinyinCorrector()
        self.assertIsInstance(corrector._cache, dict)


class WordConfidenceTests(unittest.TestCase):
    def test_is_low_below_threshold(self):
        w = WordConfidence(word="测试", probability=0.5)
        self.assertTrue(w.is_low)
        self.assertFalse(w.is_very_low)

    def test_is_very_low(self):
        w = WordConfidence(word="测试", probability=0.2)
        self.assertTrue(w.is_low)
        self.assertTrue(w.is_very_low)

    def test_is_not_low_above_threshold(self):
        w = WordConfidence(word="测试", probability=0.8)
        self.assertFalse(w.is_low)
        self.assertFalse(w.is_very_low)

    def test_marker_very_low(self):
        w = WordConfidence(word="测试", probability=0.1)
        self.assertEqual(w.marker, "❓")

    def test_marker_low(self):
        w = WordConfidence(word="测试", probability=0.5)
        self.assertEqual(w.marker, "⚠️")

    def test_marker_high(self):
        w = WordConfidence(word="测试", probability=0.9)
        self.assertEqual(w.marker, "")

    def test_roundtrip(self):
        w = WordConfidence(word="开会", probability=0.75, start=1.0, end=2.0)
        data = w.to_dict()
        restored = WordConfidence.from_dict(data)
        self.assertEqual(restored.word, "开会")
        self.assertEqual(restored.probability, 0.75)
        self.assertEqual(restored.start, 1.0)
        self.assertEqual(restored.end, 2.0)

    def test_default_probability(self):
        w = WordConfidence(word="测试")
        self.assertEqual(w.probability, 1.0)

    def test_default_timestamps(self):
        w = WordConfidence(word="测试")
        self.assertEqual(w.start, 0.0)
        self.assertEqual(w.end, 0.0)


class SegmentConfidenceTests(unittest.TestCase):
    def test_avg_confidence_high(self):
        words = [
            WordConfidence("你", 0.9),
            WordConfidence("好", 0.95),
        ]
        sc = SegmentConfidence(words=words)
        self.assertAlmostEqual(sc.avg_confidence, 0.925)
        self.assertEqual(sc.low_confidence_count, 0)

    def test_avg_confidence_low(self):
        words = [
            WordConfidence("测", 0.5),
            WordConfidence("试", 0.3),
        ]
        sc = SegmentConfidence(words=words)
        self.assertAlmostEqual(sc.avg_confidence, 0.4)
        self.assertEqual(sc.low_confidence_count, 2)

    def test_low_confidence_words(self):
        words = [
            WordConfidence("高", 0.9),
            WordConfidence("低", 0.2),
            WordConfidence("中", 0.5),
        ]
        sc = SegmentConfidence(words=words)
        low = sc.low_confidence_words()
        self.assertEqual(len(low), 2)
        self.assertEqual(low[0].word, "低")
        self.assertEqual(low[1].word, "中")

    def test_empty_words(self):
        sc = SegmentConfidence(words=[])
        self.assertEqual(sc.avg_confidence, 1.0)
        self.assertEqual(sc.low_confidence_count, 0)

    def test_roundtrip(self):
        words = [
            WordConfidence("测", 0.55, start=0.0, end=0.5),
            WordConfidence("试", 0.2, start=0.5, end=1.0),
        ]
        sc = SegmentConfidence(words=words)
        data = sc.to_dict()
        restored = SegmentConfidence.from_dict(data)
        self.assertEqual(len(restored.words), 2)
        self.assertAlmostEqual(restored.avg_confidence, 0.375)
        self.assertEqual(restored.low_confidence_count, 2)


class CorrectionConfigConfidenceTests(unittest.TestCase):
    def test_analyze_confidence(self):
        config = CorrectionConfig.default()
        words_data = [
            [
                {"word": "大家", "probability": 0.95, "start": 0.0, "end": 0.5},
                {"word": "好", "probability": 0.4, "start": 0.5, "end": 1.0},
            ],
            [
                {"word": "今天", "probability": 0.2, "start": 1.0, "end": 1.5},
            ],
        ]
        results = config.analyze_confidence(words_data)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].avg_confidence, 0.675)
        self.assertEqual(results[0].low_confidence_count, 1)
        self.assertEqual(results[1].low_confidence_count, 1)

    def test_get_low_confidence_words(self):
        config = CorrectionConfig.default()
        words_data = [
            [
                {"word": "高", "probability": 0.9, "start": 0.0, "end": 0.5},
                {"word": "低", "probability": 0.2, "start": 0.5, "end": 1.0},
            ],
        ]
        segs_conf = config.analyze_confidence(words_data)
        low_words = config.get_low_confidence_words(segs_conf)
        self.assertEqual(len(low_words), 1)
        self.assertEqual(low_words[0].word, "低")

    def test_confidence_thresholds_in_config(self):
        config = CorrectionConfig(confidence_threshold=0.7, confidence_very_low=0.2)
        self.assertEqual(config.confidence_threshold, 0.7)
        self.assertEqual(config.confidence_very_low, 0.2)

    def test_pinyin_corrector_in_default_config(self):
        config = CorrectionConfig.default()
        self.assertIsInstance(config.pinyin_corrector, PinyinCorrector)
        self.assertTrue(config.pinyin_corrector.enabled)


class PinyinIntegrationTests(unittest.TestCase):
    """Test pinyin correction combined with other pipeline steps."""

    def test_pinyin_before_regex(self):
        """Pinyin correction should run before regex rules."""
        config = CorrectionConfig.default()
        config.pinyin_corrector = PinyinCorrector(enabled=True)
        # The correction pipeline applies pinyin first, then regex
        result = config.apply("使用 A P I 接口")
        # Regex should still fix "A P I" → "API"
        self.assertIn("API", result)

    def test_correction_with_pinyin_disabled(self):
        config = CorrectionConfig.default()
        config.pinyin_corrector = PinyinCorrector(enabled=False)
        text = "使用 A P I 接口"
        result = config.apply(text)
        self.assertIn("API", result)

    def test_full_config_roundtrip_with_pinyin(self):
        config = CorrectionConfig.default()
        config.pinyin_corrector = PinyinCorrector(enabled=False, threshold=0.8)
        config.confidence_threshold = 0.65
        data = config.to_dict()
        restored = CorrectionConfig.from_dict(data)
        self.assertFalse(restored.pinyin_corrector.enabled)
        self.assertEqual(restored.pinyin_corrector.threshold, 0.8)
        self.assertEqual(restored.confidence_threshold, 0.65)


if __name__ == "__main__":
    unittest.main()
