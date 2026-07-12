# 自动说话人识别设计方案

## 一、目标

在现有手动标注工具基础上，增加「自动识别 + 人工修正」的工作流：

1. 自动检测音频中「谁在什么时间段说话」（说话人日志 / Speaker Diarization）
2. 将识别结果加载到现有波形界面，用户可以手动修正（合并、拆分、改发言人、调整起止时间）
3. 修正后的数据可以继续导出为 TXT / CSV / XLSX

---

## 二、整体架构

```
┌─────────────────────────────────────────────┐
│              AudioAnnotator (现有)            │
│  ┌─────────────┐  ┌──────────────┐           │
│  │ WaveformWidget│  │ SegmentsTable│           │
│  │ (波形+播放头) │  │ (片段列表)    │           │
│  └──────┬──────┘  └──────┬───────┘           │
│         │                │                   │
│  ┌──────▼────────────────▼───────┐           │
│  │     AudioAnnotator (主控制器)  │           │
│  └──────────────────────────────┘           │
│                     ▲                        │
│                     │  segments 列表          │
│  ┌────────────────────┴──────────────┐       │
│  │     DiarizationEngine (新增)       │       │
│  │  ┌─────────────┐  ┌───────────┐  │       │
│  │  │ VAD (语音检测)│  │  Speaker  │  │       │
│  │  │ Silero / pyannote │ Embedding│  │       │
│  │  └──────┬──────┘  └─────┬─────┘  │       │
│  │         │               │          │       │
│  │  ┌──────▼───────────────▼─────┐  │       │
│  │  │     Clustering (聚类)        │  │       │
│  │  │   SpectralCluster / Agglomerative ││       │
│  │  └──────────────────────────┘  │       │
│  └────────────────────────────────┘       │
└─────────────────────────────────────────────┘
```

### 数据流

```
音频文件 (WAV)
    │
    ▼
[1] VAD ──→ 检测出「有语音的时间段」 (speech segments)
    │
    ▼
[2] Feature Extraction ──→ 每个时间段提取 speaker embedding (512维向量)
    │
    ▼
[3] Clustering ──→ 将 embedding 按相似度聚类，得到 K 个说话人
    │
    ▼
[4] 输出 ──→ segments 列表: [{start, end, speaker: "说话人1"/"说话人2"/...}]
    │
    ▼
[5] 加载到现有波形界面 ──→ 用户手动修正
```

---

## 三、技术选型

### 方案对比

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| **pyannote.audio 3.x** | 业界最准确，预训练模型完善，支持 VAD + embedding + 聚类 | 需安装 PyTorch，首次运行需接受模型 license（HuggingFace），模型较大（~300MB） | ✅ 推荐作为离线高质量方案 |
| **Silero VAD + ECAPA-TDNN** | 轻量（~10MB），无需 GPU，纯 CPU 即可实时运行 | 准确率略低于 pyannote，需自行实现聚类 | ✅ 推荐作为轻量快速方案 |
| **云端 API (Azure / Google)** | 准确率最高 | 需网络、付费、数据上传到第三方 | ❌ 不适合本地工具 |

### 推荐：双模式

```
模式 A（轻量模式）：Silero VAD + 简单聚类
  - 下载模型 ~10MB
  - 纯 CPU，处理 1小时音频 ~30秒
  - 适合快速预览

模式 B（精准模式）：pyannote.audio 预训练模型
  - 下载模型 ~300MB
  - 需要 PyTorch，可用 CPU 或 GPU
  - 处理 1小时音频 ~2-5分钟（CPU）
  - 适合最终标注
```

---

## 四、技术细节

### 4.1 VAD（Voice Activity Detection）

**作用**：从音频中切分出「有语音」的时间段，过滤静音和噪声。

**Silero VAD**：
```python
import torch
model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                              model='silero_vad', trust_repo=True)
get_speech_timestamps = utils[0]

# 输入音频数据，输出 [{start: 0.0, end: 3.5}, ...]
speech_timestamps = get_speech_timestamps(audio_data, model, sampling_rate=16000)
```

**输出**：`[{start: 0.0, end: 3.5}, {start: 5.2, end: 8.1}, ...]`
- 每个时间段是连续的语音段
- 静音段已被过滤

### 4.2 Speaker Embedding

**作用**：将每个语音段转换成一个 512 维向量，表示「这个声音的特征」。

```python
from speechbrain.pretrained import EncoderClassifier

classifier = EncoderClassifier.from_hparams(
    source="speechbrain/spkrec-ecapa-voxceleb"
)

# 对每个语音段提取 embedding
embeddings = []
for seg in speech_segments:
    segment_audio = audio_data[seg['start'] : seg['end']]
    emb = classifier.encode_batch(segment_audio)
    embeddings.append(emb.squeeze().numpy())
```

