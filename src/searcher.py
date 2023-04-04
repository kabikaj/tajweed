#!/usr/bin/env python3
#
#    searcher.py
#                                                                                                   احفظ هذا المصودر يا كبيكج يا كبيكج
# find text in the quran and retrieve index; supports regex and unicode in hexadecimal
#
# Copyright (C) 2023 Alicia González Martínez
#
# Format of index:
#   sura:verse:verseloc,medinapage:medinapageloc,cairopage:cairoline:cairolineloc,absloc
#
# output:
#     TOKEN INDEX
#     TOKEN INDEX TOKEN INDEX
#
#     example:
#       $ python searcher.py --text "ۜ."
#       >> وَيَبۡصُۜطُ 39,2:245:14,4878
#       >> بَصۜۡطَةࣰ 159,7:69:22,20416
#       >> عِوَجَاۜ 293,18:1:15,37729 قَيِّمࣰا 293,18:2:1,37730
#       >> (...)
#
# output with --join option:
#     TOKEN INDEX
#     TOKEN INDEX INDEX
#
#     example:
#       $ python searcher.py --text "ۜ." --join
#       >> وَيَبۡصُۜطُ 2:245:14,39:115,50:7:7,4878
#       >> بَصۜۡطَةࣰ 7:69:22,159:29,203:9:6,20416
#       >> عِوَجَاۜقَيِّمࣰا 18:1:15,293:108,380:4:2,37730 18:2:1,293:109,380:4:3,37731
#       >> (...)
#
# TODO
# ====
#   * add processing of {i,j} to CHAR_SPLITTER
#   * FIXME: it seems that some results are doubled !!!
#
# String containing all pausal marks:
#    "ۘۙۚۖۗۛ" # 6d8,6d9,6da,6d6,6d7,6db
#
#  To get full text of hadith al-islam:
#  $ cat ../hadith.al-islam/*.json | jq -r '.original, .commentary' > hadith.al-islam_all
#
# examples:
#
#  $ python searcher.py --hex 6e8,62c,650
#
#  $ python searcher.py --text "ال"
#
#  $ python searcher.py --text "ۜ."
#  $ python searcher.py --hex 6dc
#
#  $ python searcher.py --text ب. --only --join | awk '{print $1}' | LC_ALL=C sort | LC_ALL=C uniq -c | LC_ALL=C sort -nr | 
#    python -c "exec('import sys\nimport unicodedata as u\nfor i, text in (l.strip().split(None, 1) \
#    for l in sys.stdin): print(\'\\\n\', i, \'\\\n\', \'\\\n\'.join(\'{} {} {}\'.format(c, \'U+\'+hex(ord(c))[2:].zfill(4), \
#    u.name(c)) for c in text if u.category(c)[0]!=\'C\'))')"
#
#  $ python searcher.py --hex 628,628
#
#  $ python searcher.py --text "ً."  | grep  -o $'\xd9\x8e.' | awk '{print $1}' | LC_ALL=C sort | LC_ALL=C uniq
#
#  $ cat ../hadith.al-islam/*.json | jq -r '.original, .commentary'
#
##########################################################################################################################

import os
import re
import sys
import ujson as json
from argparse import ArgumentParser, FileType, ArgumentTypeError


MUSHAF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/_private/mushaf.json')

# spirits for the spirits
CHAR_SPLITTER = re.compile(r'((?:[\[\(].+[\)\]]|\\?.)(?:\?|\+|\*|\{\d+(?:,\d+)?\})?\??)')

NOISY_CHARS = {c : None for c in (0x200c, ord('<'), ord('>'), ord('['), ord(']'), 0x6d6,
                                  0x6d7, 0x6d8, 0x6d9, 0x6da, 0x6db, 0x6de, 0x6e9)}


def parse_seq(arg):
    """ Check if arg is given as a sequence of hex unicodes separated
    by comma, eg.: 6e8,62c,650 and return a unicode uninterrumpted string.

    Args:
        arg (str): sequence of hex unicodes with the format (d)ddd,[(d)ddd,...]

    Return:
        str: uninterrupted unicode string.

    Raise:
        ArgumentTypeError: if arg does not follow the format ddd,[ddd,...]

    """
    if re.match(r'[\da-fA-F]{3,4}(,[\da-fA-F]{3,4})*', arg):
        return ''.join(chr(int(h, 16)) for h in arg.split(','))

    raise ArgumentTypeError('argument format must be (d)ddd,[(d)ddd,...], eg. 6e8,62c,650 ')


