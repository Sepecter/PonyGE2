from fitness.base_ff_classes.base_ff import base_ff
from os import getcwd, path
from fitness.cpp_code_gen.differential_testing import differential_testing
from algorithm.parameters import params
from stats.stats import stats
import os
import subprocess
import random
from datetime import datetime
import math


def calculate_fitness(length, number, compiling_result, differential_testing_result):
    # print(stats)

    if differential_testing_result == 1:
        return 0, True

    size = params['POPULATION_SIZE']
    if stats['last_gen'] != stats['gen']:
        stats['last_gen'] = stats['gen']
        stats['last_sum_number'] = stats['sum_number']
        stats['sum_number'] = 0
    avg_number = stats['last_sum_number'] / size
    stats['sum_number'] += number
    expected_length = 30
    expected_number = 15

    # print(stats['gen'])
    # print(avg_number)

    fitness = 30 - 10 * math.exp(-(length - expected_length) ** 2) - 10 * math.exp(-(number - expected_number) ** 2)
    # - (number - avg_number)
    # 越接近fitness越小
    return fitness, False


# 使用here document编译代码
def cmd_compile(compiler_command, code):
    try:
        process = subprocess.Popen(compiler_command, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
                                   universal_newlines=True)
        _, stderr = process.communicate(code)
        if process.returncode == 0:
            return True, ""
        else:
            return False, stderr
    except Exception as e:
        return False, str(e)

def compile_code(code):
    result = 0
    # 指定文件路径
    now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')
    path_1 = path.join(params['FILE_PATH'], "code_results")
    output_dir = path.join(path_1, "bin")  # 编译后的可执行文件存放目录
    path_1 = path.join(path_1, "code")

    file_path = path.join(path_1, now + '.cpp')
    cpp_file = file_path

    # 定义编译器命令
    compiler1 = 'g++-15-cov'
    compiler2 = 'clang++-20'

    # 构建输出文件的完整路径
    output_file = path.join(output_dir, now)

    # g++ 模板（stdin/heredoc：从 '-' 读入 code）
    compile_command1 = [
        compiler1,
        "-x", "c++",
        "-std=c++20",
        "-c", "-",
        "-o", output_file,

        # g++：宽松/降噪
        "-fpermissive",
        "-w",
        "-Wno-error",
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
        "-std=c++20",
        "-c", "-",
        "-o", output_file,

        # clang++：降噪（无 -fpermissive）
        "-w",
        "-Wno-everything",
        "-Wno-error",
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

    # 执行编译器1命令
    compiled, gcc_errors = cmd_compile(compile_command1, code)
    if compiled:
        result |= 1

    # 执行编译器2命令
    compiled, clang_errors = cmd_compile(compile_command2, code)
    if compiled:
        result |= 2

    # DEBUG
    clang_errors_file = f'{output_file}_clang_error.txt'
    with open(clang_errors_file, 'w') as errors_file:
        errors_file.write(clang_errors)

    gcc_errors_file = f'{output_file}_gcc_error.txt'
    with open(gcc_errors_file, 'w') as errors_file:
        errors_file.write(gcc_errors)

    # 保存触发错误的源码（注意：你原代码写了两次，这里保留一次）
    with open(cpp_file, 'w') as error_code:
        error_code.write(code)

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
        # Initialise base fitness function class.
        super().__init__()

    def evaluate(self, ind, **kwargs):
        raw_code = ind.phenotype

        # 变量池
        # identifier_pool = 'int X0,X1,X2,X3,X4,X5,x6,x7,x8,x9; '
        # identifier_pool = 'class X0{}; class X1{}; class X2{}; class X3{}; class X4{}; class X5{}; class X6{}; ' \
        #                   'class X7{}; class X8{};'
        identifier_pool = ''
        # 填充代码标识符
        code = identifier_pool + fill_identifiers(raw_code)
        # 编译
        compiling_result, gcc_errors, clang_errors, time = compile_code(code)
        length = calculate_length(raw_code)
        number = calculate_number(raw_code)

        # crash error
        gcc_crash = gcc_errors.find('report')
        clang_crash = clang_errors.find('report')
        crashed_source = ''
        if gcc_crash != -1:
            crashed_source += gcc_errors
        if clang_crash != -1:
            crashed_source += clang_errors

        # diagnostic error
        # diagnostic = 0
        # gcc_count = gcc_errors.count('error')
        # clang_count = clang_errors.count('error')
        # if abs(gcc_count - clang_count) >= 3:
        #     diagnostic = 1

        # differential_testing
        differential_testing_result = 0
        if crashed_source != '' or compiling_result == 1 or compiling_result == 2:
            differential_testing_result = differential_testing(gcc_errors, clang_errors, crashed_source,
                                                               time, compiling_result)

        # 输出触发缺陷程序到bugs目录下
        bugs_path = path.join(getcwd(), "..", "results", "bugs", time + '.cpp')
        if gcc_crash != -1 or clang_crash != -1:
            with open(bugs_path, 'w') as bug_file:
                bug_file.write(code)
        if (compiling_result == 1 or compiling_result == 2) and differential_testing_result != 0:
            with open(bugs_path, 'w') as bug_file:
                bug_file.write(code)
        fitness, result = calculate_fitness(length, number, compiling_result, differential_testing_result)

        if result:

            target_path = "/home/syc/GE/PonyGE2/results/diff/diff.txt"

            if result:
                if not os.path.exists(target_path):
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with open(target_path, "w") as f:
                        f.write("")

        return fitness
