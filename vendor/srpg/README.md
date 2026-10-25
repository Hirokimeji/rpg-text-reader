# SRPG Studio parser

This directory contains the unmodified `SRPG_Unpacker.exe` from
[Sinflower/SRPG-ToolBox v0.1.2](https://github.com/Sinflower/SRPG-ToolBox/releases/tag/v0.1.2).

- License: MIT, Copyright (c) 2024 Sinflower. See [LICENSE](LICENSE).
- Download: https://github.com/Sinflower/SRPG-ToolBox/releases/download/v0.1.2/SRPG_Unpacker.exe
- SHA-256: `bf38aace603d1852e1684e8ae0505f6c35b4c912c46bbd9fda78377ff97f6462`
- Release source: https://github.com/Sinflower/SRPG-ToolBox/tree/d444bdfc56fc4784e0352bfb232f79232567c05d
- Archive-format reference reviewed: https://github.com/Sinflower/SRPG-ToolBox/tree/9326904865b913fbdc9f931c3e45056357ea1640

Textlight invokes only the `project.dat -c -o <temporary directory>` text-export
operation. The game-data project segment and a generated config are copied into
temporary storage. Game executables and scripts are never run. Resource unpacking,
patch application, and game-file writes are not used.

The adapter's archive-header handling follows the upstream `FileHeader.cpp`
format. The upstream license is retained here for both the component and format
adaptation. The release executable is checksum-verified before every invocation.
