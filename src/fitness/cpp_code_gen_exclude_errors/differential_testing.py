import os
from os import path
import re
from typing import Optional
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
    s = stderr_text.lower()
    pats = _GCC_ICE_PATTERNS if compiler == "gcc" else _CLANG_ICE_PATTERNS
    for p in pats:
        if p.lower() in s:
            return True
    return False


def _sev_class(sev: str) -> str:
    if not sev:
        return "unknown"
    s = sev.lower()
    if "warning" in s:
        return "warning"
    if "error" in s or "fatal" in s:
        return "error"
    if "note" in s:
        return "note"
    return "other"


def _is_warning_convertible(opt: Optional[str]) -> bool:
    if not opt:
        return False
    if opt == "-fpermissive":
        return True
    if opt.startswith("-W") and not opt.startswith("-Werror"):
        return True
    return False


def _is_convertible_pair(g: dict, c: dict) -> bool:
    if not g or not c:
        return False

    g_cls = _sev_class(g.get("sev", ""))
    c_cls = _sev_class(c.get("sev", ""))
    if g_cls not in ("warning", "error") or c_cls not in ("warning", "error"):
        return False

    g_base = (g.get("msg_base") or "").strip()
    c_base = (c.get("msg_base") or "").strip()
    if not g_base or not c_base:
        return False

    return g_base == c_base


def parse_diagnostics(stderr_text: str):
    items = []
    if not stderr_text:
        return items

    for line in stderr_text.splitlines():
        line = line.strip()
        if not line:
            continue

        loc = None
        sev = None
        msg = line
        opt = None

        m = re.match(r"^(.*?):(\d+):(\d+):\s*([^:]+):\s*(.*)$", line)
        if m:
            loc = f"{m.group(1)}:{m.group(2)}:{m.group(3)}"
            sev = m.group(4).strip()
            msg = m.group(5).strip()
        else:
            m2 = re.match(r"^(.*?):(\d+):\s*([^:]+):\s*(.*)$", line)
            if m2:
                loc = f"{m2.group(1)}:{m2.group(2)}"
                sev = m2.group(3).strip()
                msg = m2.group(4).strip()
            else:
                m3 = re.match(r"^([^:]+):\s*(.*)$", line)
                if m3:
                    sev = m3.group(1).strip()
                    msg = m3.group(2).strip()

        mopt = re.search(r"(?:\s*\[(?P<opt>-(?:Werror(?:=[\w-]+)?|W[\w-]+|fpermissive))\]\s*)$", msg)
        if mopt:
            opt = mopt.group("opt")
            msg_base = msg[:mopt.start()].rstrip()
        else:
            msg_base = msg.strip()

        items.append({
            "loc": loc,
            "sev": sev,
            "msg": msg,
            "msg_base": msg_base,
            "opt": opt,
        })

    return items


def _eliminate_convertible_mismatches(g_items, c_items):
    g_drop = set()
    c_drop = set()

    for gi, g in enumerate(g_items):
        for ci, c in enumerate(c_items):
            if _is_convertible_pair(g, c):
                g_drop.add(gi)
                c_drop.add(ci)

    g_keep = [it for i, it in enumerate(g_items) if i not in g_drop]
    c_keep = [it for i, it in enumerate(c_items) if i not in c_drop]
    return g_keep, c_keep


def differential_testing(gcc_errors, clang_errors, code, time, compiling_result):
    """
    Experimental setting:
      - keep differential-testing logic
      - remove deduplication / known-error suppression
    """
    out_dir = path.join(params['FILE_PATH'], "code_results", "exclude_errors")
    os.makedirs(out_dir, exist_ok=True)

    gcc_ice = _looks_like_ice("gcc", gcc_errors)
    clang_ice = _looks_like_ice("clang", clang_errors)

    if gcc_ice or clang_ice:
        report_path = path.join(out_dir, f"{time}_ICE.txt")
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

    if compiling_result not in (1, 2):
        return 0

    g_items_all = parse_diagnostics(gcc_errors)
    c_items_all = parse_diagnostics(clang_errors)

    if compiling_result == 1:
        succ_items = g_items_all
        fail_items = c_items_all
    else:
        succ_items = c_items_all
        fail_items = g_items_all

    fail_has_error = any(_sev_class(it.get("sev", "")) == "error" for it in fail_items)
    succ_has_convertible_warning = any(
        _sev_class(it.get("sev", "")) == "warning" and _is_warning_convertible(it.get("opt"))
        for it in succ_items
    )
    if fail_has_error and succ_has_convertible_warning:
        return 0

    g_items, c_items = _eliminate_convertible_mismatches(g_items_all, c_items_all)

    def keep_for_report(items):
        res = []
        for it in items:
            cls = _sev_class(it["sev"])
            if cls in ("warning", "error"):
                res.append(it)
        return res

    g_keep = keep_for_report(g_items)
    c_keep = keep_for_report(c_items)
    if not g_keep and not c_keep:
        return 0

    report_path = path.join(out_dir, f"{time}_DIFF.txt")
    with open(report_path, "w") as f:
        f.write("=== gcc diags kept ===\n")
        for it in g_keep:
            f.write(f"{it['loc'] or '<noloc>'}: {it['sev']}: {it['msg_base']} [{it['opt'] or ''}]\n")

        f.write("\n=== clang diags kept ===\n")
        for it in c_keep:
            f.write(f"{it['loc'] or '<noloc>'}: {it['sev']}: {it['msg_base']} [{it['opt'] or ''}]\n")

        f.write("\n=== raw gcc stderr ===\n")
        f.write(gcc_errors or "")
        f.write("\n=== raw clang stderr ===\n")
        f.write(clang_errors or "")

    return 1
