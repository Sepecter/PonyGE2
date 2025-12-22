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
    "clang: error: unable to execute command",
    "clang: error: clang frontend command failed",
    "please submit a bug report",
    "stack dump",
    "segmentation fault",
    "fatal error: error in backend",
)


def _looks_like_ice(compiler: str, s: str) -> bool:
    if not s:
        return False
    low = s.lower()
    pats = _GCC_ICE_PATTERNS if compiler == "gcc" else _CLANG_ICE_PATTERNS
    return any(p in low for p in pats)


# ---------------- diagnostic parsing & normalization ----------------
# 解析：
# 1) <file>:line:col: (fatal error|error|warning|note): message [opt]
# 2) (fatal error|error|warning|note): message [opt]

_DIAG_HEAD_RE = re.compile(
    r"^(?P<file>.*?):(?P<line>\d+):(?P<col>\d+):\s*(?P<sev>fatal error|error|warning|note):\s*(?P<msg>.*)$"
)
_DIAG_NOLC_RE = re.compile(
    r"^(?P<sev>fatal error|error|warning|note):\s*(?P<msg>.*)$"
)

# 选项 tag（gcc/clang 常见在行末：[-Wxxx] / [-fpermissive] / [-Werror]）
_OPT_TAG_RE = re.compile(r"(?:\s*\[(?P<opt>-[^\]]+)\]\s*)$")

_PATH_RE = re.compile(r'([A-Za-z]:\\[^:\n]+|/[^:\n]+)')
_LOC_INLINE_RE = re.compile(r'(<source>|<stdin>|[^:\n]+):\d+:\d+:')
_HEX_RE = re.compile(r'0x[0-9a-fA-F]+')
_NUM_RE = re.compile(r'\b\d+\b')


def normalize_message(msg: str) -> str:
    """用于比较/指纹的强归一化（降低噪声）"""
    if not msg:
        return ""
    s = msg.replace("\r\n", "\n").replace("\r", "\n")
    s = _LOC_INLINE_RE.sub("<loc>:", s)
    s = _PATH_RE.sub("<path>", s)
    s = _HEX_RE.sub("0x<hex>", s)
    s = _NUM_RE.sub("<n>", s)
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def strip_opt_tag(msg: str):
    """拆分末尾的 [ -Wxxx ] / [ -fpermissive ] 等"""
    if not msg:
        return "", None
    m = _OPT_TAG_RE.search(msg)
    if not m:
        return msg, None
    opt = m.group("opt")
    base = msg[:m.start()].rstrip()
    return base, opt


def _loc_key(file_: str | None, line: str | None, col: str | None):
    if not (file_ and line and col):
        return None
    # stdin/heredoc 场景常见 <stdin> 或 <source>；这里不改写，直接作为 key
    return f"{file_}:{line}:{col}"


def parse_diagnostics(compile_output: str):
    """
    输出条目：
      {
        "loc": "file:line:col" or None,
        "sev": "warning"|"error"|"fatal error"|"note",
        "msg_norm": 归一化后的 message（含 opt tag 已去除）
        "msg_base": 去 opt tag 的原始 base（未强归一化，仅用于同位匹配）
        "opt": "-Wxxx" / "-fpermissive" / "-Werror" ... or None
      }
    """
    items = []
    for line in (compile_output or "").splitlines():
        m = _DIAG_HEAD_RE.match(line)
        if m:
            file_ = m.group("file")
            ln = m.group("line")
            col = m.group("col")
            sev = m.group("sev")
            msg = m.group("msg")

            base, opt = strip_opt_tag(msg)
            items.append({
                "loc": _loc_key(file_, ln, col),
                "sev": sev,
                "msg_base": base.strip(),
                "msg_norm": normalize_message(base),
                "opt": opt,
            })
            continue

        m2 = _DIAG_NOLC_RE.match(line)
        if m2:
            sev = m2.group("sev")
            msg = m2.group("msg")
            base, opt = strip_opt_tag(msg)
            items.append({
                "loc": None,
                "sev": sev,
                "msg_base": base.strip(),
                "msg_norm": normalize_message(base),
                "opt": opt,
            })
    return items


def fingerprint_norm_messages(norm_msgs) -> str:
    joined = "\n".join(sorted(set([m for m in norm_msgs if m])))
    h = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return h[:16]