### 4.3 Clustering（聚类）

**作用**：将 embedding 按相似度分组，同一组的归为同一个说话人。

```python
from sklearn.cluster import AgglomerativeClustering

# 计算 embedding 之间的相似度矩阵
similarity = cosine_similarity(embeddings)

# 层次聚类，自动确定人数
clustering = AgglomerativeClustering(
    n_clusters=None,
    distance_threshold=0.5,  # 可调参数
    metric='precomputed',
    linkage='average'
)
labels = clustering.fit_predict(1 - similarity)  # 距离 = 1 - 相似度
```

**输出**：`[0, 0, 1, 1, 0, 2, ...]` — 每个语音段对应的说话人编号

### 4.4 后处理

聚类后需要进行合理性修正：

| 问题 | 处理策略 |
|---|---|
| 同一说话人中间有静音被分成两段 | 合并相邻的同类片段（间隔 < 0.5s） |
| 片段太短（< 0.3s） | 合并到前后最近的片段 |
| 片段太长（> 30s） | 可选：不拆分（保持原样） |
| 检测到太多说话人（> 8） | 合并相似度最高的两个类别 |
| 检测到太少说话人（= 1） | 降低聚类阈值重试 |

---

## 五、UI 设计

### 5.1 新增按钮

在顶部工具栏增加：

```
[📂 打开] [▶ 播放] [⏹ 从头播放] | [🤖 自动识别] | [📏 缩放...] | [💾 导出]
```

### 5.2 自动识别流程

```
用户点击 [🤖 自动识别]
    │
    ▼
弹出选项对话框：
  ┌─────────────────────────────────┐
  │  自动识别设置                    │
  │                                 │
  │  识别模式:                       │
  │  ○ 快速模式（Silero VAD）        │
  │  ○ 精准模式（pyannote）          │
  │                                 │
  │  预期说话人数量: [自动检测]       │
  │  最小片段长度: [0.3] 秒          │
  │  合并间隔:    [0.5] 秒          │
  │                                 │
  │  [开始识别]  [取消]              │
  └─────────────────────────────────┘
    │
    ▼
显示进度条（处理中...）
    │
    ▼
识别完成 → 自动加载到波形
  - 不同说话人用不同颜色显示
  - 片段列表自动填充
  - 状态栏显示：「识别完成：检测到 3 个说话人，共 12 个片段」
```

### 5.3 修正流程

识别结果加载后，用户可以：

| 操作 | 说明 |
|---|---|
| 拖拽波形 | 在已有片段之间添加新片段（与现有功能一致） |
| 双击片段 | 修改说话人名称（与现有功能一致） |
| 拖拽片段边缘 | 调整起止时间（新增） |
| 选中片段 + Delete | 删除误识别的片段 |
| 选中两个片段 → 合并 | 将相邻的同类片段合并（新增按钮） |
| 右键片段 → 拆分 | 在片段中间拆分（新增） |

### 5.4 波形显示

- 每个说话人的片段用不同颜色填充（与现有颜色体系一致）
- 片段之间用 1px 间隔区分
- 当前选中的说话人高亮显示
- 未识别的片段（VAD 检测到但聚类不确定）用灰色显示

---

## 六、文件结构

```
audio_annotator/
├── main.py                  # 主程序（现有，少量修改）
├── waveform_widget.py       # 波形画布（现有，新增拖拽调整片段边缘）
├── segments_table.py        # 片段列表（现有，新增合并/拆分按钮）
├── speaker_panel.py         # 发言人面板（现有，无需修改）
├── diarization.py           # 新增：自动识别引擎
│   ├── DiarizationEngine    #   主类
│   ├── VADBackend           #   语音活动检测接口
│   │   ├── SileroVAD        #     Silero 实现
│   │   └── PyannoteVAD      #     pyannote 实现
│   ├── EmbeddingExtractor   #   说话人特征提取
│   ├── Clusterer            #   聚类算法
│   └── PostProcessor        #   后处理（合并/过滤）
└── README.md
```

---

## 七、依赖变化

```bash
# 新增依赖（按模式选择）

# 模式 A：轻量模式（Silero VAD + SpeechBrain）
pip install torch torchaudio speechbrain scikit-learn

# 模式 B：精准模式（pyannote.audio）
pip install torch torchaudio pyannote.audio scikit-learn
```

