# Audio Annotator — 当前设计结构

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                          main.py (1190 行)                           │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  AudioAnnotator (主控制器)                                    │  │
│  │  - UI 布局 (toolbar / waveform / table / speaker panel)      │  │
│  │  - 音频 I/O (open_file / load_audio)                         │  │
│  │  - 播放控制 (play / pause / seek / stop)                     │  │
│  │  - 片段管理 (drag / split / merge / delete / adjust)         │  │
│  │  - 项目保存/加载                                              │  │
│  │  - 导出 (TXT/CSV/XLSX + CLI)                                 │  │
│  │  - 转写触发 (transcribe_segments)                             │  │
│  │  - 纠错面板 (_build_correction_panel)                         │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│              ┌───────────────┼───────────────┐                       │
│              ▼               ▼               ▼                       │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐            │
│  │ waveform_     │  │ segments_     │  │ speaker_      │            │
│  │ widget.py     │  │ table.py      │  │ panel.py      │            │
│  │ (638 行)      │  │ (150 行)      │  │ (244 行)      │            │
│  └───────────────┘  └───────────────┘  └───────────────┘            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  models.py (187 行)                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │
│  │ Segment     │  │ Speaker     │  │ AnnotationProject            │  │
│  │ - start/end │  │ - name      │  │ - audio_path                 │  │
│  │ - speaker   │  │ - color     │  │ - speakers[]                 │  │
│  │ - text      │  │             │  │ - segments[]                 │  │
│  │ - duration  │  │             │  │ - normalize()                │  │
│  │ - to/from   │  │ - to/from   │  │ - to/from_dict               │  │
│  │   dict      │  │   dict      │  │                              │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────────┘  │
│                                                                     │
│  函数层: sort_segments / split_segment / merge_segments            │
│          adjust_segment_edge / find_overlaps / validate_segment    │
│          coerce_segment                                            │
│          save_project / load_project                               │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  transcriber.py (160 行)                                             │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  FasterWhisperTranscriber                                    │  │
│  │  - __init__(model_size, device, compute_type)                │  │
│  │  - transcribe_file(path, language) → str                     │  │
│  │  - transcribe_with_timestamps(path, language,               │  │
│  │    initial_prompt, word_timestamps)                          │  │
│  │    → (segments[], info, word_data[])                         │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  匹配函数                                                     │  │
│  │  - match_transcription_to_segments(transcribed, annotations)  │  │
│  │    → [(segment, text), ...]                                   │  │
│  │  - match_confidence_to_segments(word_data, annotations)       │  │
│  │    → [SegmentConfidence, ...]                                 │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  transcribe_audio_segment(path, segment, transcriber)         │  │
│  │  (保留用于切片场景，当前主流程已不用)                          │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  correction.py (280 行)                                              │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐     │
│  │ CustomTerm   │  │ RegexRule    │  │ FillerFilter          │     │
│  │ - term       │  │ - pattern    │  │ - enabled             │     │
│  │ - hint       │  │ - replace    │  │ - words[]             │     │
│  │              │  │ - enabled    │  │                       │     │
│  └──────────────┘  └──────────────┘  └───────────────────────┘     │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐     │
│  │WordConfidence│  │SegmentConf.  │  │ PinyinCorrector       │     │
│  │- word        │  │- words[]     │  │ - enabled             │     │
│  │- probability │  │- avg_conf    │  │ - threshold           │     │
│  │- start/end   │  │- low_count   │  │ - correct(text)       │     │
│  │- is_low      │  │              │  │                       │     │
│  │- marker      │  │              │  │                       │     │
│  └──────────────┘  └──────────────┘  └───────────────────────┘     │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  CorrectionConfig                                            │  │
│  │  - custom_terms[]                                            │  │
│  │  - regex_rules[]                                             │  │
│  │  - filler_filter                                             │  │
│  │  - pinyin_corrector                                          │  │
│  │  - confidence_threshold (0.6)                                │  │
│  │  - confidence_very_low (0.3)                                 │  │
│  │                                                               │  │
│  │  - build_initial_prompt() → str                              │  │
│  │  - apply(text) → str          [纠错流水线]                    │  │
│  │  - analyze_confidence(word_data) → [SegmentConfidence]        │  │
│  │  - get_low_confidence_words(segs_conf) → [WordConfidence]     │  │
│  │  - to/from_dict                                              │  │
│  │  - default() → CorrectionConfig                              │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  配置文件 (JSON)                                              │  │
│  │  ~/.audio-annotator/correction-config.json                   │  │
│  │  - 跨会话持久化                                               │  │
│  │  - 容错加载 (missing/corrupt → default)                       │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## 二、转写+纠错数据流

