# C++ Code Generation 使用说明

这份说明针对 `src/fitness/` 下的 C++ code generation fitness，以及 `src/` 下用于批量运行的 `.sh` 和错误过滤 `.txt` 文件。

## 目录概览

相关 fitness 目录：

- `src/fitness/cpp_code_gen/`
- `src/fitness/cpp_code_gen_v2/`
- `src/fitness/cpp_code_gen_exclude_diff/`
- `src/fitness/cpp_code_gen_exclude_errors/`

每个目录通常包含：

- `code_eval.py`: PonyGE2 的 fitness function，负责接收个体 phenotype、补全标识符、调用编译器、计算 fitness。
- `differential_testing.py`: 根据 GCC/Clang 编译结果判断是否为有价值的差分 case、ICE/crash 或已知问题。
- `__init__.py`: Python package 标记文件。

## 基本流程

1. PonyGE2 根据 grammar 生成 C++ phenotype。
2. `code_eval.py` 将 phenotype 中的 `Identifier` 随机替换为 `X0`、`X1` 等标识符。
3. 使用两个编译器分别编译同一段 C++ 代码。
4. 根据编译结果 bitmask 判断状态：
   - `1`: GCC 编译成功，Clang 失败。
   - `2`: Clang 编译成功，GCC 失败。
   - `3`: 两边都成功。
   - `0`: 两边都失败。
5. 必要时调用 `differential_testing.py` 做差分判断、去重、过滤已知错误，并保存触发 case。
6. 返回 fitness。当前几个版本主要用代码长度和 token 种类数构造结构性 fitness；部分版本会把新差分结果映射为更优 fitness。

## 四个 fitness 版本

### `cpp_code_gen`

参数文件示例：

```text
parameters/code_gen.txt
```

配置中使用：

```text
FITNESS_FUNCTION: cpp_code_gen.code_eval
GRAMMAR_FILE: c++/selected_bnf.bnf
```

特点：

- 使用 `g++-15-cov` 和 `clang++-20`。
- 会把 Clang stderr 写入 `code_results/bin/<timestamp>_clang_error.txt`。
- 对 crash 文本和一边成功一边失败的情况做较早期的差分检测。
- 新的差分结果会触发 `results/diff/diff.txt`。
- 触发缺陷程序会保存到 `results/bugs/`。

### `cpp_code_gen_v2`

参数文件示例：

```text
parameters/code_gen_v2.txt
parameters/abla_RL_code_gen.txt
```

配置中使用：

```text
FITNESS_FUNCTION: cpp_code_gen_v2.code_eval
```

特点：

- 使用 `g++-16` 和 `clang++-trunk`。
- `code_gen_v2.txt` 使用 `c++/selected_bnf.bnf`，适合 RL 生成 grammar 后调用。
- `abla_RL_code_gen.txt` 使用 `c++/full.bnf`，适合作为 full grammar 的对照实验。
- `differential_testing.py` 增加了更细的诊断解析、warning/error 可互转过滤、fingerprint 去重。
- 会把已知 ICE 保存到 `results/known_ice/`，已知普通 bug 保存到 `results/known_bugs/`。
- 新 ICE 保存到 `results/ice/`，新差分 case 保存到 `results/bugs/`。
- 如果触发了已见/已知问题但不是新 bug，会写 `results/diff/diff_dup.txt`。
- 如果发现新差分 bug，会写 `results/diff/diff_new.txt`。

### `cpp_code_gen_exclude_diff`

参数文件：

```text
parameters/abla_GE_exclude_diff.txt
```

配置中使用：

```text
FITNESS_FUNCTION: cpp_code_gen_exclude_diff.code_eval
GRAMMAR_FILE: c++/full.bnf
```

特点：

- 用于消融实验：不使用在线差分测试结果指导 fitness。
- 编译和 defect 检测仍会执行，用于保证运行成本和 case 收集公平。
- `differential_testing.py` 不做差分过滤和去重；只要编译异常，包括一边成功一边失败、两边失败、ICE/crash，都会记录为候选。
- 触发代码保存到 `results/code/exclude_diff/`。
- 诊断报告保存到 `code_results/exclude_diff/`。
- fitness 只基于结构指标计算，不因发现 bug 直接变优。

### `cpp_code_gen_exclude_errors`

参数文件：

```text
parameters/abla_GE_exclude_errors.txt
```

配置中使用：

```text
FITNESS_FUNCTION: cpp_code_gen_exclude_errors.code_eval
GRAMMAR_FILE: c++/full.bnf
```

特点：

