# 自动化测试设计

## 目标

手动音频打标软件的高风险逻辑集中在数据保存、时间处理、片段编辑和导出格式。自动化测试优先覆盖这些纯逻辑边界，避免依赖真实音频设备、文件选择器或图形显示环境。

## 测试分层

| 层级 | 覆盖内容 | 测试方式 |
|---|---|---|
| 数据模型 | Segment/Speaker/Project 序列化、排序、拆分、合并、边缘调整、重叠检测 | `tests/test_models.py` |
| 导出逻辑 | 时间解析、时间格式化、CLI 导出、CSV 转义、TXT 输出 | `tests/test_main_logic.py` |
| 冒烟检查 | 核心模块可导入，避免循环导入和缺失依赖 | `tests/test_smoke.py` |

## 暂不自动化的部分

- Tkinter 真实窗口交互
- 声卡播放链路
- 文件选择器弹窗
- 鼠标拖拽波形的端到端操作

这些部分适合后续用 Playwright/Sikuli 或平台原生 GUI 自动化工具做单独的端到端测试。目前先保证核心业务逻辑可重复验证。

## 运行命令

```bash
env PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests
```

使用 `PYTHONDONTWRITEBYTECODE=1` 是为了避免测试生成 `__pycache__` 干扰工作区状态。
