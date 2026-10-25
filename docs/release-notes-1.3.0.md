## 新增 Unity 文本读取

- 支持选择 Windows Unity 游戏目录、游戏 EXE 或 `*_Data` 文件夹。
- 读取标准资源／AssetBundle 中的 TextAsset 和 StreamingAssets 中的文本文件。
- 解析可读取的 MonoBehaviour／ScriptableObject 对白结构，保留说话人、正文、选项与来源。
- Mono 数据缺少类型树时，从游戏附带的 Managed 程序集元数据恢复字段布局，不执行游戏代码。
- 按资源对象／剧本分组，支持应用内阅读、搜索、复制和 TXT／Excel 汇总或拆分导出。
- 阅读视图清理已知 Unity 富文本格式，保留原始文字、未知标记和重复台词的位置。

### 兼容性说明

Unity 的文本存储由各个游戏自行决定，当前支持标准资源与可解析的对象结构，不能保证覆盖所有 Unity 游戏。无法识别／解析的对象会在提取报告中说明。

暂不处理加密／自定义资源封装，不恢复 IL2CPP 缺失的类型树，也不读取图片文字或运行时动态拼接内容。资源／剧本的分组顺序不代表真实剧情发生顺序。

便携版已内置读取组件，无需安装 Python、Unity、.NET 或 Excel。

下载 `textlight-1.3.0-windows-x64.zip`，解压后运行 `台词拾光.exe`；也可单独下载 `Textlight.exe`。