- 用于消融实验：保留差分测试逻辑，但去掉已知错误过滤和去重抑制。
- 使用 `g++-16` 和 `clang++-trunk`。
- ICE/crash 会直接返回有效差分结果。
- 一边成功一边失败时，仍会做诊断解析和 warning/error 可互转过滤。
- 报告保存到 `code_results/exclude_errors/`。
- 触发 case 根据类型保存到 `results/ice/` 或 `results/diff/`。
- 如果触发异常但没有新差分结果，会写 `results/diff_exclude_errors/diff_dup.txt`。
- 如果发现新差分结果，会写 `results/diff_exclude_errors/diff_new.txt`。

## 运行脚本

脚本都在 `src/` 目录下，建议先进入 `src` 再运行：

```bash
cd src
```

### `repeat_run.sh`

运行：

```bash
python ponyge.py --parameters code_gen_v2.txt
```

默认行为：

- 每 5 秒检查一次。
- 最多同时运行 8 个进程。
- 使用 `parameters/code_gen_v2.txt`。
- 适合配合 RL 生成的 `grammars/c++/selected_bnf.bnf` 做主实验。

### `ablation_RL_run.sh`

运行：

```bash
python ponyge.py --parameters abla_RL_code_gen.txt
```

默认行为：

- 每 5 秒检查一次。
- 最多同时运行 8 个进程。
- 最长启动 24 小时，之后停止启动新任务并等待已启动任务结束。
- 使用 full grammar 和 `cpp_code_gen_v2`，作为 RL/selected grammar 的对照。

### `ablation_GE_exclude_diff_run.sh`

运行：

```bash
python ponyge.py --parameters abla_GE_exclude_diff.txt
```

默认行为：

- 每 5 秒检查一次。
- 最多同时运行 2 个进程。
- 最长启动 24 小时。
- 使用 `cpp_code_gen_exclude_diff`，用于“不用差分结果指导 fitness”的消融实验。

### `ablation_GE_exclude_errors_run.sh`

运行：

```bash
python ponyge.py --parameters abla_GE_exclude_errors.txt
```

默认行为：

- 每 5 秒检查一次。
- 最多同时运行 2 个进程。
- 最长启动 24 小时。
- 使用 `cpp_code_gen_exclude_errors`，用于“保留差分逻辑但不做已知错误过滤/去重”的消融实验。

### `repeat_run_cangjie.sh`

运行：

```bash
python ponyge.py --parameters cangjie_gen.txt
```

默认行为：

- 每 5 秒检查一次。
- 最多同时运行 4 个进程。
- 面向 Cangjie 生成实验，不属于本文档重点的 C++ code generation fitness。

## `src/*.txt` 文件

`src` 下的 `.txt` 文件是已知错误/已知 crash 的正则模式库：

- `gcc_errors.txt`: GCC 普通错误模式。
- `gcc_crash.txt`: GCC ICE/crash 模式。
- `clang_errors.txt`: Clang 普通错误模式。
- `clang_crash.txt`: Clang ICE/crash 模式。

这些文件的用途是过滤已经见过或已知的问题，避免相同类型的编译器错误反复被当作新 bug。`cpp_code_gen_v2` 的差分测试逻辑会读取这些模式，并把匹配到的 case 归入 known 类别。

## 常见输出目录

- `results/code/`: 保存生成的源码或部分触发 case。
- `results/bugs/`: 保存判定为新差分 bug 的源码。
- `results/ice/`: 保存新 ICE/crash 源码。
- `results/known_bugs/`: 保存匹配已知普通错误模式的源码。
- `results/known_ice/`: 保存匹配已知 ICE/crash 模式的源码。
- `results/diff/`: 主实验的差分标记文件，例如 `diff_new.txt`、`diff_dup.txt`。
- `results/diff_exclude_errors/`: `exclude_errors` 消融实验的差分标记文件。
- `code_results/`: 编译中间产物和差分测试报告，通常位于参数中的 `FILE_PATH` 下。

## 注意事项

- 这些脚本假设系统中存在对应编译器命令，例如 `g++-16`、`clang++-trunk`、`g++-15-cov`、`clang++-20`。
- `repeat_run.sh` 和 `repeat_run_cangjie.sh` 当前脚本注释存在乱码，但核心变量和命令可读。
- `repeat_run.sh` 与 `repeat_run_cangjie.sh` 中 `total` 和 `while` 相关行在源码里注释粘连，实际运行前建议确认循环条件是否符合预期。
- 如果从 RL 流程调用，`GE-RL` 会先写 `grammars/c++/selected_bnf.bnf`，再调用 `src/repeat_run.sh`。