def _ensure_set(key: str):
    if key not in stats:
        stats[key] = set()
    elif isinstance(stats[key], list):
        stats[key] = set(stats[key])
    elif not isinstance(stats[key], set):
        stats[key] = set(list(stats[key]))


# ---------------- warning/error convertibility logic ----------------

def _is_warning_to_error_convertible(opt: str | None) -> bool:
    # clang/gcc warning 通常带 [-Wxxx]，可被 -Werror 或 -Werror=xxx 升级为 error
    return bool(opt and opt.startswith("-W") and opt != "-Werror")


def _is_error_to_warning_convertible(opt: str | None) -> bool:
    # 两类最常见：
    # 1) GCC 的 [-fpermissive]（加 -fpermissive 可把部分 error 降为 warning）
    # 2) 由 -Werror 导致的 error，通常会带 [-Werror] 或 [-Werror=xxx]，去掉 Werror 可降回 warning
    if not opt:
        return False
    if opt == "-fpermissive":
        return True
    if opt.startswith("-Werror"):
        return True
    return False


def _sev_class(sev: str) -> str:
    # note 不参与差分主判定；fatal error 视为 error
    if sev == "warning":
        return "warning"
    if sev in ("error", "fatal error"):
        return "error"
    return "other"


def _build_loc_map(items):
    m = {}
    for it in items:
        if it["loc"] is None:
            continue
        m.setdefault(it["loc"], []).append(it)
    return m


def _eliminate_convertible_mismatches(g_items, c_items):
    """
    从两侧 items 里剔除满足：
    - 同 loc
    - 一边 warning 一边 error
    - message(去 opt tag 后归一化)一致
    - warning 可升 error 或 error 可降 warning（任一成立即可）
    返回：(g_keep, c_keep)
    """
    g_loc = _build_loc_map(g_items)
    c_loc = _build_loc_map(c_items)

    g_drop = set()
    c_drop = set()

    for loc, glist in g_loc.items():
        clist = c_loc.get(loc)
        if not clist:
            continue

        for gi in glist:
            for ci in clist:
                gs = _sev_class(gi["sev"])
                cs = _sev_class(ci["sev"])
                if {gs, cs} != {"warning", "error"}:
                    continue
                if gi["msg_norm"] != ci["msg_norm"]:
                    continue

                convertible = False
                if gs == "warning" and _is_warning_to_error_convertible(gi["opt"]):
                    convertible = True
                if cs == "warning" and _is_warning_to_error_convertible(ci["opt"]):
                    convertible = True
                if gs == "error" and _is_error_to_warning_convertible(gi["opt"]):
                    convertible = True
                if cs == "error" and _is_error_to_warning_convertible(ci["opt"]):
                    convertible = True

                if convertible:
                    g_drop.add(id(gi))
                    c_drop.add(id(ci))

    g_keep = [it for it in g_items if id(it) not in g_drop]
    c_keep = [it for it in c_items if id(it) not in c_drop]
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

    g_items, c_items = _eliminate_convertible_mismatches(g_items_all, c_items_all)

    # 若差异完全可互转，可能两边剩余诊断都为空；此时不算差分
    def keep_for_fp(items):
        res = []
        for it in items:
            cls = _sev_class(it["sev"])
            if cls in ("warning", "error"):
                # 注意：这里不依赖 loc 做 fingerprint，避免 <stdin>/<source> 等差异误判
                res.append(f"{cls}:{it['msg_norm']}")
        return res

    fg = fingerprint_norm_messages(keep_for_fp(g_items))
    fc = fingerprint_norm_messages(keep_for_fp(c_items))

    # 如果两边都没有可比较的主诊断（常见于纯粹由参数导致的等级变化），不算差分
    if fg == "" and fc == "":
        return 0

    diff_class = "SUCCESS_MISMATCH"

    _ensure_set("diff_fps")
    pair_fp = hashlib.sha256(f"{diff_class}:{fg}:{fc}".encode("utf-8")).hexdigest()[:16]
    if pair_fp in stats["diff_fps"]:
        return 0
    stats["diff_fps"].add(pair_fp)

    file_path = path.join(out_dir, f"{time}_{diff_class}_{pair_fp}.txt")
    with open(file_path, "w") as f:
        f.write(f"diff_class: {diff_class}\n")
        f.write(f"compiling_result: {compiling_result}\n")
        f.write(f"gcc_fp: {fg}\n")
        f.write(f"clang_fp: {fc}\n\n")

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
