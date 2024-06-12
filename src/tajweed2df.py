#!/usr/bin/env python3
#
#    tajweed2df.py
#
# convert tajweed rules counts to dataframe
#
# Copyright (C) 2023 Alicia González Martínez
#  
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# TODO:
#   * add functionality for --group --rm_hapax param
# 
# dependencies:
#   * rasm library
#   * ../data/json/rules_counts.json
#
# examples:
#   $ cat ../data/rules_counts.json | python tajweed2df.py --groups --rm_hapax ../data/tajweed_all.csv
#   $ cat ../data/rules_counts.json | python tajweed2df.py --groups --rm_hapax --chunks 30 ../data/tajweed_groups_30.csv
#   $ cat ../data/rules_counts.json | python tajweed2df.py --groups --rm_hapax --chunks 30 --exclude ../data/tajweed_groups_30_exclude.csv
#   $ cat ../data/rules_counts.json | python tajweed2df.py --groups --rm_hapax --chunks 30 --restrict ../data/tajweed_groups_10_restrict.csv
#
############################################################################################################################################

import os
import io
import re
import sys
import pandas as pd
import ujson as json
from argparse import ArgumentParser, FileType

from rasm import rasm


RULE_GROUPS = {
    'ASSIM-M': ['M1', 'M2'],
    'ASSIM-N': ['N2.1.1.A', 'N2.1.1.B', 'N2.1.1.C', 'N2.1.1.D', 'N2.1.2.A', 'N2.1.2.B', 'N2.1.2.C', 'N2.1.2.D', 'N2.2.A', 'N2.2.B', 'N2.2.C',
                  'N2.2.D', 'N3.A', 'N3.B', 'N3.C', 'N3.D', 'N4.A', 'N4.B', 'N4.C', 'N4.D'],
    'ASSIM': ['MITHL-bb', 'MITHL-dd', 'MITHL-kk', 'MITHL-ll', 'MITHL-yy', 'MITHL-hh', 'MITHL-ww', 'MITHL-tt', 'MITHL-rr', 'MITHL-ðð', 'MITHL-ff', 'MITHL-33',
              'MTJNS-dt', 'MTJNS-td', 'MTJNS-tT', 'MTJNS-ṯð', 'MTJNS-lr', 'MTJNS-ðṮ', 'MTJNS-qk', 'MTJNS-bm', 't-assim'],
    'MADDA': ['MADD-hmz', 'MADD-hmz-A-sil', 'MADD-hmz-sp-1', 'MADD-hmz-sp-2', 'MADD-hmz-sp-3', 'MADD-hmz-sp-4', 'MADD-lzm', 'MADD-shdd-skn', 'MADD-sp-1', 'MADD-sp-2',
              'MADD-sp-3', 'MADD-sp-4', 'MADD-sp-5', 'MADD-sp-6', 'MADD-sp-7', 'MADD-sp-8', 'MADD-sp-9', 'MADD-sp-A', 'MADD-sp-B', 'MADD-sp-C', 'MADD-sp-D'],
    'SHAMS': ['SHMS'],
    'CLIT-H': ['HU', 'HI'],
    'MIN-W': ['min-u-1', 'min-u-2', 'min-u-3', 'min-u-4', 'min-u-5', 'min-u-6', 'min-u-7', 'min-u-8'],
    'MIN-Y': ['min-y-1', 'min-y-2', 'min-y-3', 'min-y-4', 'min-y-5', 'min-y-6', 'min-y-7', 'min-y-8', 'min-y-9', 'min-y-A'],
    'P_SIL': ['P-sil-1', 'P-sil-2'],
    'SIL': ['Sil-1', 'Sil-2', 'Sil-3', 'Sil-4', 'Sil-5', 'Sil-6', 'Sil-7', 'Sil-8', 'Sil-9', 'Sil-A', 'Sil-B', 'Sil-C', 'Sil-D', 'Sil-E', 'Sil-F', 'Sil-G'],
    'SAKT': ['sakt-1', 'sakt-2', 'sakt-3'],
    'HAPAX': ['hapax-1', 'hapax-2', 'hapax-3'],
}