def search_btw_words(str1, str2, tokens):
    """ apply regex search of two strings str1 and str2 in two consecutive words from tokens

    Args:
        str1 (str): string to search in first word.
        str2 (str): string to search in following word.

    Yield:
        int, dict, sre.SRE_Match object, int, dict, sre.SRE_Match object:
            two pairs containing absolute index, token and search object.

    """
    yield from filter(lambda x : x[2] and x[5],
                        (
                           (
                             tokens[j][0],
                             tokens[j][1],
                             re.findall('(%s)$' % str1, tokens[j][1]['tok']),

                             tokens[j+1][0],
                             tokens[j+1][1],
                             re.findall('^(%s)' % str2, tokens[j+1][1]['tok'])
                           )
                           for j in range(len(tokens)) if j<len(tokens)-1
                        )
                     )

def apply_search(string, tokens):
    """ search string in each token from tokens and in between two tokens.

    Args:
        string (str): sequence to search.
        tokens (list): struct containig absolute index of token, and each token and its indexes as a dict.

    yield:
        int, dict, sre.SRE_Match object, int, dict, sre.SRE_Match object:
            two pairs containing absolute index, token and search object.
        int, dict, sre.SRE_Match object, dict: absolute index, token and search object.

    """
    if '_' in args.string:

        yield from search_btw_words(*args.string.split('_', 1), tokens)

    else:

        yield from filter(lambda x: x[2], ((i, tok, re.findall('(%s)' % args.string, tok['tok'])) for i, tok in tokens))

        if not '^' in args.string and not '$' in args.string:

            segmented = re.findall(CHAR_SPLITTER, args.string)

            for i in range(1, len(segmented)):
                yield from search_btw_words(''.join(segmented[:i]), ''.join(segmented[i:]), tokens)


if __name__ == '__main__':

    parser = ArgumentParser(description='''Search string in quran and retrieve matched string and index. Use "_" to mark explicitly
                a word boundary. The presence of ^ or $ force the search to be applied to isolated words and not across boundaries''')

    parser.add_argument('--file', type=FileType('r'), default=MUSHAF_PATH, help='input file containing quran [DEFAULT: WebQuran]')
    parser.add_argument('outfile', nargs='?', type=FileType('w'), default=sys.stdout, help='output file')

    query = parser.add_mutually_exclusive_group(required=True)
    query.add_argument('--hex', dest='string', type=parse_seq, help='sequence of unicodes to search, eg.: 6e8,62c,650')
    query.add_argument('--text', dest='string', help='text to search (supports regex)')

    parser.add_argument('--only', action='store_true', help='print matched sequence only and not full token')
    parser.add_argument('--join', action='store_true', help='print together two matches from consecutive words')
    parser.add_argument('--not_normalise', action='store_true', help='do not normalise quran (i.e. do not ignore 200c, <, >, [, ], 6d6-6db, 6de, 6e9)')

    args = parser.parse_args()

    if args.string.count('_') > 1:
        parser.error('--text cannot contain more than one word boundary mark "_"')

    tokens = list(enumerate(json.load(args.file)))

    if not args.not_normalise:
        i = 0
        while i < len(tokens):
            tokens[i][1]['tok'] = tokens[i][1]['tok'].translate(NOISY_CHARS)
            if not tokens[i][1]['tok']:
                tokens.pop(i)
            else:
                i += 1

    results = apply_search(args.string, tokens)

    for iabs, tok, found, *next_ in results:

        matches = found if args.only else [tok['tok']]

        for match in matches:

            if args.join and next_:
                
                iabs2, tok2, search_obj2 = next_
                
                res = match + (search_obj2[0] if args.only else tok2['tok'])
    
                res += ' %d:%d:%d,%d:%d,%d:%d:%d,%d %d:%d:%d,%d:%d,%d:%d:%d,%d' % (
                        tok['sura'], tok['vers'], tok['word'],
                        tok['mpage'], tok['mword'], 
                        tok['cpage'], tok['cline'], tok['cword'],
                        iabs,
                        tok2['sura'], tok2['vers'], tok2['word'],
                        tok2['mpage'], tok2['mword'], 
                        tok2['cpage'], tok2['cline'], tok2['cword'],
                        iabs2)
    
            else:
    
                res = '%s %d:%d:%d,%d:%d,%d:%d:%d,%d' % (match,
                        tok['sura'], tok['vers'], tok['word'],
                        tok['mpage'], tok['mword'], 
                        tok['cpage'], tok['cline'], tok['cword'],
                        iabs)
    
                if next_:
                    iabs, tok, found = next_
                    match = found[0] if args.only else tok['tok']
                    res += ' %s %d:%d:%d,%d:%d,%d:%d:%d,%d' % (match,
                        tok['sura'], tok['vers'], tok['word'],
                        tok['mpage'], tok['mword'], 
                        tok['cpage'], tok['cline'], tok['cword'],
                        iabs)
    
            print(res, file=args.outfile)

