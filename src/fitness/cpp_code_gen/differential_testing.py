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


def Filter(crashed_source):
    # a set of unique crashing records
    crash_set = set()

    # Step 1. Filter crashes
    for line in crashed_source:
        if line not in crash_set:
            crash_set.add(line)

    return crash_set


def differential_testing(gcc_errors, clang_errors, crashed_source, time, compiling_result):
    crash_set = Filter(crashed_source.split('\n'))

    path_1 = path.join(params['FILE_PATH'], "code_results", "differential_testing")
    # DEBUG
    # path_2 = path.join(getcwd(), "..", "results", "bugs")
    # 判断是否触发崩溃
    if crash_set and str(crash_set) != "{\'\'}":
        file_path = path.join(path_1, time + '_crash.txt')
        with open(file_path, 'w') as f:
            f.write(str(crash_set))
        # file_path = path.join(path_2, time + '_crash.txt')
        # with open(file_path, 'w') as f:
        #     f.write(str(crash_set))
        return 1

    # 提取并比对错误信息
    if compiling_result == 1:
        flag = 0
        clang_error_messages = extract_errors(clang_errors)
        for i in clang_error_messages:
            for pattern in stats['clang_errors']:
                match_result = re.findall(pattern, i)
            if not match_result:
                stats['clang_errors'].append(i)
                flag = 1
        if flag == 0:
            return 0
    if compiling_result == 2:
        flag = 0
        gcc_error_messages = extract_errors(gcc_errors)
        for i in gcc_error_messages:
            for pattern in stats['gcc_errors']:
                match_result = re.findall(pattern, i)
            if not match_result:
                stats['gcc_errors'].append(i)
                flag = 1
        if flag == 0:
            return 0
    return 1
