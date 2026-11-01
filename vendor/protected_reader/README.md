# 兼容读取助手

这些助手只供台词拾光的隔离读取流程使用。`version.dll` 在模拟环境中的游戏副本内读取已知数据路径；`launcher.exe` 管理同一模拟环境中的子进程。它们不向宿主系统中的游戏进程注入代码。

`isolation_check.exe` 在读取前检查 AppContainer 身份、外部测试文件的读写限制，以及网络连接限制。检查失败时不会运行模拟组件。

重建需要 Zig，或目标为 32 位 Windows 的 MinGW 编译器：

```powershell
py build_reader_helpers.py --zig C:\Tools\zig\zig.exe
```

BoxedWine 与 Wine 文件系统不打入本项目的 EXE。普通便携包首次增强读取时从上游下载固定版本；离线增强包附带同样的上游组件。两者均校验 SHA-256 后使用。来源、版本和许可见 `third_party/compat-reader-notices.md`。
