"""Transcription post-processing pipeline: user dictionary, regex rules, filler filtering,
pinyin-based homophone correction, and confidence marking."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CustomTerm:
    term: str
    hint: str = ""

    def to_dict(self):
        return {"term": self.term, "hint": self.hint}

    @classmethod
    def from_dict(cls, data):
        return cls(term=str(data.get("term", "")), hint=str(data.get("hint", "")))


@dataclass
class RegexRule:
    pattern: str
    replacement: str
    enabled: bool = True
    description: str = ""

    def __post_init__(self):
        self._compiled = re.compile(self.pattern)

    def apply(self, text: str) -> str:
        if not self.enabled:
            return text
        return self._compiled.sub(self.replacement, text)

    def to_dict(self):
        return {
            "pattern": self.pattern,
            "replacement": self.replacement,
            "enabled": self.enabled,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            pattern=str(data.get("pattern", "")),
            replacement=str(data.get("replacement", "")),
            enabled=bool(data.get("enabled", True)),
            description=str(data.get("description", "")),
        )


@dataclass
class FillerFilter:
    enabled: bool = True
    words: list[str] = field(default_factory=lambda: ["嗯", "啊", "就是", "那个", "然后呢", "就是说"])

    def filter(self, text: str) -> str:
        if not self.enabled or not self.words:
            return text
        result = text
        for word in self.words:
            result = result.replace(word, "")
        # Clean up extra spaces
        result = re.sub(r"\s{2,}", " ", result).strip()
        # Remove punctuation-only artifacts left by filler removal
        result = re.sub(r"[，。]{2,}", "，", result)
        return result

    def to_dict(self):
        return {"enabled": self.enabled, "words": list(self.words)}

    @classmethod
    def from_dict(cls, data):
        return cls(
            enabled=bool(data.get("enabled", True)),
            words=list(data.get("words", ["嗯", "啊", "就是", "那个", "然后呢", "就是说"])),
        )


@dataclass
class WordConfidence:
    """Represents a word with its transcription confidence."""
    word: str
    probability: float = 1.0
    start: float = 0.0
    end: float = 0.0

    @property
    def is_low(self) -> bool:
        return self.probability < 0.6

    @property
    def is_very_low(self) -> bool:
        return self.probability < 0.3

    @property
    def marker(self) -> str:
        if self.is_very_low:
            return "❓"  # Very uncertain
        elif self.is_low:
            return "⚠️"  # Uncertain
        return ""

    def to_dict(self):
        return {
            "word": self.word,
            "probability": round(self.probability, 4),
            "start": self.start,
            "end": self.end,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            word=str(data.get("word", "")),
            probability=float(data.get("probability", 1.0)),
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
        )


@dataclass
class SegmentConfidence:
    """Confidence analysis for a transcribed segment."""
    words: list[WordConfidence] = field(default_factory=list)
    avg_confidence: float = 1.0
    low_confidence_count: int = 0

    def __post_init__(self):
        if self.words:
            self.avg_confidence = sum(w.probability for w in self.words) / len(self.words)
            self.low_confidence_count = sum(1 for w in self.words if w.is_low)

    def low_confidence_words(self) -> list[WordConfidence]:
        return [w for w in self.words if w.is_low]

    def to_dict(self):
        return {
            "words": [w.to_dict() for w in self.words],
            "avg_confidence": round(self.avg_confidence, 4),
            "low_confidence_count": self.low_confidence_count,
        }

    @classmethod
    def from_dict(cls, data):
        words = [WordConfidence.from_dict(w) for w in data.get("words", [])]
        return cls(
            words=words,
            avg_confidence=float(data.get("avg_confidence", 1.0)),
            low_confidence_count=int(data.get("low_confidence_count", 0)),
        )


@dataclass
class PinyinCorrector:
    enabled: bool = True
    threshold: float = 0.85  # Similarity threshold for correction
    _cache: dict = field(default_factory=dict, repr=False, compare=False)

    def correct(self, text: str) -> str:
        if not self.enabled or not text:
            return text or ""
        try:
            from pypinyin import lazy_pinyin, pinyin
            from pypinyin.errors import InvalidPinyin
        except ImportError:
            return text

        # Build homophone lookup for the text
        result = []
        for char in text:
            if not self._is_chinese(char):
                result.append(char)
                continue
            try:
                py = lazy_pinyin(char)[0]
            except (InvalidPinyin, IndexError):
                result.append(char)
                continue
            candidates = self._get_homophones(char, py)
            if not candidates:
                result.append(char)
                continue
            # Check if context suggests a different candidate
            best = self._pick_best(char, candidates, text)
            result.append(best)
        return "".join(result)

    def _is_chinese(self, char: str) -> bool:
        cp = ord(char)
        return 0x4E00 <= cp <= 0x9FFF

    def _get_homophones(self, char: str, pinyin: str) -> list[str]:
        try:
            from pypinyin import pinyin as _pinyin
            # Get all characters with same pinyin
            all_py = _pinyin(char, style=0, heteronym=True)
            if not all_py or not all_py[0]:
                return []
            # Characters with same pronunciation
            candidates = []
            py_list = all_py[0]
            for py in py_list:
                if py == pinyin:
                    continue  # Skip same pronunciation
                # Find characters with this pronunciation
                from pypinyin.loader import _load_single
                raw = _load_single()
                for c, readings in raw.items():
                    if pinyin in readings and c != char and self._is_chinese(c):
                        candidates.append(c)
            return candidates
        except Exception:
            return []

    def _pick_best(self, original: str, candidates: list[str], context: str) -> str:
        if not candidates:
            return original
        # Prefer candidates that form common words in context
        for candidate in candidates[:3]:
            if candidate in context:
                return candidate
        # Default to original (conservative)
        return original

    def to_dict(self):
        return {"enabled": self.enabled, "threshold": self.threshold}

    @classmethod
    def from_dict(cls, data):
        return cls(
            enabled=bool(data.get("enabled", True)),
            threshold=float(data.get("threshold", 0.85)),
        )


@dataclass
class CorrectionConfig:
    custom_terms: list[CustomTerm] = field(default_factory=list)
    regex_rules: list[RegexRule] = field(default_factory=list)
    filler_filter: FillerFilter = field(default_factory=FillerFilter)
    pinyin_corrector: PinyinCorrector = field(default_factory=PinyinCorrector)
    confidence_threshold: float = 0.6  # Below this = low confidence
    confidence_very_low: float = 0.3  # Below this = very low confidence

    def build_initial_prompt(self) -> str:
        """Build initial_prompt from custom terms for Whisper transcription."""
        terms = [t.term for t in self.custom_terms if t.term.strip()]
        if not terms:
            return "这是一段中文会议录音，包含专业术语和项目名称。"
        term_list = "、".join(terms)
        return f"这是一段中文会议录音，涉及以下术语和名称：{term_list}。"

    def apply(self, text: str) -> str:
        """Apply all post-processing corrections to transcribed text."""
        if text is None:
            return ""
        if not text:
            return text
        result = text
        # Step 1: Pinyin homophone correction (before regex)
        result = self.pinyin_corrector.correct(result)
        # Step 2: Apply regex rules
        for rule in self.regex_rules:
            result = rule.apply(result)
        # Step 3: Apply filler filter
        result = self.filler_filter.filter(result)
        return result.strip()

    def analyze_confidence(self, words_data: list[dict]) -> list[SegmentConfidence]:
        """Analyze word-level confidence from Whisper output."""
        segments_conf = []
        for seg_words in words_data:
            words = []
            for w in seg_words:
                words.append(WordConfidence(
                    word=w.get("word", ""),
                    probability=float(w.get("probability", 1.0)),
                    start=float(w.get("start", 0.0)),
                    end=float(w.get("end", 0.0)),
                ))
            segments_conf.append(SegmentConfidence(words=words))
        return segments_conf

    def get_low_confidence_words(self, segments_conf: list[SegmentConfidence]) -> list[WordConfidence]:
        """Extract all low-confidence words across all segments."""
        result = []
        for sc in segments_conf:
            result.extend(sc.low_confidence_words())
        return result

    def to_dict(self):
        return {
            "custom_terms": [t.to_dict() for t in self.custom_terms],
            "regex_rules": [r.to_dict() for r in self.regex_rules],
            "filler_filter": self.filler_filter.to_dict(),
            "pinyin_corrector": self.pinyin_corrector.to_dict(),
            "confidence_threshold": self.confidence_threshold,
            "confidence_very_low": self.confidence_very_low,
        }

    @classmethod
    def from_dict(cls, data):
        terms = [CustomTerm.from_dict(t) for t in data.get("custom_terms", [])]
        rules = [RegexRule.from_dict(r) for r in data.get("regex_rules", [])]
        filler = FillerFilter.from_dict(data.get("filler_filter", {}))
        pinyin = PinyinCorrector.from_dict(data.get("pinyin_corrector", {}))
        config = cls(
            custom_terms=terms,
            regex_rules=rules,
            filler_filter=filler,
            pinyin_corrector=pinyin,
            confidence_threshold=float(data.get("confidence_threshold", 0.6)),
            confidence_very_low=float(data.get("confidence_very_low", 0.3)),
        )
        return config

    @classmethod
    def default(cls):
        """Return default configuration with common Chinese meeting filler rules."""
        return cls(
            custom_terms=[],
            regex_rules=[
                RegexRule(
                    pattern=r"\bA\s+P\s+I\b",
                    replacement="API",
                    description="合并API字母间距",
                ),
                RegexRule(
                    pattern=r"\bK\s*八\s*S\b",
                    replacement="K8s",
                    description="K8s 纠错",
                ),
                RegexRule(
                    pattern=r"嗯[，。\s]*|啊[，。\s]*",
                    replacement="",
                    description="清除语气词嗯啊",
                ),
                RegexRule(
                    pattern=r"\s{2,}",
                    replacement=" ",
                    description="合并多余空格",
                ),
            ],
            filler_filter=FillerFilter(),
            pinyin_corrector=PinyinCorrector(),
        )


def load_config(path: str | Path) -> CorrectionConfig:
    path = Path(path)
    if not path.exists():
        return CorrectionConfig.default()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return CorrectionConfig.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return CorrectionConfig.default()


def save_config(path: str | Path, config: CorrectionConfig):
    path = Path(path)
    path.write_text(json.dumps(config.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
