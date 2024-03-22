from os import getcwd, path

def EDecomposer(text):
    # lines contain error messages
    error_lines = []
    # a dictionary record of a error message compiler front-end
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


def differential_testing(gcc_file, clang_file):
    gcc_errors = ''
    clang_errors = ''

    # 打开文件并读取内容
    with open(gcc_file, 'r') as f:
        # 读取整个文件内容
        gcc_errors = f.read()

    # 打开文件并读取内容
    with open(clang_file, 'r') as f:
        # 读取整个文件内容
        clang_errors = f.read()

    gcc_results = EDecomposer(gcc_errors)
    clang_results = EDecomposer(clang_errors)

    missing = EAligner(gcc_results, clang_results)

    crash_set, missing_set = Filter([], missing)

    if crash_set or missing_set:
        path_1 = path.join(getcwd(), "..", "results")
        file_path = path_1 + gcc_file + clang_file + 'missing.txt'
        with open(file_path, 'w') as f:
            f.write(missing_set)
        return 1
    else:
        return 0
