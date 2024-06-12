#!/usr/bin/env python3
#
#    tajweed_tabular.py
#
# convert data of counts of rules from tajweed.py to csv containing sum of counts
# for main groups of rules by sura:verse
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
# input file:
#
#     { "M1": [ { "ind": [2, 8, 10],
#                 "cnt": 1
#               },
#               ...
#              ],
#      ... }
#
# output file:
#
#     chunk, M, N, SHMS, MITHL MTJNS
#     0,     0, 0, 3,    0,    0  
#
# examples:
#   $ cat ../data/rules_counts.json | python tajweed_tabular.py > ../data/verses_rules.csv
#   $ cat ../data/rules_counts.json | python tajweed_tabular.py -n 30 > ../data/verses_rules.csv
#
####################################################################################################################

import sys
import ujson as json
from argparse import ArgumentParser, FileType

from rasm import rasm

# group rules in main categories
RULES = ['M', 'N', 'SHMS', 'MTHL', 'MTJNS']

#TODO
# - add arg for range
# - add exclusion list. Aaccording to Nicolai Sinai the following list seem to be additions:
#   Q. 52:21, 53:23, 53:26–32, 69:7, 73:20, 74:31, 74:56, 78:37–40, 81:29, 84:25, 85:7–11, 87:7, 89:15–16, 89:23–24, 89:27–
#   30, 90:17–20, 95:6, 97:4, and 103:3
# Add a reference to this!!!
    

if __name__ == '__main__':

    parser = ArgumentParser(description='create csv with main groups of rules counts in chunks (default by verses)')
    parser.add_argument('infile', nargs='?', type=FileType('r'), default=sys.stdin, help='input json file')
    parser.add_argument('outfile', nargs='?', type=FileType('w'), default=sys.stdout, help='output csv file')
    parser.add_argument('-n', type=int, help='aggregate counts in n-gram of tokens instead of by verses')
    args = parser.parse_args()

    #
    # prepare data
    #

    rules_counts = json.load(args.infile)
    
    parsed = []
    for rule in rules_counts:
        rule_gr = None
        for rule_pat in RULES:
            if rule.startswith(rule_pat):
                rule_gr = rule_pat
                break
        for word in rules_counts[rule]:
            ind = tuple(word['ind'])
            cnt = word['cnt']
    
            parsed.append((rule_gr, ind, cnt))

    #
    # process data in chunks of n-grams
    #

    if args.n:

        # prepare quran indexes
        indexes = [i for *_, i in rasm(((0, None, None, None), (114, None, None, None)))]

        chunks = [indexes[i:i + args.n] for i in range(0, len(indexes), args.n)]

        merged_ = {i:({'M':0, 'N':0, 'SHMS':0, 'MTHL':0, 'MTJNS':0}, chunks[i-1]) for i in range(1, len(chunks)+1)}

        for rule_id, rule_ind, rule_cnt in parsed:
            for i in merged_:
                count_dic, ind_list = merged_[i]
                if rule_ind in ind_list:
                    merged_[i][0][rule_id] = merged_[i][0].get(rule_id, 0)+rule_cnt
                    break

        merged = {k:v[0] for k,v in merged_.items()}

    #
    # process data in groups in verses
    #

    else:

        # prepare quran indexes
        ind_complete = [(i[0], i[1]) for *_, i in rasm(((0, None, None, None), (114, None, None, None)))]

        seen = set()
        indexes = [i for i in ind_complete if not (i in seen or seen.add(i))]
    
        merged = {':'.join(map(str, i)):{'M':0, 'N':0, 'SHMS':0, 'MTHL':0, 'MTJNS':0} for i in indexes}
        for rule_id, rule_ind, rule_cnt in parsed:
            rule_ind = ':'.join(map(str, rule_ind[:-1]))
            merged[rule_ind][rule_id] = merged[rule_ind].get(rule_id, 0)+rule_cnt

    #
    # print csv output
    #

    print('chunk,M,N,SHMS,MITHL,MTJNS', file=args.outfile)
    for ind in merged:
        print(ind, ',', ', '.join(str(c) for _,c in merged[ind].items()), file=args.outfile)