#FIXME add reference
# According to Nicolai Sinai the following list seems to be additions:
# Q. 52:21, 53:23, 53:26–32, 69:7, 73:20, 74:31, 74:56, 78:37–40, 81:29, 84:25, 85:7–11, 87:7, 89:15–16, 89:23–24, 89:27–30, 90:17–20, 95:6, 97:4, and 103:3
EXCLUDE = [(52,21), (53,23), (53,26), (53,27), (53,28), (53,29), (53,30), (53,31), (53,32),
           (69,7),
           (73,20), (74,31), (74,56),
           (78,37), (78,38), (78,39), (78,40),
           (81,29),
           (84,25), (85,7), (85,8), (85,9), (85,10), (85,11),
           (87,7),
           (89,15), (89,16), (89,23), (89,24), (89,27), (89,28), (89,29), (89,30), (90,17), (90,18), (90,19), (90,20),
           (95,6),
           (97,4),
           (103,3)]


if __name__ == '__main__':

    parser = ArgumentParser(description='add or remove tajweed phonetic layer to orthography in Quranic text')
    parser.add_argument('infile', nargs='?', type=FileType('r'), default=sys.stdin, help='counts json file')
    parser.add_argument('outfile', help='csv outfile') #DEBUG
    parser.add_argument('--groups', action='store_true', help='aggregate the rules in logical groups and sum the counts')
    parser.add_argument('--rm_hapax', action='store_true', help='do not include hapax rule')
    parser.add_argument('--exclude', action='store_true', help='exclude verses that have been identified as possible later additions')
    parser.add_argument('--restrict', action='store_true', help='include ONLY verses have been identified as possible later additions')
    parser.add_argument('--chunks', metavar='SIZE', type=int, help='aggregate counts in chunks of words instead of by verses')
    parser.add_argument('--debug', action='store_true', help='show debugging info')
    args = parser.parse_args()

    counts = json.load(args.infile)

    RULE_MAPPER = {rule:gr for gr,rule_li in RULE_GROUPS.items() for rule in rule_li}

    if args.groups:
        _cnt = dict(zip(RULE_GROUPS, [0]*len(RULE_GROUPS)))
    else:
        _cnt = dict(zip(RULE_MAPPER, [0]*len(RULE_MAPPER)))

    cnt_inner = dict(_cnt)
    cnt_bound = dict(_cnt)

    rows = []
    for qara, _, _, qpal, qind in rasm(((1,1,1,1), (114,6,3,4)), paleo=True):

        if args.restrict and (qind[0], qind[1]) not in EXCLUDE:
            continue

        if args.exclude and (qind[0], qind[1]) in EXCLUDE:
            continue

        for rule, tokens in counts.items():

            if args.rm_hapax and rule in RULE_GROUPS['HAPAX']:
                continue
            
            if args.groups:
                rule = RULE_MAPPER[rule]

            for token in tokens:
                if tuple(token['ind']) == qind:

                    if token['bound']:
                        cnt_bound[rule] += token['cnt']
                    else:
                        cnt_inner[rule] += token['cnt']

        rows.append({**{'qindex': ':'.join(map(str, qind))},
                     **{k+'_I':v for k,v in cnt_inner.items()},
                     **{k+'_B':v for k,v in cnt_bound.items()}})

        cnt_inner = dict(_cnt)
        cnt_bound = dict(_cnt)

    if args.chunks:
        aux = []
        for i in range(0, len(rows), args.chunks):
            row_group = rows[i:i+args.chunks]
            qindex = row_group[0]['qindex']
            for r in row_group:
                r.pop('qindex')
            new_row = dict(zip(row_group[0].keys(), [0]*len(row_group[0])))
            for row in row_group:
                for k in row:
                    new_row[k] += row[k]
            new_row['qindex'] = qindex
            aux.append(new_row)
        rows = aux

    df = pd.DataFrame([r.values() for r in rows])
    df.columns = rows[0].keys()

    # move qindex from last column position to first position
    cols = df.columns.tolist()
    df = df[cols[-1:]+cols[:-1]]

    # remove columns that only contain zeros
    df = df.loc[:, (df!=0).any(axis=0)]

    df.to_csv(args.outfile, index=False)

