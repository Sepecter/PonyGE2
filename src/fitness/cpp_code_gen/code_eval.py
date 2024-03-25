from fitness.base_ff_classes.base_ff import base_ff
from os import getcwd, path
from fitness.cpp_code_gen.differential_testing import differential_testing
import os
import subprocess
from datetime import datetime
import math


def calculate_fitness(length, number, compiling_result, differential_testing_result):
    expected_length = 100
    expected_number = 30
    if differential_testing_result == 1:
        return 0
    if compiling_result == 0:
        fitness = 1000
    elif compiling_result == 1 or compiling_result == 2:
        fitness = 0
    else:
        fitness = 500 - 100 * (math.exp(-(length - expected_length) ** 2) + math.exp(-(number - expected_number) ** 2))
        # 越接近fitness越小
    return fitness


def compile_code(code):
    result = 0
    # 指定文件路径
    path_1 = path.join(getcwd(), "..", "results")
    path_1 = path.join(path_1, "code")
    file_path = path.join(path_1, datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f') + '.cpp')

    # 打开文件并将内容写入
    with open(file_path, 'w') as f:
        f.write(code)
    # 定义要编译的C++文件列表
    cpp_file = file_path

    # 定义编译器命令
    compiler1 = 'g++'
    compiler2 = 'clang-7'
    # compiler2 = 'g++'
    output_dir = path_1 + 'bin'  # 编译后的可执行文件存放目录
    compile_command1 = [compiler1, '-o', '', '-c']  # 可以添加其他编译选项，比如 -O3（优化等级）
    compile_command2 = [compiler2, '-o', '', '-c']
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 循环编译每个C++文件

    # 构建输出文件的完整路径
    output_file = os.path.join(output_dir, os.path.splitext(cpp_file)[0])
    compile_command1[2] = output_file  # 更新编译器命令中的输出文件路径
    compile_command1.append(cpp_file)  # 添加要编译的C++文件路径
    compile_command2[2] = output_file
    compile_command2.append(cpp_file)
    gcc_error_file = ''
    clang_error_file = ''
    # 执行编译器1命令
    try:
        output = subprocess.check_output(compile_command1, stderr=subprocess.STDOUT, universal_newlines=True)
        result |= 1
        # print(f'Compiled {cpp_file} successfully!')
    except subprocess.CalledProcessError as e:
        # print(f'Failed to compile {cpp_file}.')
        error_file_path = f'{output_file}_gcc_error.txt'
        gcc_error_file = error_file_path
        with open(error_file_path, 'w') as error_file:
            error_file.write(e.output)
    # 执行编译器2命令
    try:
        output = subprocess.check_output(compile_command2, stderr=subprocess.STDOUT, universal_newlines=True)
        result |= 2
        # print(f'Compiled {cpp_file} successfully!')
    except subprocess.CalledProcessError as e:
        # print(f'Failed to compile {cpp_file}.')
        error_file_path = f'{output_file}_clang_error.txt'
        clang_error_file = error_file_path
        with open(error_file_path, 'w') as error_file:
            error_file.write(e.output)
    return result, gcc_error_file, clang_error_file


def fill_identifiers(raw_code):
    raw_code = raw_code.split(' ')
    length = len(raw_code)
    cnt = 0
    code = ''
    for i in range(length):
        if raw_code[i] == 'Identifier':
            raw_code[i] = 'X' + str(cnt)
            cnt += 1
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
        code = fill_identifiers(raw_code)
        compiling_result, gcc_error_file, clang_error_file = compile_code(code)
        length = calculate_length(raw_code)
        number = calculate_number(raw_code)
        differential_testing_result = 0
        if compiling_result != 0:
            differential_testing_result = differential_testing(gcc_error_file, clang_error_file)
        fitness = calculate_fitness(length, number, compiling_result, differential_testing_result)

        return fitness