```
┌──────────────────────────────────────────────────────────────────────┐
│  Step 1: 全文件转写                                                   │
│  ─────────────────                                                   │
│  FasterWhisperTranscriber.transcribe_with_timestamps()               │
│  ├── model_size="medium"                                             │
│  ├── device="auto" (MPS on Apple Silicon)                           │
│  ├── compute_type="float16"                                          │
│  ├── language="zh"                                                   │
│  ├── vad_filter=True                                                 │
│  ├── initial_prompt = config.build_initial_prompt()                  │
│  │   "这是一段中文会议录音，涉及以下术语和名称：数智办公、例会。"      │
│  ├── word_timestamps=True (Phase 2 新增)                             │
│  └── 返回: (transcribed_segments[], info, word_data[])               │
│                                                                      │
│  示例输出:                                                            │
│  transcribed = [                                                     │
│    {start: 0.0, end: 3.5, text: "大家好欢迎参加"},                   │
│    {start: 3.5, end: 7.0, text: "本次会议讨论"},                     │
│    ...                                                               │
│  ]                                                                   │
│  word_data = [                                                       │
│    [{word: "大家", probability: 0.95, start: 0.0, end: 0.5},         │
│     {word: "好", probability: 0.4, start: 0.5, end: 1.0}],          │
│    ...                                                               │
│  ]                                                                   │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Step 2: 时间匹配                                                     │
│  ─────────────────                                                   │
│  match_transcription_to_segments(transcribed, user_segments)          │
│  - 对每个用户标注片段，查找时间重叠的转写文本                          │
│  - 重叠条件: tseg.end > seg.start AND tseg.start < seg.end           │
│  - 多段重叠时拼接文本                                                 │
│                                                                      │
│  match_confidence_to_segments(word_data, user_segments)               │
│  - 对每个用户标注片段，查找时间重叠的词级置信度数据                    │
│  - 聚合为 SegmentConfidence                                          │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Step 3: 置信度分析                                                   │
│  ─────────────────                                                   │
│  config.analyze_confidence(word_data) → [SegmentConfidence]           │
│  - 计算每个片段的 avg_confidence                                      │
│  - 统计 low_confidence_count (< 0.6)                                 │
│  - 标记 very_low (< 0.3)                                             │
│                                                                      │
│  config.get_low_confidence_words(segs_conf) → [WordConfidence]        │
│  - 提取所有低置信度词                                                 │
│  - UI 可据此高亮显示 (尚未实现)                                       │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Step 4: 后处理纠错                                                   │
│  ─────────────────                                                   │
│  config.apply(text) → corrected_text                                  │
│                                                                      │
│  流水线顺序:                                                          │
│  ① PinyinCorrector.correct(text)                                     │
│     - 逐字检测汉字                                                    │
│     - 提取拼音 → 查找同音字候选                                       │
│     - 上下文优化选择 (保守: 优先保持原字)                              │
│                                                                      │
│  ② RegexRule.apply(text) × N                                         │
│     - 内置规则: API 合并 / K8s 纠错 / 语气词清除 / 空格合并           │
│     - 用户自定义规则                                                   │
│                                                                      │
│  ③ FillerFilter.filter(text)                                         │
│     - 清除预设语气词 (嗯/啊/就是/那个/然后呢/就是说)                  │
│     - 清理标点残留                                                    │
│                                                                      │
│  ④ .strip()                                                          │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Step 5: 填充结果                                                     │
│  ─────────────────                                                   │
│  seg["text"] = corrected_text                                         │
│  _refresh_table()  →  波形 + 列表更新                                │
│  状态栏: "识别完成: 42 个片段，38 个有内容 (模型: medium)"             │
└──────────────────────────────────────────────────────────────────────┘
```

## 三、UI 组件关系

