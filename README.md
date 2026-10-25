<div align="center">

<img src="docs/images/icon.png" width="88" alt="台词拾光图标">

# 台词拾光 · Textlight

**把游戏里的文字，整理成方便阅读和检索的创作参考。**

Windows 图形化 RPG Maker 文本提取器 · 内嵌汉化 / MTool 译文 · TXT / Excel 导出

[下载便携版](https://github.com/Hirokimeji/rpg-text-reader/releases/latest) · [快速开始](#快速开始) · [支持范围](#支持范围) · [反馈问题](https://github.com/Hirokimeji/rpg-text-reader/issues)

![Windows](https://img.shields.io/badge/Windows-10%20%2F%2011-0078D4)
![Version](https://img.shields.io/badge/version-1.1.1-146C67)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)

</div>

台词拾光面向需要查找游戏对白、整理音声台本参考的朋友。选择游戏文件夹后，程序会识别受支持的游戏数据和翻译文件，把文字按地图、事件和事件页整理出来。提取后可以直接在应用中阅读、搜索、复制和导出。

![台词拾光界面预览](docs/images/preview.png)

*图中为程序内的演示数据，不包含实际游戏的文本或素材。*

## 下载与运行

到 [Releases 页面](https://github.com/Hirokimeji/rpg-text-reader/releases/latest) 下载 `textlight-1.1.1-windows-x64.zip`，解压后双击 `台词拾光.exe`。

**无需安装 Python、Excel 或 MTool，也无需启动游戏。** 适用于 Windows 10 / 11 的 64 位电脑。

GitHub 的 **Code → Download ZIP** 下载的是源码；普通使用者请下载 Releases 里的便携包。

## 能做什么

| 功能 | 说明 |
| --- | --- |
| 识别文本来源 | 读取游戏内现有文字，或关联 MTool 的原文—译文 JSON 字典；多份译文可以选择版本 |
| 整理场景 | 按地图 → 事件 → 事件页浏览；公共事件、战斗事件、数据库和其他数据分别归类 |
| 应用内阅读 | 默认译文优先，可查看原文、译文、原始文字和来源位置；支持分页连续阅读 |
| 搜索与复制 | 检索台词、原文、说话人和场景，按类别或匹配状态筛选，跨页复制筛选结果 |
| TXT 导出 | 适合直接阅读和整理台本，可选原译对照、保留原始控制符 |
| Excel 导出 | 保留分类、场景、说话人、原文、译文、匹配状态和来源位置，方便进一步筛选 |
| 汇总或拆分 | 导出全部、当前筛选结果或选中的文本；可按事件页／公共事件分别生成文件 |

TXT 正文、连续阅读和复制内容中不会反复插入“触发类型”“开关编号”等条件说明。

## 快速开始

1. **打开游戏**：点击“选择游戏文件夹”，或把文件夹、游戏 EXE、翻译 JSON 拖到窗口。把工具 EXE 放入游戏主目录后启动，也可以自动识别该目录。
2. **选择来源**：已经内嵌汉化的游戏可选择“只读取游戏内文本”；使用 MTool 的游戏请选择对应翻译文件。如果翻译文件在其他位置，先打开游戏，再点“切换翻译文件”。
3. **找台词**：左侧选场景，中间输入关键词，右侧阅读所选文字。默认仅显示对白、滚动文字和选项，切换“所有文本类别”可以查看物品、技能、菜单等。
4. **看上下文**：点击“连续阅读”。列表每页显示 200 条，连续阅读每页显示 100 条；搜索和导出会覆盖全部符合条件的页面。
5. **导出**：点击“导出文本”，选择范围和 TXT / Excel 格式。需要拆分时勾选“场景拆分”。每次导出都会建立新的文件夹。

> 只打开翻译 JSON 也能阅读和导出；没有配套游戏数据时，条目会保留在“未关联场景”中。

## 支持范围

| 来源 | 当前支持 | 识别依据 |
| --- | --- | --- |
| RPG Maker MV | ✅ 可读取的标准数据 | `data/*.json` 或 `www/data/*.json`，以及对应引擎文件 |
| RPG Maker MZ | ✅ 可读取的标准数据 | `data/*.json`，以及对应引擎文件 |
| RPG Maker VX Ace | ✅ 已展开的数据 | `Data/*.rvdata2` |
| MTool 翻译 | ✅ 字符串字典 | JSON 中的键和值分别为原文、译文字符串 |
| RPG Maker XP / VX | 暂不支持 | `.rxdata` / `.rvdata` |
| RGSS 加密归档、特殊封装 | 暂不支持 | 需要另外适配 |
| 图片中的文字 | 暂不支持 | 当前不包含 OCR |

**游戏图标的颜色不能准确代表数据格式。** 同样是“红色龙头”，也可能属于不同版本；程序按文件结构识别。

MTool 支持的字典示例：

```json
{
  "こんにちは。": "你好。",
  "旅に出る準備はできた？": "准备好出发旅行了吗？"
}
```

## 阅读与提取规则

- 同一对话框的多行合并成一条记录，保留换行。相同台词出现在不同场景时，分别保留位置，不自动去重。
- MTool 译文先匹配完整对话框，再逐行匹配。有译文时优先显示译文；“部分匹配”表示仍有未翻译的行，“未匹配”显示原文。
- “游戏内文本”表示游戏文件中现存的文字，不代表程序自动判断了它是否已汉化。工具本身不提供机器翻译。
- `〔变量#3〕`、`〔角色#2〕` 等是游戏运行时决定的内容，不擅自替换成固定值；未知插件控制符保留。
- 说话人有可靠标注时才提取。事件页条件与分支信息可在“原始／来源”及 Excel 的独立列中查阅。
- 场景按游戏数据结构排列，**不等于实际剧情发生顺序**。公共事件单列，不在每个调用位置重复展开。
- 脚本、注释和插件参数单独分类，其中可能包含内部参数。动态拼接文字、特殊插件和非标准数据可能无法完整覆盖。

## 导出的文件

TXT 使用 UTF-8 BOM，方便 Windows 记事本读取。Excel 的长文本会拆成续段，避免超过单元格长度限制。

```text
台词拾光_日期_时间/
├─ 00001_游戏名称_汇总.txt     # 或 .xlsx；也可以按场景生成多个文件
└─ 导出清单.json              # 来源、提取说明与文件列表
```

取消或失败的导出目录会保留 `导出未完成.txt` 标记；`.part` 文件是尚未完成的结果。

## 本地处理

应用在本机读取和导出文字，不联网、不上传游戏内容、不启动游戏，也不修改游戏文件。VX Ace 数据由纯数据解析器读取，不运行 Ruby 脚本或反序列化回调。

出现错误时，日志保存在 `%LOCALAPPDATA%\台词拾光\error.log`。反馈问题时可以提供引擎版本、报错信息与不含私人内容的最小样例。

## 从源码运行与构建

需要 Windows 和 Python 3.12：

```powershell
git clone https://github.com/Hirokimeji/rpg-text-reader.git
cd rpg-text-reader
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

运行针对性测试：

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_engine test_gui.GuiTests test_rgss
```

生成独立 EXE 与便携包：

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm textlight.spec
.\.venv\Scripts\python.exe package_release.py
```

EXE 位于 `dist/`，便携包位于 `release/`。测试覆盖译文匹配、场景保留、导出、长文本、分页、拖放与 VX Ace 数据解析；已使用 MV、MZ、VX Ace 的实际样本验证提取和 TXT / Excel 导出。

## 项目结构

```text
app.py                 图形界面、阅读、搜索和任务管理
engine.py              引擎识别、场景整理和译文匹配
rgss.py                VX Ace 的 Ruby Marshal 数据解析
exporter.py            TXT / Excel 导出
textlight.spec         PyInstaller 打包配置
package_release.py     便携包与第三方许可整理
test_*.py              针对性测试
docs/                  界面示例与文档资源
```

## 更新记录

### 1.1.1

- TXT 正文、连续阅读和复制内容不再插入触发条件、开关编号等说明。

### 1.1

- 增加 RPG Maker VX Ace 已展开的 `.rvdata2` 数据支持。

### 1.0

- 支持 MV / MZ、MTool 译文关联、图形化阅读、搜索、场景分类及 TXT / Excel 导出。

## 第三方组件

使用 Python、PySide6 / Qt、openpyxl 和 PyInstaller。便携包附带“第三方许可”与可重新构建的源文件；Qt / PySide6 的 LGPL 文本也保存在 [`third_party/`](third_party/) 中。
