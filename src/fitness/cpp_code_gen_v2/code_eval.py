# code_eval.py

from fitness.base_ff_classes.base_ff import base_ff
from os import getcwd, path
from fitness.cpp_code_gen_v2.differential_testing import differential_testing
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

    avg_number = stats['last_sum_number'] / size
    stats['sum_number'] += number

    expected_length = 300
    # expected_number = 15
    # fitness = 30 - 10 * math.exp(-(length - expected_length) ** 2) - 10 * math.exp(-(number - expected_number) ** 2)
    fitness = 20 - 10 * math.exp(-(length - expected_length) ** 2)

    return fitness, False


# 使用here document编译代码
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
    path_1 = path.join(path_1, "code")

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(path_1, exist_ok=True)

    file_path = path.join(path_1, now + '.cpp')
    cpp_file = file_path

    compiler1 = 'g++-16'
    compiler2 = 'clang++-20'

    output_file = path.join(output_dir, now)

    # g++ 模板（stdin/heredoc：从 '-' 读入 code）
    compile_command1 = [
        compiler1,
        "-x", "c++",
        "-c", "-",
        "-o", output_file,

        # g++：宽松/降噪
        "-fpermissive",
        "-Wno-attributes",
        "-Wno-unknown-pragmas",
        "-Wno-unused-parameter",
        "-Wno-unused-variable",
        "-Wno-unused-function",
        "-Wno-return-type",
    ]

    # clang++ 模板（stdin/heredoc：从 '-' 读入 code）
    compile_command2 = [
        compiler2,
        "-x", "c++",
        "-c", "-",
        "-o", output_file,

        # clang++：降噪（无 -fpermissive）
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

    # DEBUG 落盘
    # clang_errors_file = f'{output_file}_clang_error.txt'
    # with open(clang_errors_file, 'w') as errors_file:
    #     errors_file.write(clang_errors)
    #
    # gcc_errors_file = f'{output_file}_gcc_error.txt'
    # with open(gcc_errors_file, 'w') as errors_file:
    #     errors_file.write(gcc_errors)
    #
    # with open(cpp_file, 'w') as error_code:
    #     error_code.write(code)

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

        # differential testing：只要不是“两边都成功(3)”就进入（包含 both-fail=0）
        differential_testing_result = 0
        if compiling_result != 3:
            differential_testing_result = differential_testing(
                gcc_errors, clang_errors, code, time, compiling_result
            )

        # 输出触发缺陷程序到 bugs 目录下：差分触发即保存（包含 both-fail 差异）
        bugs_path = path.join(getcwd(), "..", "results", "bugs", time + '.cpp')
        if differential_testing_result != 0:
            os.makedirs(path.dirname(bugs_path), exist_ok=True)
            with open(bugs_path, 'w') as bug_file:
                bug_file.write(code)

        fitness, result = calculate_fitness(length, number, compiling_result, differential_testing_result)

        triggered_bug = (compiling_result != 3)  # 至少一个编译器失败
        found_new_bug = (differential_testing_result != 0)

        if triggered_bug == True and found_new_bug == False:
            target_path = "/home/syc/GE/PonyGE2/results/diff/diff_dup.txt"
            if not os.path.exists(target_path):
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "w") as f:
                    f.write("")

        if result:
            target_path = "/home/syc/GE/PonyGE2/results/diff/diff_new.txt"
            if not os.path.exists(target_path):
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "w") as f:
                    f.write("")

        return fitness
