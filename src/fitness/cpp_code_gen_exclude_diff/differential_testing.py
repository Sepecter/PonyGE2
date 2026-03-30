import os
from os import path
from algorithm.parameters import params


_GCC_ICE_PATTERNS = (
    "internal compiler error",
    "please submit a full bug report",
    "please submit a bug report",
    "compiler error:",
    "segmentation fault",
    "stack dump",
)

_CLANG_ICE_PATTERNS = (
    "clang: error:",
    "clang: fatal error:",
    "stack dump",
    "PLEASE submit a bug report",
    "llvm error",
    "Assertion `",
    "Assertion failed",
    "segmentation fault",
)


def _looks_like_ice(compiler: str, stderr_text: str) -> bool:
    if not stderr_text:
        return False

    text = stderr_text.lower()
    patterns = _GCC_ICE_PATTERNS if compiler == "gcc" else _CLANG_ICE_PATTERNS
    return any(pattern.lower() in text for pattern in patterns)


def differential_testing(gcc_errors, clang_errors, code, time, compiling_result):
    """
    Experimental setting:
      - no differential-testing filter
      - no deduplication

    Any compiler abnormality (one-pass-one-fail or both-fail, including ICE/crash)
    is recorded as a defect candidate.
    """
    out_dir = path.join(params['FILE_PATH'], "code_results", "exclude_diff")
    os.makedirs(out_dir, exist_ok=True)

    gcc_ice = _looks_like_ice("gcc", gcc_errors)
    clang_ice = _looks_like_ice("clang", clang_errors)

    if compiling_result == 3:
        return 0

    if gcc_ice or clang_ice:
        report_path = path.join(out_dir, f"{time}_CRASH.txt")
        with open(report_path, "w") as f:
            if gcc_ice:
                f.write("=== GCC ICE/CRASH ===\n")
                f.write(gcc_errors or "")
                f.write("\n")
            if clang_ice:
                f.write("=== CLANG ICE/CRASH ===\n")
                f.write(clang_errors or "")
                f.write("\n")
        return 1

    report_path = path.join(out_dir, f"{time}_RAW_FAILURE.txt")
    with open(report_path, "w") as f:
        f.write(f"compiling_result={compiling_result}\n\n")
        f.write("=== gcc stderr ===\n")
        f.write(gcc_errors or "")
        f.write("\n=== clang stderr ===\n")
        f.write(clang_errors or "")

    return 1