**注意**：
- `torch` 和 `torchaudio` 是两个大依赖（~2GB）
- 首次使用需要下载模型（Silero ~10MB，pyannote ~300MB）
- 模型缓存到 `~/.cache/torch/hub/` 或 HuggingFace cache

---

## 八、实现优先级

### Phase 1：核心识别（最小可用）

1. 创建 `diarization.py` 框架
2. 实现 Silero VAD 语音检测
3. 实现简单的聚类（AgglomerativeClustering）
4. 在 `main.py` 添加「自动识别」按钮和选项对话框
5. 识别结果加载到现有 segments 列表

**预计代码量**：~300 行新代码

### Phase 2：修正功能

1. 波形上拖拽调整片段边缘（改变 start/end）
2. 片段合并按钮（选中两个相邻片段 → 合并为一个）
3. 片段拆分（在选中位置拆成两个）
4. 右键菜单优化

**预计代码量**：~200 行新代码

### Phase 3：优化

1. 添加 pyannote 精准模式选项
2. 识别进度条
3. 聚类参数可视化（调整 distance_threshold 滑块实时预览）
4. 批量操作（全部合并同类片段）

---

## 九、关键技术风险

| 风险 | 缓解措施 |
|---|---|
| PyTorch 安装包过大 (~2GB) | 提供「仅安装轻量模式」选项；文档说明 Miniconda 安装 |
| 模型下载需网络 | 提供模型文件手动下载链接；支持离线导入 |
| 聚类结果不稳定 | 提供 `distance_threshold` 滑块让用户实时调整 |
| 处理长音频慢（>1小时） | 分块处理 + 进度条；后台线程不阻塞 UI |
| macOS Apple Silicon 兼容性 | Silero 和 pyannote 均支持 arm64，测试确认 |

---

## 十、示例代码骨架

```python
# diarization.py

class DiarizationEngine:
    def __init__(self, mode='fast'):
        self.mode = mode
        self.vad = SileroVAD() if mode == 'fast' else PyannoteVAD()
        self.embedder = SpeechBrainEmbeddingExtractor()
        self.clusterer = AgglomerativeClusterer()

    def process(self, audio_path, num_speakers=None, min_duration=0.3):
        # 1. 加载音频
        audio, sr = load_audio(audio_path)

        # 2. VAD 检测语音段
        speech_segs = self.vad.detect(audio, sr)
        # → [{start: 0.0, end: 3.5}, {start: 5.2, end: 8.1}, ...]

        # 3. 提取 embedding
        embeddings = self.embedder.extract(audio, sr, speech_segs)
        # → [np.array([...]), np.array([...]), ...]

        # 4. 聚类
        labels = self.clusterer.cluster(embeddings, num_speakers)
        # → [0, 0, 1, 1, 0, 2, ...]

        # 5. 后处理
        segments = self.post_process(speech_segs, labels, min_duration)
        # → [{start, end, speaker: "说话人1"}, ...]

        return segments
```

---

## 十一、用户工作流

```
┌──────────────────────────────────────────────────┐
│  1. 打开音频文件                                   │
│     python main.py meeting.wav                    │
├──────────────────────────────────────────────────┤
│  2. 点击 [🤖 自动识别]                              │
│     - 选择模式（快速/精准）                         │
│     - 点击开始                                     │
├──────────────────────────────────────────────────┤
│  3. 等待识别完成（进度条）                           │
│     → 波形上显示彩色片段                            │
│     → 片段列表自动填充                              │
│     → 状态栏：「检测到 3 个说话人，共 15 个片段」    │
├──────────────────────────────────────────────────┤
│  4. 人工修正                                       │
│     - 拖拽片段边缘调整时间                          │
│     - 双击修改说话人名称                            │
│     - 合并误拆分的片段                              │
│     - 删除误识别的片段                              │
├──────────────────────────────────────────────────┤
│  5. 导出标注结果                                   │
│     → TXT / CSV / XLSX                            │
└──────────────────────────────────────────────────┘
```

---

## 十二、总结

| 项目 | 方案 |
|---|---|
| 识别引擎 | Silero VAD（轻量） + SpeechBrain ECAPA-TDNN（embedding） |
| 聚类算法 | Agglomerative Clustering（层次聚类） |
| UI 集成 | 新增「自动识别」按钮 + 选项对话框，结果直接加载到现有 segments |
| 修正方式 | 在现有波形界面上拖拽/合并/拆分/删除 |
| 处理速度 | 轻量模式：1小时音频 ~30秒；精准模式：~3分钟 |
| 模型大小 | 轻量模式：~30MB（VAD + embedding）；精准模式：~300MB |