```
AudioAnnotator (主窗口 1400×800)
│
├── Row 1: 工具栏 (toolbar)
│   ├── 📂 打开 → open_file()
│   ├── ▶ 播放 / ⏸ 暂停 → _on_play_click()
│   ├── ⏹ 从头播放 → stop()
│   ├── │ 时间显示 ┃ 输出设备下拉 ┃ 当前发言人标签
│   │
│   ├── Row 2: 工具栏
│   │   ├── 📌 打点模式 → _toggle_mark_mode()
│   │   ├── 📁 打开项目 → open_project()
│   │   ├── 💾 保存项目 → save_project()
│   │   ├── 💾 导出 → export_segments()
│   │   ├── 📝 识别内容 → transcribe_segments()     [转写入口]
│   │   ├── ✏️ 纠错 → _open_correction_panel()       [纠错设置入口]
│   │   ├── 🗑 删除 → _delete_selected()
│   │   ├── ✂ 拆分 → _split_selected()
│   │   ├── ⛓ 合并下段 → _merge_selected_with_next()
│   │   ├── 缩放控制 (＋/－/⟲)
│   │   ├── 高度滑块
│   │   │
│   │   └── Seek 进度条
│   │
│   ├── PanedWindow (水平分割)
│   │   │
│   │   ├── left_paned (垂直分割, weight=4)
│   │   │   ├── waveform_container
│   │   │   │   └── WaveformWidget
│   │   │   │       - 波形绘制
│   │   │   │       - 片段着色
│   │   │   │       - 播放头
│   │   │   │       - 鼠标交互 (拖拽标注 / 边缘调整 / 打点)
│   │   │   │       - 缩放/滚动
│   │   │   │       └── Scrollbar (水平, 缩放 > 1x 时显示)
│   │   │   │
│   │   │   └── table_container
│   │   │       └── SegmentsTable (Treeview)
│   │   │           - 片段列表
│   │   │           - 双击编辑说话人
│   │   │           - Delete 删除
│   │   │           - 点击跳转播放
│   │   │
│   │   └── speaker_container (weight=1)
│   │       └── SpeakerPanel
│   │           - 发言人列表 (Listbox + 颜色)
│   │           - ＋ 新增 / ✕ 删除
│   │           - 双击重命名
│   │           - 点击选择当前发言人
│   │
│   └── Status bar (底部)
│       └── 状态文字 / 进度提示
```

## 四、数据模型关系

```
AnnotationProject (顶层)
├── audio_path: str | None
├── speakers: List[Speaker]
│   └── Speaker {name: str, color: str}
└── segments: List[Segment]
    └── Segment {
        start: float,      # 自动 clamp ≥ 0
        end: float,        # 自动 ≥ start (swap if needed)
        speaker: str,
        text: str,         # 转写内容 (可空)
        duration → float   # property: max(0, end - start)
      }

双向访问:
  seg["start"]  ↔  seg.start
  seg["speaker"] ↔ seg.speaker
  seg["text"]   ↔  seg.text

序列化:
  Segment.to_dict() → {"start", "end", "speaker", "text"}
  Speaker.to_dict() → {"name", "color"}
  AnnotationProject.to_dict() → {"version", "audio_path", "speakers", "segments"}

持久化:
  save_project(path, project) → JSON file (.aaproj)
  load_project(path) → AnnotationProject
  - normalize() 自动排序 + 类型 coercion
```

## 五、转写引擎参数配置

```python
# 当前配置 (M5 Pro 24GB 最优)
FasterWhisperTranscriber(
    model_size="medium",     # 769M 参数，~5GB 内存
    device="auto",            # Apple Silicon → MPS
    compute_type="float16",   # 原生支持，速度翻倍
)

# transcribe_with_timestamps 参数
transcribe_with_timestamps(
    path=audio_path,
    language="zh",
    initial_prompt="这是一段中文会议录音，涉及以下术语和名称：...",
    word_timestamps=True,  # Phase 2 新增，用于置信度分析
)

# Whisper 内部参数
vad_filter=True
vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=200)
beam_size=5
```

## 六、纠错流水线配置

```python
CorrectionConfig(
    # 1. 用户词典 → 构建 initial_prompt
    custom_terms=[
        CustomTerm("数智办公", "项目名称"),
        CustomTerm("例会", "会议类型"),
        # 用户通过 UI 面板添加
    ],

    # 2. 正则替换规则 (按顺序执行)
    regex_rules=[
        RegexRule(r"\bA\s+P\s+I\b", "API", description="合并API字母间距"),
        RegexRule(r"\bK\s*八\s*S\b", "K8s", description="K8s 纠错"),
        RegexRule(r"嗯[，。\s]*|啊[，。\s]*", "", description="清除语气词嗯啊"),
        RegexRule(r"\s{2,}", " ", description="合并多余空格"),
        # 用户可通过 UI 添加自定义规则
    ],

    # 3. 语气词过滤
    filler_filter=FillerFilter(
        enabled=True,
        words=["嗯", "啊", "就是", "那个", "然后呢", "就是说"],
    ),

    # 4. 拼音纠错 (Phase 2 新增)
    pinyin_corrector=PinyinCorrector(
        enabled=True,
        threshold=0.85,
    ),

    # 5. 置信度阈值
    confidence_threshold=0.6,      # < 0.6 → ⚠️ 低置信度
    confidence_very_low=0.3,       # < 0.3 → ❓ 极低置信度
)
```

