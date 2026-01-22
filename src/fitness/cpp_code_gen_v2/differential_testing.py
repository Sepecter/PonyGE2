# differential_testing.py

import os
from os import path
import re
import hashlib
from algorithm.parameters import params
from stats.stats import stats


# ---------------- ICE / crash detection ----------------

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
    if compiler == "gcc":
        pats = _GCC_ICE_PATTERNS
    else:
        pats = _CLANG_ICE_PATTERNS
    for p in pats:
        if p.lower() in s:
            return True
    return False


# ---------------- message normalization / fingerprinting ----------------

def normalize_message(msg: str) -> str:
    """Normalize compiler output to make fingerprinting more stable."""
    if msg is None:
        return ""
    # Remove file paths/line numbers and volatile addresses
    msg = re.sub(r"/[^ \n\t:]+", "<path>", msg)
    msg = re.sub(r"\b\d+\b", "<num>", msg)
    msg = re.sub(r"0x[0-9a-fA-F]+", "0x<hex>", msg)
    # Collapse whitespace
    msg = re.sub(r"[ \t]+", " ", msg)
    msg = re.sub(r"\n{3,}", "\n\n", msg)
    return msg.strip()


def fingerprint_norm_messages(norm_msgs) -> str:
    """Fingerprint a list of normalized messages."""
    joined = "\n---\n".join(sorted(set([m for m in norm_msgs if m])))
    h = hashlib.sha256(joined.encode("utf-8", errors="ignore")).hexdigest()
    return h


def _ensure_set(key: str):
    if key not in stats:
        stats[key] = set()
    elif isinstance(stats[key], list):
        stats[key] = set(stats[key])
    elif not isinstance(stats[key], set):
        stats[key] = set(list(stats[key]))


# ---------------- known bug (regex) suppression ----------------

def _match_known_bug_regex(compiler: str, stderr_text: str) -> bool:
    """Return True if stderr_text matches any regex in stats['gcc_errors'] / stats['clang_errors'].

    This is used to suppress repeated/known bugs for:
      - one-pass-one-fail differential cases
      - crash/ICE cases
    """
    if not stderr_text:
        return False

    key = "gcc_errors" if compiler == "gcc" else "clang_errors"
    patterns = stats.get(key, [])

    if patterns is None:
        return False
    if isinstance(patterns, str):
        patterns = [patterns]
    elif not isinstance(patterns, (list, tuple)):
        try:
            patterns = list(patterns)
        except Exception:
            return False

    for pat in patterns:
        if not pat:
            continue
        try:
            if re.search(pat, stderr_text, flags=re.IGNORECASE | re.DOTALL):
                return True
        except re.error:
            # Invalid regex; ignore rather than breaking the pipeline
            continue

    return False


# ---------------- warning/error convertibility logic ----------------

def _sev_class(sev: str) -> str:
    """Map severities to coarse classes."""
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


def _is_warning_convertible(opt: str | None) -> bool:
    """Only analyze convertibility (no message comparison).

    Treat a warning as convertible to an error if:
      - it has a -W... tag (so -Werror / -Werror=<x> can promote it), or
      - it has -fpermissive (removing -fpermissive typically makes it an error in GCC).
    """
    if not opt:
        return False
    if opt == "-fpermissive":
        return True
    if opt.startswith("-W") and not opt.startswith("-Werror"):
        return True
    return False


def _is_convertible_pair(g: dict, c: dict) -> bool:
    """Heuristic: allow warning<->error differences to be considered equivalent if message base matches."""
    if not g or not c:
        return False

    g_cls = _sev_class(g.get("sev", ""))
    c_cls = _sev_class(c.get("sev", ""))

    if g_cls not in ("warning", "error") or c_cls not in ("warning", "error"):
        return False

    # Same base message text => convertible
    g_base = (g.get("msg_base") or "").strip()
    c_base = (c.get("msg_base") or "").strip()
    if not g_base or not c_base:
        return False

    return g_base == c_base


def parse_diagnostics(stderr_text: str):
    """Parse gcc/clang stderr into a list of diagnostic dicts.
    Expected formats (best-effort):
      file:line:col: <sev>: <msg> [<opt>]
      <sev>: <msg>
    """
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

        # Try: file:line:col: sev: msg
        m = re.match(r"^(.*?):(\d+):(\d+):\s*([^:]+):\s*(.*)$", line)
        if m:
            loc = f"{m.group(1)}:{m.group(2)}:{m.group(3)}"
            sev = m.group(4).strip()
            msg = m.group(5).strip()
        else:
            # Try: file:line: sev: msg
            m2 = re.match(r"^(.*?):(\d+):\s*([^:]+):\s*(.*)$", line)
            if m2:
                loc = f"{m2.group(1)}:{m2.group(2)}"
                sev = m2.group(3).strip()
                msg = m2.group(4).strip()
            else:
                # Try: sev: msg
                m3 = re.match(r"^([^:]+):\s*(.*)$", line)
                if m3:
                    sev = m3.group(1).strip()
                    msg = m3.group(2).strip()

        # Extract trailing option tag: [-Wxxx] / [-Werror] / [-Werror=xxx] / [-fpermissive]
        mopt = re.search(r"(?:\s*\[(?P<opt>-(?:Werror(?:=[\w-]+)?|W[\w-]+|fpermissive))\]\s*)$", msg)
        if mopt:
            opt = mopt.group("opt")
            msg_base = msg[:mopt.start()].rstrip()
        else:
            msg_base = msg.strip()

        items.append(
            {
                "loc": loc,
                "sev": sev,
                "msg": msg,
                "msg_base": msg_base,
                "opt": opt,
            }
        )

    return items


