# 增强读取组件

普通版首次使用增强读取时，从上游直接下载以下组件；离线增强版附带同样的组件。游戏文件和文本不会发送给这些服务。

| 组件 | 固定版本 | 来源及许可 |
| --- | --- | --- |
| BoxedWine | 25R1.0，Windows x64 | [上游发布](https://github.com/danoon2/Boxedwine/releases/tag/25R1.0)，[源代码](https://github.com/danoon2/Boxedwine/tree/25R1.0)，GNU GPL v2 |
| TinyCore / Wine 文件系统 | TinyCore15Wine9.0，第 5 版 | [上游下载索引](https://www.boxedwine.org/v2/26R1/filesV2.xml)，[构建说明](https://github.com/danoon2/Boxedwine/tree/25R1.0/tools/buildWine) |

Wine 使用 LGPL 2.1 或更新版本；文件系统中其他组件采用各自的许可。上游文件系统内附带 `build.txt`、`installed.txt` 和重建说明，Wine 对应源代码可在 [wine-9.0](https://gitlab.winehq.org/wine/wine/-/tree/wine-9.0) 获取。

离线增强版保留上游组件的原始压缩包。下载地址、大小和 SHA-256 固定在 `protected_reader.py`，在线或离线组件都必须通过校验后才能使用。

`vendor/protected_reader` 中的助手源码与本项目一起提供；它们通过独立进程和文件与模拟组件交互。
