# code_eval.py

from fitness.base_ff_classes.base_ff import base_ff
from os import getcwd, path
from algorithm.parameters import params
from stats.stats import stats
import json
import math
import os
import random
import re
import shutil
import subprocess
from datetime import datetime


_ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
_CANGJIE_ICE_REGEXES = (
    re.compile(r"\binternal compiler error\b", re.IGNORECASE),
    re.compile(r"\bplease submit (?:a )?bug report\b", re.IGNORECASE),
    re.compile(r"\bassertion(?: failed)?\b", re.IGNORECASE),
    re.compile(r"\bsegmentation fault\b", re.IGNORECASE),
    re.compile(r"\bstack dump\b", re.IGNORECASE),
    re.compile(r"\bpanic:\b", re.IGNORECASE),
    re.compile(r"\bfatal error\b", re.IGNORECASE),
    re.compile(r"\bcore dumped\b", re.IGNORECASE),
    re.compile(r"\babort trap\b", re.IGNORECASE),
    re.compile(r"\billegal instruction\b", re.IGNORECASE),
    re.compile(r"\bcompiler crashed\b", re.IGNORECASE),
    re.compile(r"\bcjc: .*assertion.*failed\b", re.IGNORECASE),
)
_CANGJIE_KNOWN_BUG_REGEXES = [
    re.compile(
        r"DiagnosticEmitter\.cpp:\d+: .*Assertion .*range\.end\.line == range\.begin\.line.*failed",
        re.IGNORECASE,
    ),
]


def _src_root():
    return path.abspath(path.join(path.dirname(__file__), "..", ".."))


_SEEN_LINES_FILE = path.join(_src_root(), "cangjie_seen_lines.json")


