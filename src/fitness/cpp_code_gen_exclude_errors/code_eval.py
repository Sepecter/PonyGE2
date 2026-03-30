# code_eval.py

from fitness.base_ff_classes.base_ff import base_ff
from os import getcwd, path
from fitness.cpp_code_gen_exclude_errors.differential_testing import differential_testing
from algorithm.parameters import params
from stats.stats import stats
import os
import subprocess
import random
from datetime import datetime
import math


def calculate_fitness(length, number, compiling_result, differential_testing_result):
    if differential_testing_result == 1:
        return 0, True

    size = params['POPULATION_SIZE']
    if stats['last_gen'] != stats['gen']:
        stats['last_gen'] = stats['gen']
        stats['last_sum_number'] = stats['sum_number']
        stats['sum_number'] = 0

    stats['sum_number'] += number

    expected_length = 700
    fitness = 20 - 10 * math.exp(-(length - expected_length) ** 2)

    return fitness, False


def cmd_compile(compiler_command, code):
    try:
        process = subprocess.Popen(
            compiler_command,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        _, stderr = process.communicate(code)
        if process.returncode == 0:
            return True, stderr
        else:
            return False, stderr
    except Exception as e:
        return False, str(e)


def compile_code(code):
    result = 0
    now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')

    path_1 = path.join(params['FILE_PATH'], "code_results")
    output_dir = path.join(path_1, "bin")
    cpp_file = path.join(os.getcwd(), "..", "results", "code")

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(cpp_file, exist_ok=True)

    cpp_file = path.join(cpp_file, now + '.cpp')

    compiler1 = 'g++-16'
    compiler2 = 'clang++-trunk'

    output_file = path.join(output_dir, now)

    compile_command1 = [
        compiler1,
        "-x", "c++",
        "-c", "-",
        "-o", output_file,
        "-fpermissive",
        "-Wno-attributes",
        "-Wno-unknown-pragmas",
        "-Wno-unused-parameter",
        "-Wno-unused-variable",
        "-Wno-unused-function",
        "-Wno-return-type",
    ]

    compile_command2 = [
        compiler2,
        "-x", "c++",
        "-c", "-",
        "-o", output_file,
        "-Wno-unknown-attributes",
        "-Wno-unknown-pragmas",
        "-Wno-unused-parameter",
        "-Wno-unused-variable",
        "-Wno-unused-function",
        "-Wno-return-type",
        "-fno-caret-diagnostics",
        "-fno-diagnostics-color",
    ]

    gcc_errors = ''
    clang_errors = ''

    compiled, gcc_errors = cmd_compile(compile_command1, code)
    if compiled:
        result |= 1

    compiled, clang_errors = cmd_compile(compile_command2, code)
    if compiled:
        result |= 2

    return result, gcc_errors, clang_errors, now


def fill_identifiers(raw_code):
    raw_code = raw_code.split(' ')
    length = len(raw_code)
    cnt = 0
    code = ''
    for i in range(length):
        if raw_code[i] == 'Identifier':
            num = random.randint(0, cnt + 1)
            if num == cnt + 1:
                cnt += 1
            raw_code[i] = 'X' + str(num)
    for i in raw_code:
        code += i + ' '
    return code


def calculate_length(raw_code):
    code = raw_code.split(' ')
    length = len(code)
    return length


def calculate_number(raw_code):
    code = raw_code.split(' ')
    unique_list = list(set(code))
    number = len(unique_list)
    return number


def save_triggered_case(code, gcc_errors, clang_errors, time, compiling_result):
    """
    Save triggered defect cases for later manual analysis.
    """
    lower_gcc = (gcc_errors or "").lower()
    lower_clang = (clang_errors or "").lower()
    is_ice = any(
        marker in lower_gcc or marker in lower_clang
        for marker in (
            "internal compiler error",
            "please submit a full bug report",
            "please submit a bug report",
            "compiler error:",
            "segmentation fault",
            "stack dump",
            "clang: error:",
            "clang: fatal error:",
            "llvm error",
            "assertion `",
            "assertion failed",
        )
    )

    category = "ice" if is_ice else "diff"
    base_dir = path.join(getcwd(), "..", "results")
    code_dir = path.join(base_dir, "code", "exclude_errors", category)
    text_dir = path.join(base_dir, "bugs_exclude_errors", "text", category)
    os.makedirs(code_dir, exist_ok=True)
    os.makedirs(text_dir, exist_ok=True)

    cpp_path = path.join(code_dir, time + '.cpp')
    meta_path = path.join(text_dir, time + '.txt')

    with open(cpp_path, 'w') as bug_file:
        bug_file.write(code)

    with open(meta_path, 'w') as meta_file:
        meta_file.write(f"compiling_result={compiling_result}\n")
        meta_file.write(f"category={category}\n\n")
        meta_file.write("=== gcc stderr ===\n")
        meta_file.write(gcc_errors or "")
        meta_file.write("\n=== clang stderr ===\n")
        meta_file.write(clang_errors or "")


class code_eval(base_ff):

    def __init__(self):
        super().__init__()

    def evaluate(self, ind, **kwargs):
        raw_code = ind.phenotype

        identifier_pool = ''
        code = identifier_pool + fill_identifiers(raw_code)

        compiling_result, gcc_errors, clang_errors, time = compile_code(code)

        length = calculate_length(raw_code)
        number = calculate_number(raw_code)

        differential_testing_result = 0
        if compiling_result != 3:
            differential_testing_result = differential_testing(
                gcc_errors, clang_errors, code, time, compiling_result
            )

        if differential_testing_result != 0:
            save_triggered_case(code, gcc_errors, clang_errors, time, compiling_result)

        fitness, result = calculate_fitness(length, number, compiling_result, differential_testing_result)

        triggered_bug = (compiling_result != 3)
        found_new_bug = (differential_testing_result != 0)

        if triggered_bug and not found_new_bug:
            target_path = "/home/syc/GE/PonyGE2/results/diff_exclude_errors/diff_dup.txt"
            if not os.path.exists(target_path):
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "w") as f:
                    f.write("")

        if result:
            target_path = "/home/syc/GE/PonyGE2/results/diff_exclude_errors/diff_new.txt"
            if not os.path.exists(target_path):
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "w") as f:
                    f.write("")

        return fitness
