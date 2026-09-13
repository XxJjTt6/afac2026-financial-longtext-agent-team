# V73 Errors

## ERR-20260714-V73-001 inherited_github_token

**Status**: resolved

首次 GitHub 搜索继承了失效的 `GITHUB_TOKEN`，覆盖了钥匙串中的有效登录并返回
401。后续所有 GitHub CLI 调用统一使用 `env -u GITHUB_TOKEN gh ...`。

## ERR-20260714-V73-002 abbreviated_commit_typo

**Status**: resolved

两次手工抄写 YuK commit 时遗漏字符，`git show` 报 invalid object name。后续配置和
脚本全部固化完整 40 位 commit，并用 vendored CSV 的 SHA256 做二次校验。

## ERR-20260714-V73-003 wrong_virtualenv_workdir

**Status**: resolved

在项目上级目录调用相对路径 `.venv/bin/python` 失败。后续命令固定在仓库根目录执行，
跨目录时使用仓库虚拟环境的绝对路径。

## ERR-20260714-V73-004 zsh_nomatch_on_optional_glob

**Status**: resolved

一次公开仓库文件盘点使用不存在的 `baseline/*.csv`，触发 zsh `nomatch` 并中止后续
命令。后续可选文件集合改用 `find` 或先验证目录存在。

## ERR-20260714-V73-005 out_of_range_count_relaxation

**Status**: resolved

单元测试发现，对正确数为 0 的玩具行尝试 `-1` 松弛时会在底层约束器触发越界异常。
枚举器现已在求解前跳过不属于 `[0, 题目数]` 的松弛值，并由回归测试覆盖。

## ERR-20260714-V73-006 csv_line_ending_hash_drift

**Status**: resolved

四条 Kafka 外部 CSV 原始文件为 CRLF，而仓库 `.gitattributes` 会在 Git 对象中归一化
为 LF，导致首次提交后的 blob 哈希与配置里的原始哈希不同。V73 现将 vendored 文件
显式规范为 LF，`sha256` 校验可复现的仓库内容，并另存 `source_sha256` 保留上游字节
指纹。
