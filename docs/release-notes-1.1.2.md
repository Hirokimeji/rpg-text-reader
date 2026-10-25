## 修复翻译文件误识别

- 修复打开游戏 EXE 时，将 `MTool_TilesetDefinedCache.json` 缓存文件列为翻译文件并导致提取失败的问题。
- 自动扫描现在会检查 JSON 内容，跳过已知缓存、配置文件，以及空字典、非字符串字典和无法读取的文件。
- 没有有效翻译文件时直接提取游戏内文本；有效的 MTool 译文仍可选择加载。
- 手动选择不支持的 JSON 时，提示文件类型及下一步操作。

下载 `textlight-1.1.2-windows-x64.zip`，解压后运行 `台词拾光.exe`；也可以单独下载 `Textlight.exe`。无需安装 Python、Excel 或 MTool。

从旧版升级时，关闭旧版程序，改用本版 EXE 即可。无需移动或删除游戏目录中的 MTool 文件。

`SHA256SUMS.txt` 提供附件校验值。
