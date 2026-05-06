# code_eval.py

from fitness.base_ff_classes.base_ff import base_ff
from os import getcwd, path
from algorithm.parameters import params
from stats.stats import stats
import math
import os
import random
import shutil
import subprocess
from datetime import datetime


_CANGJIE_ICE_PATTERNS = (
    "internal compiler error",
    "please submit a bug report",
    "assertion failed",
    "segmentation fault",
    "stack dump",
    "panic:",
    "fatal error",
    "core dumped",
    "abort trap",
    "illegal instruction",
    "report",
    "Internal Compiler Error"
)


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


def _looks_like_ice(stderr_text, stdout_text=""):
    merged = "\n".join([stdout_text or "", stderr_text or ""]).lower()
    for pattern in _CANGJIE_ICE_PATTERNS:
        if pattern in merged:
            return True
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
        info_file.write(f"source: {compile_info['source_path']}\n")
        info_file.write(f"artifact: {compile_info['artifact_path']}\n")
        info_file.write("\n=== stdout ===\n")
        info_file.write(compile_info['stdout'])
        info_file.write("\n=== stderr ===\n")
        info_file.write(compile_info['stderr'])


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

    ice_or_crash = _looks_like_ice(stderr_text, stdout_text) or returncode < 0

    return {
        "success": returncode == 0,
        "returncode": returncode,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "artifact_path": artifact_path,
        "source_path": source_path,
        "ice_or_crash": ice_or_crash,
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

        if compile_info["ice_or_crash"]:
            _save_bug_case(code_path, code, compile_info, stamp)

        length = calculate_length(raw_code)
        number = calculate_number(raw_code)
        return calculate_fitness(length, number, compile_info["ice_or_crash"])
