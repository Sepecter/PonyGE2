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
    size = params['POPULATION_SIZE']
    if stats['last_gen'] != stats['gen']:
        stats['last_gen'] = stats['gen']
        stats['last_sum_number'] = stats['sum_number']
        stats['sum_number'] = 0
    avg_number = stats['last_sum_number'] / size
    stats['sum_number'] += number
    expected_length = 30
    expected_number = 23

    # print(stats['gen'])
    # print(avg_number)

    if differential_testing_result == 1:
        return 0
    if compiling_result == 1 or compiling_result == 2:

        fitness = -20
    else:
        fitness = 3 - (math.exp(-(length - expected_length) ** 2) + math.exp(-(number - expected_number) ** 2)) \
                  - (number - avg_number)
        # 越接近fitness越小
    return fitness


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
    path_1 = path.join(params['FILE_PATH'], "code_results")
    output_dir = path.join(path_1, "bin")  # 编译后的可执行文件存放目录
    bug_path = path.join(path_1, "bug")
    path_1 = path.join(path_1, "code")

    now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')
    file_path = path.join(path_1, now + '.cpp')
    bug_path = path.join(bug_path, now + '.cpp')

    # 打开文件并将内容写入
    # with open(file_path, 'w') as f:
    #     f.write(code)
    # 定义要编译的C++文件列表
    cpp_file = file_path

    # 定义编译器命令
    compiler1 = 'g++'
    # compiler2 = 'clang++'
    compiler2 = 'g++'

    # compile_command1 = [compiler1, '-o', '', '-c']
    # compile_command2 = [compiler2, '-o', '', '-c']

    compile_command1 = [compiler1, '-x', 'c++', '-o', '', '-']  # 使用heredoc
    compile_command2 = [compiler2, '-x', 'c++', '-o', '', '-']  # 使用heredoc

    # 循环编译每个C++文件

    # 构建输出文件的完整路径
    output_file = path.join(output_dir, now)
    compile_command1[2] = output_file  # 更新编译器命令中的输出文件路径
    compile_command1.append(cpp_file)  # 添加要编译的C++文件路径
    compile_command2[2] = output_file
    compile_command2.append(cpp_file)
    gcc_errors = ''
    clang_errors = ''
    # # 执行编译器1命令
    # try:
    #     output = subprocess.check_output(compile_command1, stderr=subprocess.STDOUT, universal_newlines=True)
    #     result |= 1
    # except subprocess.CalledProcessError as e:
    #     gcc_errors = e.output
    #
    # # 执行编译器2命令
    # try:
    #     output = subprocess.check_output(compile_command2, stderr=subprocess.STDOUT, universal_newlines=True)
    #     result |= 2
    # except subprocess.CalledProcessError as e:
    #     clang_errors = e.output

    # 执行编译器1命令
    compiled, gcc_errors = cmd_compile(compile_command1, code)
    if compiled:
        result |= 1

    # 执行编译器2命令
    compiled, clang_errors = cmd_compile(compile_command2, code)
    if compiled:
        result |= 2

    # 输出触发缺陷程序与编译结果

    if result == 1:
        clang_error_file = f'{output_file}_clang_error.txt'
        with open(clang_error_file, 'w') as error_file:
            error_file.write(clang_errors)
    elif result == 2:
        gcc_error_file = f'{output_file}_gcc_error.txt'
        with open(gcc_error_file, 'w') as error_file:
            error_file.write(gcc_errors)

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
        identifier_pool = 'int X0,X1,X2,X3,X4,X5; '
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
        diagnostic = 0
        gcc_count = gcc_errors.count('error')
        clang_count = clang_errors.count('error')
        if abs(gcc_count - clang_count) >= 3:
            diagnostic = 1

        # differential_testing
        differential_testing_result = 0
        if crashed_source != '' or diagnostic == 1 or (compiling_result != 0 and compiling_result != 3):
            differential_testing_result = differential_testing(gcc_errors, clang_errors, crashed_source,
                                                               time, compiling_result)
        fitness = calculate_fitness(length, number, compiling_result, differential_testing_result)

        return fitness
