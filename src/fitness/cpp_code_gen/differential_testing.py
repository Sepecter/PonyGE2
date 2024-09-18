import os
from os import getcwd, path
import re
from algorithm.parameters import params
from stats.stats import stats

error_content_pattern = r'error:\s*(.*)'


def extract_errors(compile_output):
    error_messages = []

    # 遍历编译输出的每一行，匹配 error 后面的内容
    for line in compile_output.splitlines():
        error_match = re.search(error_content_pattern, line)
        if error_match:
            error_message = error_match.group(1).strip()  # 提取错误内容并去除多余空白
            error_messages.append(error_message)

    return error_messages


def EDecomposer(text):
    # lines contain error messages
    error_lines = []
    # a dictionary record of an error message compiler front-end
    result = set()

    for line in text.split('\n'):
        if "error" in line:
            error_lines.append(line)

    for line in error_lines:
        error_parts = line.split(":")
        for part in error_parts:
            result.add(part.strip())

    return result


def EAligner(e1, e2):
    # a set of elements to remove from e1
    rm1 = set()
    # a set of elements to remove from e2
    rm2 = set()
    # step 1. Remove equivalent pairs
    for a in e1:
        for b in e2:
            if a == b:  # check for equivalent pair
                rm1.add(a)
                rm2.add(b)
    # step 2. Compute pairs with missing records
    missing = set()
    for a in (set(e1) - rm1):
        missing.add((a, None))  # append with None for missing record
    for b in (set(e2) - rm2):
        missing.add((None, b))  # append with None for missing record
    return missing


def Filter(crashed_source, re_missing):
    # a set of unique crashing records
    crash_set = set()
    # a set of unique missing records
    missing_set = set()

    # Step 1. Filter crashes
    for line in crashed_source:
        if line not in crash_set:
            crash_set.add(line)

    # Step 2. Filter inconsistencies
    for miss in re_missing:
        if miss not in missing_set:
            missing_set.add(miss)

    return [crash_set, missing_set]


def differential_testing(gcc_errors, clang_errors, crashed_source, time, compiling_result):
    # 提取并比对错误信息
    if compiling_result == 1:
        flag = 0
        clang_error_messages = extract_errors(clang_errors)
        for i in clang_error_messages:
            if i not in stats['clang_bugs']:
                stats['clang_bugs'].append(i)
                flag = 1
        if flag == 0:
            return 0
    if compiling_result == 2:
        flag = 0
        gcc_error_messages = extract_errors(gcc_errors)
        for i in gcc_error_messages:
            if i not in stats['gcc_bugs']:
                stats['gcc_bugs'].append(i)
                flag = 1
        if flag == 0:
            return 0

    gcc_results = EDecomposer(gcc_errors)
    clang_results = EDecomposer(clang_errors)

    missing = EAligner(gcc_results, clang_results)

    crash_set, missing_set = Filter(crashed_source.split('\n'), missing)

    path_1 = path.join(params['FILE_PATH'], "code_results", "differential_testing")
    # DEBUG
    # path_2 = path.join(getcwd(), "..", "results", "bugs")

    if crash_set and str(crash_set) != "{\'\'}":
        file_path = path.join(path_1, time + '_crash.txt')
        with open(file_path, 'w') as f:
            f.write(str(crash_set))
        # file_path = path.join(path_2, time + '_crash.txt')
        # with open(file_path, 'w') as f:
        #     f.write(str(crash_set))

    if missing_set:
        file_path = path.join(path_1, time + '_missing.txt')
        with open(file_path, 'w') as f:
            f.write(str(missing_set) + "\ncompiling_result:" + str(compiling_result))
        # file_path = path.join(path_2, time + '_missing.txt')
        # with open(file_path, 'w') as f:
        #     f.write(str(missing_set) + "\ncompiling_result:" + str(compiling_result))
        return 1
    else:
        return 0