def _load_seen_lines():
    if not path.exists(_SEEN_LINES_FILE):
        return set()
    try:
        with open(_SEEN_LINES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(item for item in data if isinstance(item, str))
    except Exception:
        pass
    return set()


def _save_seen_lines(seen_lines):
    try:
        with open(_SEEN_LINES_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(seen_lines), f, ensure_ascii=False, indent=2)
    except Exception:
        pass


_SEEN_MATCHED_LINES = _load_seen_lines()


def calculate_fitness(length, number, ice_or_crash=False):
    """
    A lightweight structural fitness for framework testing.
    Lower fitness is better in PonyGE2's default minimisation setting.
    """
    if ice_or_crash:
        return 0

    size = params['POPULATION_SIZE']
    if stats['last_gen'] != stats['gen']:
        stats['last_gen'] = stats['gen']
        stats['last_sum_number'] = stats['sum_number']
        stats['sum_number'] = 0

    stats['sum_number'] += number

    expected_length = 400
    expected_number = 80
    length_score = 10 * math.exp(
        -((length - expected_length) ** 2) / max(1, expected_length)
    )
    token_score = 10 * math.exp(
        -((number - expected_number) ** 2) / max(1, expected_number)
    )
    fitness = 30 - length_score - token_score

    return fitness


def fill_identifiers(raw_code):
    """
    Replace generic Identifier placeholders with simple generated names.
    This keeps the framework compatible with grammars that emit Identifier tokens.
    """
    raw_tokens = raw_code.split(' ')
    count = 0
    for i, token in enumerate(raw_tokens):
        if token == 'Identifier':
            idx = random.randint(0, count + 1)
            if idx == count + 1:
                count += 1
            raw_tokens[i] = f"V{idx}"
    return ' '.join(raw_tokens)


def calculate_length(raw_code):
    return len(raw_code.split())


def calculate_number(raw_code):
    return len(set(raw_code.split()))


def _timestamp():
    return datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')


def _results_root():
    return path.join(getcwd(), "..", "results")


def _strip_ansi(text):
    if not text:
        return ""
    return _ANSI_ESCAPE_RE.sub("", text)


def save_generated_code(code, stamp=None):
    output_dir = path.join(_results_root(), "code", "cangjie")
    os.makedirs(output_dir, exist_ok=True)

    stamp = stamp or _timestamp()
    file_path = path.join(output_dir, stamp + ".cj")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(code)

    return file_path


def _artifact_path(stamp):
    return path.join(_results_root(), "bin", "cangjie", stamp)


def _match_regex_line(stderr_text, stdout_text, regexes):
    merged = _strip_ansi("\n".join([stdout_text or "", stderr_text or ""]))
    for line in merged.splitlines():
        clean_line = line.strip()
        if not clean_line:
            continue
        for regex in regexes:
            if regex.search(clean_line):
                return regex.pattern, clean_line
    return None, None


def _is_duplicate_match(matched_line):
    if not matched_line:
        return False
    if matched_line in _SEEN_MATCHED_LINES:
        return True
    _SEEN_MATCHED_LINES.add(matched_line)
    _save_seen_lines(_SEEN_MATCHED_LINES)
    return False


def _save_bug_case(code_path, code, compile_info, stamp):
    bug_dir = path.join(_results_root(), "cangjie_bugs")
    os.makedirs(bug_dir, exist_ok=True)

    bug_code_path = path.join(bug_dir, stamp + ".cj")
    bug_info_path = path.join(bug_dir, stamp + ".txt")

    if code_path and path.exists(code_path):
        shutil.copyfile(code_path, bug_code_path)
    else:
        with open(bug_code_path, "w", encoding="utf-8") as code_file:
            code_file.write(code)

    with open(bug_info_path, "w", encoding="utf-8") as info_file:
        info_file.write("=== compile result ===\n")
        info_file.write(f"returncode: {compile_info['returncode']}\n")
        info_file.write(f"success: {compile_info['success']}\n")
        info_file.write(f"ice_or_crash: {compile_info['ice_or_crash']}\n")
        info_file.write(f"ice_match: {compile_info['ice_match']}\n")
        info_file.write(f"ice_line: {compile_info['ice_line']}\n")
        info_file.write(f"known_bug: {compile_info['known_bug']}\n")
        info_file.write(f"known_bug_match: {compile_info['known_bug_match']}\n")
        info_file.write(f"known_bug_line: {compile_info['known_bug_line']}\n")
        info_file.write(f"duplicate_bug: {compile_info['duplicate_bug']}\n")
        info_file.write(f"duplicate_line: {compile_info['duplicate_line']}\n")
        info_file.write(f"source: {compile_info['source_path']}\n")
        info_file.write(f"artifact: {compile_info['artifact_path']}\n")
        info_file.write("\n=== stdout ===\n")
        info_file.write(_strip_ansi(compile_info['stdout']))
        info_file.write("\n=== stderr ===\n")
        info_file.write(_strip_ansi(compile_info['stderr']))


def _cleanup_known_bug_outputs(code_path, compile_info):
    if code_path and path.exists(code_path):
        try:
            os.remove(code_path)
        except OSError:
            pass

    artifact_path = compile_info.get("artifact_path")
    if artifact_path and path.exists(artifact_path):
        try:
            os.remove(artifact_path)
        except OSError:
            pass


def compile_cangjie_code(code, source_path, output_name=None):
    """
    Compile a Cangjie source file with cjc.

    Command shape:
      cjc hello.cj -o hello

    Returns a dict with compile metadata so the caller can inspect
    return code, stdout/stderr, and crash-like compiler failures.
    """
    stamp = output_name or path.splitext(path.basename(source_path))[0]
    artifact_dir = path.join(_results_root(), "bin", "cangjie")
    os.makedirs(artifact_dir, exist_ok=True)
    artifact_path = path.join(artifact_dir, stamp)

    compile_command = ["cjc", source_path, "-o", artifact_path]
    compile_env = os.environ.copy()
    compile_env["NO_COLOR"] = "1"
    compile_env["CLICOLOR"] = "0"
    compile_env["TERM"] = "dumb"

    try:
        process = subprocess.run(
            compile_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
            env=compile_env,
        )
        stdout_text = process.stdout or ""
        stderr_text = process.stderr or ""
        returncode = process.returncode
    except subprocess.TimeoutExpired as exc:
        stdout_text = exc.stdout or ""
        stderr_text = (exc.stderr or "") + "\nCompilation timed out."
        returncode = -9
    except FileNotFoundError:
        stdout_text = ""
        stderr_text = "Compiler executable 'cjc' was not found."
        returncode = -127
    except Exception as exc:
        stdout_text = ""
        stderr_text = str(exc)
        returncode = -1

    ice_match, ice_line = _match_regex_line(
        stderr_text, stdout_text, _CANGJIE_ICE_REGEXES
    )
    known_bug_match, known_bug_line = _match_regex_line(
        stderr_text, stdout_text, _CANGJIE_KNOWN_BUG_REGEXES
    )
    ice_or_crash = (ice_match is not None) or returncode < 0
    duplicate_line = known_bug_line or ice_line
    duplicate_bug = _is_duplicate_match(duplicate_line)

    return {
        "success": returncode == 0,
        "returncode": returncode,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "artifact_path": artifact_path,
        "source_path": source_path,
        "ice_or_crash": ice_or_crash,
        "ice_match": ice_match,
        "ice_line": ice_line,
        "known_bug": known_bug_match is not None,
        "known_bug_match": known_bug_match,
        "known_bug_line": known_bug_line,
        "duplicate_bug": duplicate_bug,
        "duplicate_line": duplicate_line,
    }


class code_eval(base_ff):

    def __init__(self):
        super().__init__()

    def evaluate(self, ind, **kwargs):
        raw_code = ind.phenotype
        code = fill_identifiers(raw_code)

        stamp = _timestamp()
        code_path = save_generated_code(code, stamp=stamp)
        compile_info = compile_cangjie_code(code, code_path, output_name=stamp)

        if compile_info["known_bug"] or compile_info["duplicate_bug"]:
            _cleanup_known_bug_outputs(code_path, compile_info)
        elif compile_info["ice_or_crash"]:
            _save_bug_case(code_path, code, compile_info, stamp)

        length = calculate_length(raw_code)
        number = calculate_number(raw_code)
        reward_ice = (
            compile_info["ice_or_crash"]
            and not compile_info["known_bug"]
            and not compile_info["duplicate_bug"]
        )
        return calculate_fitness(length, number, reward_ice)
