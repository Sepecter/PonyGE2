# code_eval.py

from fitness.base_ff_classes.base_ff import base_ff
from os import path
from algorithm.parameters import params
from stats.stats import stats
import os
import random
from datetime import datetime
import math


def calculate_fitness(length, number):
    size = params['POPULATION_SIZE']
    if stats['last_gen'] != stats['gen']:
        stats['last_gen'] = stats['gen']
        stats['last_sum_number'] = stats['sum_number']
        stats['sum_number'] = 0

    stats['sum_number'] += number

    expected_length = 700
    fitness = 20 - 10 * math.exp(-(length - expected_length) ** 2)

    return fitness


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


def save_generated_code(code):
    """
    Save generated programs for offline differential testing after evolution.
    """
    now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')
    gen = stats.get('gen', 0)
    output_dir = path.join(params['FILE_PATH'], "code_results", "exclude_diff_generated")
    os.makedirs(output_dir, exist_ok=True)

    file_name = f"gen_{gen:04d}_{now}.cpp"
    file_path = path.join(output_dir, file_name)
    with open(file_path, 'w') as f:
        f.write(code)

    return file_path


class code_eval(base_ff):

    def __init__(self):
        super().__init__()

    def evaluate(self, ind, **kwargs):
        raw_code = ind.phenotype

        identifier_pool = ''
        code = identifier_pool + fill_identifiers(raw_code)

        length = calculate_length(raw_code)
        number = calculate_number(raw_code)
        save_generated_code(code)

        # No online differential-testing guidance in this baseline.
        # GE evolves only according to structural fitness, and all saved
        # programs are evaluated offline after the run.
        return calculate_fitness(length, number)
