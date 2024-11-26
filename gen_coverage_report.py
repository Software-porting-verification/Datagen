#! /usr/bin/env python3

####################################################
#
#
# Generate coverage report table.
#
# Author: Mao Yifu, maoif@ios.ac.cn
#
#
####################################################

import shutil
import os
import subprocess
import yaml
import argparse
import xlsxwriter
from datetime import datetime

g_temp_path = ""

parser = argparse.ArgumentParser(
    description='Generate coverage report table.')
parser.add_argument('-p', '--path', required=True, help='Path to the raw, colon-seperated data file.')

args = parser.parse_args()
g_temp_path = args.path

if not os.path.isfile(g_temp_path):
    print(f'Error: bad path')
    exit(-1)

cov_file = f'coverage_report_{datetime.now().strftime("%Y_%m_%d_%H_%M_%S")}.xlsx'
workbook = xlsxwriter.Workbook(cov_file)
worksheet = workbook.add_worksheet()

cell_bg_green = workbook.add_format()
cell_bg_green.set_bg_color('#6EC207')
cell_bg_orange = workbook.add_format()
cell_bg_orange.set_bg_color('#F09319')
cell_bg_red = workbook.add_format()
cell_bg_red.set_bg_color('#EE4E4E')

worksheet.write(0, 0, 'Package')
worksheet.write(0, 1, 'Func Cov')
worksheet.write(0, 2, 'Line Cov')
worksheet.write(0, 3, '#Line Cov')
worksheet.write(0, 4, '#Line Total')


with open(g_temp_path) as f:
    lines = f.readlines()

    row = 1
    numbers = []
    for line in lines:
        pkg, func_cov, line_cov, lines_cov, lines_total = line.split(':')
        try:
            func_cov = float(func_cov)
            line_cov = float(line_cov)
            lines_cov = float(lines_cov)
            lines_total = float(lines_total)
        except ValueError:
            print(f'Bad line: {line}')
            exit(-1)
        numbers.append((pkg, func_cov, line_cov, lines_cov, lines_total))

    # sort according to line_cov
    numbers.sort(key=lambda x: x[2], reverse=True)

    total_lines_cov   = 0
    total_lines_total = 0

    for pkg, func_cov, line_cov, lines_cov, lines_total in numbers:
        worksheet.write(row, 0, pkg)
        if func_cov >= 70:
            worksheet.write(row, 1, func_cov, cell_bg_green)
        elif 0 < func_cov:
            worksheet.write(row, 1, func_cov, cell_bg_orange)
        else:
            worksheet.write(row, 1, func_cov, cell_bg_red)

        if line_cov >= 70:
            worksheet.write(row, 2, line_cov, cell_bg_green)
        elif 0 < line_cov:
            worksheet.write(row, 2, line_cov, cell_bg_orange)
        else:
            worksheet.write(row, 2, line_cov, cell_bg_red)

        worksheet.write(row, 3, lines_cov)
        worksheet.write(row, 4, lines_total)

        total_lines_cov += lines_cov
        total_lines_total += lines_total

        row += 1

    worksheet.write(row, 0, 'Total')
    worksheet.write(row, 3, total_lines_cov)
    worksheet.write(row, 4, total_lines_total)

workbook.close()
print(f'Coverage report at {cov_file}')