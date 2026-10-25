## 新增 SRPG Studio 支持

- 识别 SRPG Studio 游戏文件夹、游戏 EXE 和 `data.dts`。
- 提取项目中的对白、选项、角色及数据库文本，按地图、事件和事件页组织。
- 直接在应用内搜索、连续阅读、复制，或汇总／按场景导出 TXT 和 Excel。
- 清理已知的 SRPG 显示控制符，保留未知控制符与运行时变量。
- 内置 SRPG-ToolBox 解析组件，无需单独安装；仅在本地临时目录处理数据，不运行游戏，也不修改游戏文件。

### 支持范围

本版支持 SRPG Studio 1.140–1.322 的标准未加密 `data.dts` 项目数据。暂不支持加密项目、外部 `language.dat` / `localization.dat` 翻译层、图片文字和插件运行时动态文字。部分自定义数据结构可能需要进一步适配。

原有 RPG Maker MV / MZ / VX Ace 与 MTool 功能继续可用。

### 下载

下载 `textlight-1.2.0-windows-x64.zip`，解压后运行 `台词拾光.exe`；也可单独下载 `Textlight.exe`。升级时关闭旧版，改用新版 EXE 即可。

SRPG 组件：[Sinflower/SRPG-ToolBox v0.1.2](https://github.com/Sinflower/SRPG-ToolBox/releases/tag/v0.1.2)，采用 MIT 许可证。许可与组件信息随便携包提供。
