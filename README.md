<div align="center">

<img src="docs/images/icon.png" width="80" alt="台词拾光图标">

# 台词拾光 · Textlight

RPG Maker / SRPG Studio / Unity 游戏文本提取与阅读工具

支持游戏内文本与 MTool 译文，提供场景浏览、全文搜索和 TXT / Excel 导出。

[下载 Windows 便携版](https://github.com/Hirokimeji/rpg-text-reader/releases/latest) · [使用方法](#使用方法) · [兼容性](#兼容性) · [问题反馈](https://github.com/Hirokimeji/rpg-text-reader/issues)

![Windows](https://img.shields.io/badge/Windows-10%20%2F%2011-0078D4)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)

</div>

台词拾光将游戏文件中的对白、选项和其他文字整理为可检索的文本库。你可以按场景阅读剧情、查看原文与译文，也可以将所需内容导出，用于文本查阅、翻译核对或台本整理。

所有处理均在本地完成，无需启动游戏，不修改游戏文件。

界面采用紫色与粉色的手账风格，搭配像素角色、分区卡片和浅雾紫阅读页。

![台词拾光界面](docs/images/preview.png)

*界面预览使用虚构的演示文本。*

## 主要功能

- **文本提取**：读取对白、选项、滚动文字，以及角色、物品、技能等数据库文本。
- **译文关联**：加载 MTool 翻译 JSON，保留原文与译文，并标记匹配情况。
- **场景浏览**：按地图、事件和事件页组织文本，支持连续阅读。
- **Unity 文本**：读取文本资源、外置文本及可解析的托管对白对象，按资源／剧本浏览。
- **搜索筛选**：通过关键词、文本类别和译文匹配状态查找内容，复制所需片段。
- **灵活导出**：将全部文本、筛选结果或选中条目导出为 TXT / Excel，可汇总为单个文件，也可按场景拆分。

## 下载

在 [Releases](https://github.com/Hirokimeji/rpg-text-reader/releases/latest) 中下载 `textlight-*-windows-x64.zip`，解压后运行 `台词拾光.exe`。

运行环境：**Windows 10 / 11，64 位**。便携版无需安装 Python、Excel 或 MTool。

> GitHub 的 **Code → Download ZIP** 下载的是项目源码。直接使用应用请下载 Releases 中的便携包。

## 使用方法

### 1. 打开游戏

点击“选择游戏文件夹”，或将游戏文件夹、游戏 EXE 拖入窗口。也可以把工具放在游戏主目录中运行，由程序自动识别。

### 2. 加载文本

内嵌汉化游戏直接读取游戏内文本。使用外部译文时，选择识别到的 MTool 翻译文件；文件位于其他目录时，点击“切换翻译文件”手动加载。

也可以单独打开翻译 JSON。未关联游戏数据时，文本归入“未关联场景”。

### 3. 阅读与查找

在左侧选择场景，通过搜索框查找台词，在右侧查看所选条目的内容。默认显示剧情对白与选项，并优先展示译文；切换“所有文本类别”可查看数据库等其他文字。

点击“连续阅读”可浏览场景中的文本。搜索与导出作用于全部符合条件的条目，不受当前显示页限制。

### 4. 导出

点击“导出文本”，选择导出范围与文件格式。启用“场景拆分”后，每个事件页或公共事件分别生成文件。

| 格式 | 适用场景 | 内容 |
| --- | --- | --- |
| TXT | 阅读、复制、台本整理 | 按场景排列的正文，可选原译对照或保留原始控制符 |
| Excel（.xlsx） | 筛选、核对、进一步整理 | 场景、说话人、原文、译文、匹配状态及来源等独立字段 |

每次导出会创建独立文件夹，附带记录来源和文件列表的 `导出清单.json`。TXT 使用 UTF-8 BOM 编码。

## 兼容性

| 来源 | 支持的数据格式 |
| --- | --- |
| RPG Maker MV | 标准 JSON 数据，通常位于 `data/` 或 `www/data/` |
| RPG Maker MZ | 标准 JSON 数据，通常位于 `data/` |
| RPG Maker VX Ace | 已展开的 `Data/*.rvdata2` |
| SRPG Studio | 引擎 1.140–1.322 的标准未加密 `data.dts` 项目数据 |
| Unity（Windows） | TextAsset、StreamingAssets 中的文本，以及带类型树或可通过 Mono 元数据解析的对白对象 |
| MTool 翻译文件 | 原文与译文均为字符串的 JSON 字典 |

MTool 字典格式示例：

```json
{
  "こんにちは。": "你好。",
  "準備はできた？": "准备好了吗？"
}
```

目前不支持 RPG Maker XP / VX、RGSS 加密归档及图片文字识别。特殊封装、非标准插件和运行时动态生成的文字可能无法完整提取。

SRPG Studio 支持地图事件、角色事件、公共事件及数据库文本，读取项目内现存的文字。暂不读取加密项目及外部 `language.dat` / `localization.dat` 翻译层；不同游戏的数据结构仍可能存在兼容性差异。

### Unity 支持范围

选择游戏主目录、游戏 EXE 或对应的 `*_Data` 文件夹。程序读取标准资源文件／AssetBundle 中的 TextAsset，以及 `StreamingAssets` 中的 TXT、JSON、CSV 等文本。可识别的对白结构保留说话人、正文与选项；未识别的文字保存在“其他文本”类别中。

Mono 游戏缺少字段类型树时，会尝试读取 `Managed/` 中的程序集元数据来恢复结构。该过程不执行游戏程序集。内置类型树可读的对象也可直接处理；当前不恢复 IL2CPP 缺失的类型树，不处理加密／自定义封装，也不保证覆盖运行时动态生成的文字。

Unity 使用资源对象或剧本作为场景分组，不能据此还原实际游玩顺序。已知富文本格式会在阅读视图中清理，未知标记与原始内容仍然保留。提取报告会列出无法识别／解析的对象，完成提取不代表所有文字均已覆盖。

### 文本与场景的处理方式

- 场景依据游戏数据结构组织，不代表实际游玩顺序；公共事件独立列出，不在调用位置展开。
- 同一对话框的多行文字合并显示并保留换行；不同场景中的重复台词保留各自位置。
- 译文先按完整对话框匹配，再尝试逐行匹配。未匹配的内容显示原文，工具本身不提供机器翻译。
- 已内嵌汉化的数据按现有内容读取，无法从中恢复汉化前的原文。
- 变量与角色引用保留为 `〔变量#3〕`、`〔角色#2〕` 等占位符，实际值由游戏运行状态决定。
- 触发条件等事件信息可在详情及 Excel 中查看，TXT 正文仅保留阅读所需内容。

## 开发

使用 Windows 与 Python 3.12：

```powershell
git clone https://github.com/Hirokimeji/rpg-text-reader.git
cd rpg-text-reader
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_engine test_gui.GuiTests test_rgss test_srpg test_unity
```

构建 EXE 与便携包：

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm textlight.spec
.\.venv\Scripts\python.exe package_release.py
```

构建结果分别位于 `dist/` 和 `release/`。界面使用 PySide6，提取与译文匹配位于 `engine.py`，VX Ace 数据解析位于 `rgss.py`，SRPG Studio 适配位于 `srpg.py`，Unity 适配位于 `unity_reader.py`，导出逻辑位于 `exporter.py`。SRPG 解析组件随源码保存在 `vendor/srpg/`，无需另行下载。

## 问题反馈

请通过 [Issues](https://github.com/Hirokimeji/rpg-text-reader/issues) 提交问题，并附上应用版本、游戏引擎、操作步骤与报错信息。错误日志位于 `%LOCALAPPDATA%\台词拾光\error.log`。

如需提供样例，请使用可公开分享的最小数据，并移除私人信息。

## 第三方组件

本项目使用 Python、PySide6 / Qt、openpyxl 和 PyInstaller。便携包附带第三方许可说明；Qt / PySide6 的 LGPL 相关许可证文本见 [`third_party/`](third_party/)。

SRPG Studio 的结构解析使用 [Sinflower/SRPG-ToolBox](https://github.com/Sinflower/SRPG-ToolBox) v0.1.2（MIT）。组件来源、校验值及许可证见 [`vendor/srpg/`](vendor/srpg/)。组件随程序打包，在本地临时目录中读取数据，不执行游戏脚本。

Unity 资源读取使用 [UnityPy](https://github.com/K0lb3/UnityPy) 1.25.3，托管元数据解析使用 TypeTreeGeneratorAPI 0.0.10；相关组件随便携版附带，无需安装 Unity 或 .NET 运行时。