def _eliminate_convertible_mismatches(g_items, c_items):
    """Remove diagnostics pairs that differ only by warning<->error for the same base message."""
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


# ---------------- differential testing core ----------------

def differential_testing(gcc_errors, clang_errors, code, time, compiling_result):
    """
    compiling_result bitmask:
      1 -> gcc compiled
      2 -> clang compiled
      3 -> both compiled
      0 -> both failed

    Return:
      1 -> interesting differential (novel)
      0 -> not interesting / not differential
    """
    out_dir = path.join(params['FILE_PATH'], "code_results", "differential_testing")
    os.makedirs(out_dir, exist_ok=True)

    # 1) ICE：任意情况下优先捕获
    gcc_ice = _looks_like_ice("gcc", gcc_errors)
    clang_ice = _looks_like_ice("clang", clang_errors)

    # Suppress repeated/known bugs for:
    # - one-pass-one-fail cases (compiling_result in (1, 2))
    # - crash/ICE cases (gcc_ice/clang_ice)
    if gcc_ice or clang_ice or compiling_result in (1, 2):
        if _match_known_bug_regex("gcc", gcc_errors) or _match_known_bug_regex("clang", clang_errors):
            known_dir = path.join(os.getcwd(), "..", "results", "known_bugs")
            os.makedirs(known_dir, exist_ok=True)

            fname = f"{time}_known.cpp"
            file_path = path.join(known_dir, fname)
            with open(file_path, "w") as f:
                f.write(code)

            return 0

    if gcc_ice or clang_ice:
        ice_text = ""
        if gcc_ice:
            ice_text += "GCC_ICE\n" + normalize_message(gcc_errors)
        if clang_ice:
            ice_text += "CLANG_ICE\n" + normalize_message(clang_errors)

        _ensure_set("ice_fps")
        fp = fingerprint_norm_messages([ice_text])
        if fp in stats["ice_fps"]:
            return 0
        stats["ice_fps"].add(fp)

        file_path = path.join(out_dir, f"{time}_ICE_{fp}.txt")
        with open(file_path, "w") as f:
            f.write(ice_text)

        ice_path = path.join(os.getcwd(), "..", "results", "ice", time + ".cpp")
        os.makedirs(path.dirname(ice_path), exist_ok=True)
        with open(ice_path, "w") as f:
            f.write(code)

        return 1

    # 2) 只在“一成一败”(1 或 2) 时才判为差分；都成功(3)或都失败(0)直接不算
    if compiling_result not in (1, 2):
        return 0

    # 3) 一成一败时，如需应用“warning<->error 可互转则不算差分”的规则，在这里处理：
    g_items_all = parse_diagnostics(gcc_errors)
    c_items_all = parse_diagnostics(clang_errors)

    # NEW: do NOT compare message contents; only analyze convertibility.
    # If one compiler fails with error(s) and the other compiler succeeded but produced
    # any warning that can be promoted to an error via options (e.g., -Werror or removing -fpermissive),
    # treat it as non-differential.
    if compiling_result == 1:
        succ_items = g_items_all   # gcc succeeded
        fail_items = c_items_all   # clang failed
    else:
        succ_items = c_items_all   # clang succeeded
        fail_items = g_items_all   # gcc failed

    fail_has_error = any(_sev_class(it.get("sev", "")) == "error" for it in fail_items)
    succ_has_convertible_warning = any(
        _sev_class(it.get("sev", "")) == "warning" and _is_warning_convertible(it.get("opt"))
        for it in succ_items
    )
    if fail_has_error and succ_has_convertible_warning:
        return 0

    g_items, c_items = _eliminate_convertible_mismatches(g_items_all, c_items_all)

    # 若差异完全可互转，可能两边剩余诊断都为空；此时不算差分
    def keep_for_fp(items):
        res = []
        for it in items:
            cls = _sev_class(it["sev"])
            if cls in ("warning", "error"):
                res.append(f"{cls}:{it.get('msg_base')}")
        return res

    g_norm = keep_for_fp(g_items)
    c_norm = keep_for_fp(c_items)

    if not g_norm and not c_norm:
        return 0

    _ensure_set("diff_fps")
    fp = fingerprint_norm_messages(g_norm + c_norm)
    if fp in stats["diff_fps"]:
        return 0
    stats["diff_fps"].add(fp)

    # 4) 输出差分结果
    file_path = path.join(out_dir, f"{time}_DIFF_{fp}.txt")
    with open(file_path, "w") as f:
        f.write("=== differential fingerprint ===\n")
        f.write(fp + "\n\n")

        f.write("=== gcc diags kept (after convertible mismatch elimination) ===\n")
        for it in g_items:
            cls = _sev_class(it["sev"])
            if cls in ("warning", "error"):
                f.write(f"{it['loc'] or '<noloc>'}: {it['sev']}: {it['msg_base']} [{it['opt'] or ''}]\n")

        f.write("\n=== clang diags kept (after convertible mismatch elimination) ===\n")
        for it in c_items:
            cls = _sev_class(it["sev"])
            if cls in ("warning", "error"):
                f.write(f"{it['loc'] or '<noloc>'}: {it['sev']}: {it['msg_base']} [{it['opt'] or ''}]\n")

        f.write("\n=== raw gcc stderr ===\n")
        f.write(gcc_errors or "")
        f.write("\n=== raw clang stderr ===\n")
        f.write(clang_errors or "")

    return 1