## 七、当前准确率瓶颈分析

### 实测数据 (testdata/3-数智办公四月第二次例会.wav)

| 指标 | 数值 |
|---|---|
| 音频时长 | 2430.6s (40.5 min) |
| 采样率 | 16000 Hz, 单声道 |
| small 模型转写 | 670 segments, 3527 chars, 649s |
| medium 模型转写 | 610 segments, 3517 chars, 3537s |
| 小模型 vs 中模型差异 | 1280 segments 中大部分时间范围不重合 |

### 识别错误类型 (实测)

```
[0.4s -> 1.7s]
  预期: "慢慢把这个弄进去"
  实际: "慢慢把这个弄进去"  ← small 正确

[21.9s -> 22.5s]
  预期: "是轻啊"
  实际: "是轻啊"  ← small 正确

[23.3s -> 46.7s] (23秒长段!)
  预期: "曲线" (可能是某个技术术语的重复)
  实际: "曲线"
  问题: 23秒只识别出2个字，大量内容丢失

[55.2s -> 57.0s]
  预期: "你要32元后面就没有了"
  实际: "你要32元后面就没有了"
  问题: "32元" 可能是 "三元" 或 "32元" 的误识别
```

### 根本原因

1. **VAD 过度分割** — 23 秒的语音被切成极短片段，导致长语句丢失
2. **专业术语未识别** — "数智办公"、"K8s" 等术语在没有 initial_prompt 时被拆分
3. **数字/金额混淆** — "三元" vs "32元" vs "三元"
4. **同音字** — "是轻啊" 可能是 "是清单" / "是轻啊"
5. **语气词残留** — "嗯"、"啊" 等 filler words 未被过滤

## 八、改进方向

### 短期 (Phase 2.1) — 已实现
- [x] initial_prompt 注入术语
- [x] 正则批量纠错
- [x] 语气词过滤
- [x] 拼音谐音纠错 (保守策略)
- [x] 置信度标记数据结构

### 中期 (Phase 2.2) — 部分实现
- [x] 对比模型投票 (small + medium 投票) — `vote_transcription()`
- [x] VAD 参数调优 (min_silence_duration_ms, speech_pad_ms) — `VadConfig` + 三档预设
- [x] 片段合并策略 (识别后自动合并相邻同说话人短片段) — `merge_short_segments()`
- [ ] 置信度 UI 高亮 (低置信度词黄色/红色下划线)
- [ ] 用户词典一键添加 (从转写结果右键添加)

### 长期 (Phase 3) — 规划中
- [ ] 说话人分离集成 (pyannote / Silero)
- [ ] 上下文一致性检查 (人名/数字统一性)
- [ ] 在线学习 (用户修正后自动更新词典)
- [ ] 多语言支持 (英文会议模式)

## 九、文件依赖图

```
main.py
├── models.py          (数据模型)
├── waveform_widget.py (波形画布)
├── segments_table.py   (片段列表)
├── speaker_panel.py    (发言人面板)
├── transcriber.py      (转写引擎)
│   ├── models.py       (coerce_segment)
│   ├── correction.py   (WordConfidence, SegmentConfidence)
│   ├── VadConfig       (VAD参数调优)
│   ├── merge_short_segments()  (片段合并策略)
│   └── vote_transcription()    (双模型投票)
├── correction.py       (纠错流水线)
└── openpyxl            (导出)

correction.py           (独立模块，无外部依赖除 pypinyin)
├── (standalone, 可单独测试)

tests/
├── test_smoke.py           → main, models, segments_table, speaker_panel, waveform_widget
├── test_models.py           → models
├── test_main_logic.py       → main (_parse_time, _cli_export)
├── test_transcriber.py      → transcriber, models
├── test_correction.py       → correction
├── test_audio_engine.py     → main.AudioEngine
├── test_waveform_widget.py  → waveform_widget
├── test_segments_table.py   → segments_table
├── test_speaker_panel.py    → speaker_panel
├── test_annotation_flow.py  → models, transcriber, correction, main
├── test_phase2_features.py  → correction
└── test_transcription_accuracy.py → transcriber (手动脚本)
```

## 十、版本信息

```
当前版本: v0.4.0-transcription-improved (未打 tag)
隔离版本: v0.2.0-manual-annotation (已打 tag)

commit: f1e3c69

Phase 2.2 新增: VAD调优, 片段合并, 双模型投票 (20 tests)
```
