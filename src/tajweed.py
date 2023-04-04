#!/usr/bin/env python3
#
#    tajweed.py
#
# add or remove tajweed phonetic layer to orthography in Quranic text
# tajweed that is not marked in orthography is not included here
#
# Copyright (C) 2023 Alicia González Martínez
#
# references:
#   https://tajweed.me
#   https://attajweed4beginners.wordpress.com/
#   https://www.iiste.org/Journals/index.php/JPCR/article/view/29201
#
# Quranic text:
#   - we use decotype Quran because tajweed is not completely marked in tanzil uthmani
#   - ى U+0649 used as chair for hamza and dagger
#   - ی U+‌6cc farsi ya is used (not Arabic ya) // BEAWARE that final alif maqsura is also encoded as farsi ya!!!
#   - Notes on special characters (transliteration and meaning):
#     /۟/°/  U+06df ARABIC SMALL HIGH ROUNDED ZERO - U+00B0 DEGREE SIGN / small circle - الصفر المُستَدير: the letter is additional
#                and should not be pronounced either in connection nor pause

#     /۠/⁰/  U+06e0 ARABIC SMALL HIGH UPRIGHT RECTANGULAR ZERO - oval sign - الصفر المستطيل القائم: above alif followed by a vowel letter,
#                indicates that it is additional in consecutive reading but should be pronounced in pause
#     /۫/⌃/  U+06eb ARABIC EMPTY CENTRE HIGH STOP | U+2303 (alt-08963) UP ARROWHEAD ; hapax تَأۡمَ۫نَّا
#     /۪/⌄/  U+06ea ARABIC EMPTY CENTRE LOW STOP | U+2304 DOWN ARROWHEAD ; hapax مَجۡر۪ىٰهَا
#     /۬/•/  U+06ec ARABIC ROUNDED HIGH STOP WITH FILLED CENTRE | U+2022 BULLET ; hapax ءَا۬عۡجَمِىࣱّ
# 
# dependencies:
#   * rasm library
#   * mushaf.json (decotype quran with leeds/tanzil quran morphological information)
#
# examples:
#   $ python tajweed.py --rm --json > ../data/_private/qtokens_rm.json
#   $ python tajweed.py --add --infile ../data/_private/qtokens_rm.json --json > ../data/_private/qtokens_add.json
#   $ diff -y <(rasm --source decotype -q all | awk '{print $1}' | sed -r 's/[ۖۗۘۙۚۛـ]//g')  <(cat ../data/_private/qtokens_add.json | jq -r '.[][0]')
#   $ python tajweed.py --eval --force_qmorf --save_counts ../data/rules_counts.json
#   $ python tajweed.py --eval --restrict 2:10 --debug | grep -v rule
#   $ python tajweed.py --eval --debug 2>&1 | grep "@debug@ FAIL!!"
#
###############################################################################################################################

import os
import io
import re
import sys
import ujson as json
from copy import deepcopy
from functools import partial
from argparse import ArgumentParser, FileType

from rasm import rasm


MYPATH = os.path.abspath(os.path.dirname(__file__))
QDT_FNAME = os.path.join(MYPATH, '../data/_private/mushaf.json')
QMORF_FNAME = os.path.join(MYPATH, '../data/_private/qmorf.json')

# ar.wikipedia.org/wiki/أحكام_النون_الساكنة_والتنوين
HAMZA = 'ءأإؤئ'
ITHHAR = f'{HAMZA}حخعغه'    # حروف الإاظهار ; gutturals, +pharyngeal [ʔħχʕʁh] #NOTE U+06ec is also a hamza sound, but it's a hapax ءَا۬عۡجَمِیࣱّ 41:44:9, not affected by tajweed
IDGHAM = 'نمویلر'           # حروف الإدغام huruf affected by sandhi یرملون #FIXME ب puesta fuera!! // unstable
IKHFA2 = 'تثجدذزسشصضطظفقك'  # حروف الإخفاء
    
CONS = f'ب{ITHHAR}{IDGHAM}{IKHFA2}'

QSTOPS_REGEX = re.compile(r'[ۖۗۘۙۚۛ]')

MADD_HMZ_EXCEPTION = {(2,72,4)}

EXCLUDE_INDEXES_MIN_Y_2 = {(5,81,5), (7,158,23) , (9,113,3), (9,117,5), (33,30,2), (33,32,2), (33,38,4), (33,50,33), (33,53,7), (33,56,6), (49,2,9)}

EXCLUDE_INDEXES_SIL_1 = {(2,160,9), (9,94,13), (15,49,5), (15,89,3), (20,13,1), (20,14,2), (27,9,3), (28,30,16)}
EXCLUDE_INDEXES_SIL_5 = {(7,189,22)}

MITHL_yy_EXCLUDE_INDEXES = {(51,47,3)}

# فِیهِۦ Q.25:69:7
# أُحۡیِۦ Q.2:258:22
# نُحۡیِۦ Q.15:23:3
# نُحۡیِۦ Q.50:43:3
# فَیُحۡیِۦ Q.30:24:11
# وَمَلَإِیهِۦ Q.7:103:9
# وَمَلَإِیهِۦ Q.10:75:9
# وَمَلَإِیهِۦ Q.11:97:3
# وَمَلَإِیهِۦ Q.23:46:3
# وَمَلَإِیهِۦ Q.43:46:7
# وَمَلَإِیهِۦ Q.28:32:21
# وَ‌نَسۡتَحۡیِۦ Q.7:127:17
# وَ‌یَسۡتَحۡیِۦ Q.28:4:14
# فَیَسۡتَحۡیِۦ Q.33:53:32
# یَسۡتَحۡیِۦ Q.33:53:36
# وَلِیِّۦ Q.12:101:15
RESTRICT_INDEXES_MIN_Y_4 = {(25,69,7), (2,258,22), (15,23,3), (50,43,3), (30,24,11), (7,103,9), (10,75,9), (11,97,3), (23,46,3), (43,46,7), (28,32,21),
                            (7,127,17), (28,4,14), (33,53,32), (33,53,36), (12,101,15)}


# لِلۡحَوَارِیِّۧنَ Q.61:14:12
# ٱلۡأُمِّیِّۧنَ   Q.62:2:5
# ٱلۡحَوَارِیِّۧنَ Q.5:111:4
# وَٱلۡأُمِّیِّۧنَ  Q.3:20:13
# ٱلۡأُمِّیِّۧنَ   Q.3:75:30
# رَبَّٰنِیِّۧنَ    Q.3:79:21
RESTRICT_INDEXES_MIN_5 = {(61,14,12), (62,2,5), (5,111,4), (3,20,13), (3,75,30), (3,79,21)}

RESTRICT_INDEXES_SIL_6 = {(5,18,5), (20,18,4), (26,6,4), (6,5,8), (60,4,14), (20,119,3), (12,85,3), (59,17,9), (5,29,12), (5,33,2), (40,50,12),
  (42,21,3), (6,94,21), (30,13,6), (26,197,7), (14,21,5), (40,47,6), (35,28,13), (23,24,2), (27,29,3), (27,32,3), (27,38,3), (10,34,12), (10,34,6), (10,4,8),
  (27,64,2), (30,11,2), (30,27,3), (16,48,9), (25,77,3), (75,13,1), (43,18,2), (14,9,3), (38,21,4), (64,5,3), (11,87,16), (24,8,1), (37,106,4), (42,40,1)}

RESTRICT_INDEXES_SIL_7 = {(20,84,3), (3,119,2), (65,6,13), (11,116,7), (13,19,15), (14,52,12), (24,22,3), (27,33,3), (2,269,15), (38,29,8), (39,18,12),
  (39,9,23), (3,7,45), (46,35,4), (4,8,4), (9,86,11), (17,5,9), (24,22,9), (24,31,51), (28,76,18), (35,1,13), (38,45,6), (48,16,8), (4,83,15), (4,95,7), (73,11,3),
  (9,113,11), (21,37,5), (7,145,18), (12,111,6), (20,128,16), (20,54,8), (24,44,9), (38,43,9), (39,21,30), (3,13,28), (3,190,10), (40,54,3), (65,4,15), (27,33,5),
  (33,6,8), (3,18,9), (8,75,10), (4,59,8), (2,179,5), (2,197,28), (59,2,39), (5,100,12), (65,10,8)}

RESTRICT_INDEXES_MIN_U_7 = {(4,135,30), (18,16,7)}

RESTRICT_INDEXES_SIL_8 = {(8,65,17), (8,66,12), (18,25,5), (24,2,7), (2,259,19), (2,259,35), (2,261,16), (37,147,3), (8,65,13), (8,66,15)}
RESTRICT_INDEXES_SIL_9 = {(21,34,7), (3,144,10), (6,34,21), (10,75,9), (11,97,3), (23,46,3), (28,32,21), (43,46,7), (7,103,9), (10,83,12)}
RESTRICT_INDEXES_SIL_A = {(43,13,1), (11,68,7), (76,4,4), (76,16,1), (4,135,30), (18,16,7), (2,275,20), (2,275,25), (2,275,3), (2,276,3), (2,278,10),
  (3,130,6), (4,161,2), (25,38,2), (29,38,2), (53,51,1), (18,14,12), (47,31,7), (47,4,28), (30,39,5), (13,30,10), (38,67,3), (44,33,6), (4,176,8)}


REMOVE_SANDHI_RULES = [

  #           [      rule applies between two words       ]  [ rule applies inside a word ]
  # ID_RULE,  ((TOK_PRE, TOK_POST), (REPL_PRE, REPL_POST)),  (TOK_INSIDE, REPL_INSIDE),  FILTER_POS,  EXCLUDE_INDEXES,   EXCLUDE_LEMAS,  FORCE_INDEXES,  RESTRICT_INDEXES

  # ID_RULE: id for identifying the rule
  # TOK_PRE: end of word pattern of first token indicating where rule should be applied, when rule applies between words
  # TOK_POST: beggining of word pattern of second token indicating where rule should be applied, when rule applies between words
  # REPL_PRE: end of word replacement text for first token when pattern has been matched, when rule applies between words
  # REPL_POST: beginning of word replacement text for second token when pattern has been matched, when rule applies between words
  # TOK_INSIDE: pattern in token indicating where rule should be applied, when rule applies within a word
  # REPL_INSIDE: replacement text in token when pattern has been matched, when rule applies within a word
  # FILTER_POS: if not None, apply rule only to the words that have a POS included in the list
  # EXCLUDE_INDEXES: exlude Quranic indexes of the form sura:verse:word included in the set. #FIXME see if it is the same as excluding specific wordforms.
  # EXCLUDE_LEMAS: exlude wordforms with LEMAs included in the set.
  # FORCE_INDEXES: force wordforms corresponding to the Quranic indexes included in the set to be applied if the pattern is matched, regardless of EXCLUDE_INDEXES
  #                and EXCLUDE_LEMAS. If the index is included in EXCLUDE_INDEXES it won't be expected to be here.
  # RESTRICT_INDEXES: restrict rule to indexes included in the list.
  
  # ** الميم الساكنة
  #   M1   الإخفاء الشفوي        /m b/mᵒ b/             Q.23:59:2-3 // [β̃ b] no mᵒb/mb inside a word
  ('M1', (('م', 'ب'), ('مۡ', 'ب')), (None, None), None, {}, {}, {}, {}),
  #   M2   الإدغام المثلين       /m mᵚ/mᵒ m/            Q.7:41:1-2  // [mm] no mᵒm/mm inside a word
  ('M2', (('م', 'مّ'), ('مۡ', 'م')), (None, None), None, {}, {}, {}, {}),
  #   M3   الإظهار الشفوي        /(mᵒ ?[^bm])/\1/       Q.2:107:1-2 // no change in orthography

  # ** النون الساكنة
  #   N1   الإاظهار              /(nᵒ[ʔħxʕgh])/\1/      Q.2:35:3-4;Q.1:7:3;Q.2:10:8-9 // no change in orthography
  #   N2   الإدغام
  #    N2.1.1.A ادغام بغنة كامل  /n( [nm])ᵚ/nᵒ\1/       Q.3:104:1-2;Q.11:54:1-2 // no nᵒ[nm]/n[nm] inside a word
  ('N2.1.1.A', ((r'ن', r'([نم])ّ'), (r'نۡ', r'\1')), (None, None), None, {}, {}, {}, {}),
  #    N2.1.1.B                  /ᵃᵃ([AY]? [nm])ᵚ/ᵃⁿ\1/ Q.2:26:7-8;Q.2:5:3-4    // applies only between words
  ('N2.1.1.B', ((r'ࣰ([ای]?)', r'([نم])ّ'), (r'ً\1', r'\1')), (None, None), None, {}, {}, {}, {}),
  #    N2.1.1.C                  /ᵘᵘ((A°)? [nm])ᵚ/ᵘⁿ\1/ Q.9:1:1-2;Q.44:33:6-7   // applies only between words // only one case with ᵘᵘA°: بَلَٰٓؤࣱا۟ (44:33:6)
  ('N2.1.1.C', ((r'ࣱ(ا۟)?', r'([نم])ّ'), (r'ٌ\1', r'\1')), (None, None) , None, {}, {}, {}, {}),
  #    N2.1.1.D                  /ᵢᵢ( [nm])ᵚ/ᵢₙ\1/      Q.4:96:1-2              // applies only between words
  ('N2.1.1.D', ((r'ࣲ', r'([نم])ّ'), (r'ٍ', r'\1')), (None, None), None, {}, {}, {}, {}),
  #    N2.1.2.A ادغام بغنة ناقص  /n( [wy])/nᵒ\1/        Q.2:95:1-2;Q.2:107:14-15 // n retains nasality when the assimilation is to y (palatalization) and w (labialization)
  #                      // does NOT assimilate internally:
  #                      //   2 unique examples with waw; 3 ocurrences: قِنۡوَانࣱ (6:99:23), صِنۡوَانࣱ (13:4:10), صِنۡوَانࣲ (13:4:13)
  #                      //   2 unique examples (with inflectional variations) with ya; many ocurrences, e.g. بُنۡیَٰنَهُم (16:26:8), ٱلدُّنۡیَا (2:85:38)
  ('N2.1.2.A', ((r'ن', r'(?:[وی])'), (r'نۡ', None)), (None, None), None, {}, {}, {}, {}),
  #    N2.1.2.B                  /ᵃᵃ([AY]? [wy])/ᵃⁿ\1/  Q.65:11:1-2;Q.2:22:7-8  // applies only between words
  ('N2.1.2.B', ((r'ࣰ([ای]?)', r'(?:[وی])'), (r'ً\1', None)), (None, None), None, {}, {}, {}, {}),
  #    N2.1.2.C                  /ᵘᵘ( [wy])/ᵘⁿ\1/       Q.88:2:1-2;Q.2:7:9-10   // applies only between words
  ('N2.1.2.C', ((r'ࣱ', r'(?:[وی])'), (r'ٌ', None)), (None, None), None, {}, {}, {}, {}),
  #    N2.1.2.D                  /ᵢᵢ( [wy])/ᵢₙ\1/       Q.2:118:23-24;Q.69:15:1-2 // applies only between words
  ('N2.1.2.D', ((r'ࣲ', r'(?:[وی])'), (r'ٍ', None)), (None, None), None, {}, {}, {}, {}),
  #    N2.2.A   ادغام بلا غنة كامل /n( [rl])ᵚ/nᵒ\1/     Q.2:5:4-5;Q.2:24:1-2   // no cases inside a word
  ('N2.2.A', ((r'ن', r'([رل])ّ'), (r'نۡ', r'\1')), (None, None), None, {}, {}, {}, {}),
    #    N2.2.B                    /ᵃᵃ([AY]? [rl])ᵚ/ᵃⁿ\1/ Q.4:176:35-36;Q.50:11:1-2 // applies only between words
  ('N2.2.B', ((r'ࣰ([ای]?)', r'([رل])ّ'), (r'ً\1', r'\1')), (None, None), None, {}, {}, {}, {}),
  #    N2.2.C                    /ᵘᵘ( [rl])ᵚ/ᵘⁿ\1/      Q.3:31:13-14;Q.56:91:1-2 // applies only between words
  ('N2.2.C', ((r'ࣱ', r'([رل])ّ'), (r'ٌ', r'\1')), (None, None), None, {}, {}, {}, {}),
  #    N2.2.D                    /ᵢᵢ( [rl])ᵚ/ᵢₙ\1/      Q.9:100:8-9;Q.68:12:1-2  // applies only between words
  ('N2.2.D', ((r'ࣲ', r'([رل])ّ'), (r'ٍ', r'\1')), (None, None), None, {}, {}, {}, {}),
  #  N3     الإقلاب (الباء - حرف الإقلاب)       // [β̃ b] recited with the sound between Idghaam and Ikhfaa’
  ('N3.A', ((r'نۢ', r'ب'), ('نۡ', None)), (r'نۢ(?=ب)', 'نۡ'), None, {}, {}, {}, {}),  #  N3.A    /nᵐ(?= ?b)/nᵒ/      Q.7:169:2-3;Q.80:27:1  
  #   N3.B                       /ᵃᵐ(?=A? b)/ᵃⁿ/        Q.2:249:23-24;Q.19:32:1-2 // no case of acc. + alif maqsura (encoded here as farsi ya)
  ('N3.B', ((r'َۢ(ا)?', r'ب'), (r'ً\1', None)), (None, None), None, {}, {}, {}, {}),
  #   N3.C                       /ᵘᵐ(?= b)/ᵘⁿ/          Q.2:18:1-2
  ('N3.C', ((r'ُۢ', r'ب'), (r'ٌ', None)), (None, None), None, {}, {}, {}, {}),
  #   N3.D                       /ᵢₘ(?= b)/ᵢₙ/          Q.80:16:1-2
  ('N3.D', ((r'ِۭ', r'ب'), (r'ٍ', None)), (None, None), None, {}, {}, {}, {}),

  #  N4     الإخفاء   n is approximant // word will be read btw اظهار and إدغام بغنة, and the duration will be of two Harakah
  #   N4.A                       /n(?= ?[tṯjdðzsšSDTṮfqk])/nᵒ/       Q.113:2:1-2;Q.4:109:1
  ('N4.A', ((r'ن', rf'(?=[{IKHFA2}])'), (r'نۡ', None)), (rf'ن(?=[{IKHFA2}])', r'نۡ'), None, {}, {}, {}, {}),
  #   N4.B                       /ᵃᵃ(?=[AY]? [tṯjdðzsšSDTṮfqk])/ᵃⁿ/  Q.22:33:6-7
  ('N4.B', ((rf'ࣰ([ای])?', rf'(?=[{IKHFA2}])'), (r'ً\1', None)),  (None, None), None, {}, {}, {}, {}),
  #   N4.C                       /ᵘᵘ(?= [^tṯjdðzsšSDTṮfqk])/ᵘⁿ/      Q.3:197:2-3
  ('N4.C', ((rf'ࣱ', rf'(?=[{IKHFA2}])'), (r'ٌ', None)),  (None, None), None, {}, {}, {}, {}),
  #   N4.D                       /ᵢᵢ(?= [^tṯjdðzsšSDTṮfqk])/ᵢₙ/      Q.6:132:1-2
  ('N4.D', ((rf'ࣲ', rf'(?=[{IKHFA2}])'), (r'ٍ', None)),  (None, None), None, {}, {}, {}, {}),

  # MADD-hmz - maddda before a hamza - elongation ; "Al-Madd Al-Waajib Al-Mutasil" and "Al-Madd Al-Jaa’ez Al-Munfasil"
  #          یَشَآءُ Q.2:90:18 ; ٱلۡمَلَٰٓىِٕكَةِ Q.2:31:8 ; ٱلسُّفَهَآءُۗ Q.2:13:12 ; بِٱلسُّوٓءِ Q.2:169:3 ; وَجِا۟یٓءَ Q.39:69:7 ; یَٰٓأَیُّهَا Q.2:21:1 ;
  #          فِیٓ أَنفُسِكُمۡۚ Q.2:235:12-13 ; بِمَآ أَنزَلۡتُ Q.2:41:2-3 ; فَٱقۡتُلُوٓا۟ أَنفُسَكُمۡ Q.2:54:14-15 ; بِهِۦٓ إِلَّا Q.83:12:3-4 ;
  #          مُوسَیٰٓ إِذۡ Q.79:15:4-79:16:1 ; فَلَهُۥٓ أَجۡرُهُۥ Q.2:112:8-9 ; هَٰذِهِۦٓ إِیمَٰنࣰاۚ Q.9:124:10-11
  #  فَٱدَّٰرَٰٔۡتُمۡ 2:72:4
  ('MADD-hmz',  ((r'(َا|َیٰ|ُ[وۥ]|ِ[یۦ])ٓ', fr'(?:[{HAMZA}]|[ىی]ٕ|ٔ)'), (r'\1', None)), (fr'(َ[اٰ]|ُ[وۥ]|ِ[یۦ])ٓ(?=ـ?(?:[{HAMZA}]|[ىی]ٕ|ٔ))', r'\1'), None, MADD_HMZ_EXCEPTION, {}, {}, {}),
  ('MADD-hmz-A-sil',  ((r'ُوٓا۟', fr'(?:[{HAMZA}]|[ىی]ٕ)'), (r'ُوا۟', None)), (None, None), None, {}, {}, {}, {}), # جَعَلُوٓا۟ أَصَٰبِعَهُمۡ Q.71:7:6-7
  ('MADD-hmz-sp-1',  ((None, None), (None, None)), ('تَلۡوُۥٓا۟', 'تَلۡوُۥا۟'), None, {}, {}, {}, {}), # Q.4:135:30
  ('MADD-hmz-sp-2',  ((None, None), (None, None)), ('فَأۡوُۥٓا۟', 'فَأۡوُۥا۟'), None, {}, {}, {}, {}), # Q.18:16:7
  ('MADD-hmz-sp-3',  ((None, None), (None, None)), ('وَجِا۟یٓءَ', 'وَجِا۟یءَ'), None, {}, {}, {}, {}), # Q.39:69:7 ; Q.89:23:1
  ('MADD-hmz-sp-4',  (('ٱلرِّبَوٰٓا۟', fr'[{HAMZA}]'), ('ٱلرِّبَوٰا۟', None)), (None, None), None, {}, {}, {}, {}), # Q.2:278:10 ; Q.3:130:6


  # MADD-lzm - Al-Madd Al-Laazim: necessary prolongation: no two saakin letters can follow one another
  #            "Al-madd al-laazim al-kalimee al-muthaqal" (because of shadda) and "Al-madd al-laazim al-kalimee al-mukhaffaf" (because of sukun)
  #            ٱلۡحَآقَّةُ Q.69:1:5 ; وَٱلصَّٰٓفَّٰتِ Q.37:1:5 ; ٱلضَّآلِّینَ Q.1:7:9 ; ءَآلۡـَٰٔنَ Q.10:51:7
  ('MADD-lzm',  ((None, None), (None, None)), (fr'(َ[اٰ]|ُو|ِی)ٓ(?=[{CONS}](?:[ّْ]|[{CONS}]))', r'\1'), None, {}, {}, {}, {}),

  ('MADD-shdd-skn', ((None, None), (None, None)), (fr'َآ([{CONS}])(?=[ّۡ])', r'َا\1'), None, {}, {}, {}, {}),  # دَآبَّةٍ Q.16:49:10 ; ءَآللَهُ Q.10:59:14  #FIXME

  # Al-Madd Al-Laazim Al-Harfee: apply to those chapters in the Quran that start with letters (exception: alif)
  ('MADD-sp-1', ((None, None), (None, None)), (r'^الٓمٓ$', 'الم'), None, {}, {}, {}, {}),     # Q.2:1:5, Q.29:1:5, Q.30:1:5, Q.31:1:5, Q.32:1:5
  ('MADD-sp-2', ((None, None), (None, None)), (r'^طسٓمٓ$', 'طسم'), None, {}, {}, {}, {}),     # Q.26:1:5, Q.28:1:5
  ('MADD-sp-3', ((None, None), (None, None)), (r'^طسٓ$', 'طس'), None, {}, {}, {}, {}),       # Q.27:1:5
  ('MADD-sp-4', ((None, None), (None, None)), (r'^یسٓ$', 'یس'), None, {}, {}, {}, {}),       # Q.36:1:5
  ('MADD-sp-5', ((None, None), (None, None)), (r'^حمٓ$', 'حم'), None, {}, {}, {}, {}),       # Q.40:1:5, Q.41:1:5, Q.42:1:5, Q.43:1:5, Q.44:1:5, Q.45:1:5, Q.46:1:5
  ('MADD-sp-6', ((None, None), (None, None)), (r'^كٓهیعٓصٓ$', 'كهیعص'), None, {}, {}, {}, {}), # Q.19:1:5
  ('MADD-sp-7', ((None, None), (None, None)), (r'^الٓر$', 'الر'), None, {}, {}, {}, {}),     # Q.10:1:5, Q.11:1:5, Q.12:1:5, Q.14:1:5, Q.15:1:5
  ('MADD-sp-8', ((None, None), (None, None)), (r'^الٓمٓصٓ$', 'المص'), None, {}, {}, {}, {}),   # Q.7:1:5
  ('MADD-sp-9', ((None, None), (None, None)), (r'^الٓمٓر$', 'المر'), None, {}, {}, {}, {}),   # Q.13:1:5
  ('MADD-sp-A', ((None, None), (None, None)), (r'^صٓ$', 'ص'), None, {}, {}, {}, {}),         # Q.38:1:5
  ('MADD-sp-B', ((None, None), (None, None)), (r'^عٓسٓقٓ$', 'عسق'), None, {}, {}, {}, {}),     # Q.Q.42:2:1
  ('MADD-sp-C', ((None, None), (None, None)), (r'^قٓ$', 'ق'), None, {}, {}, {}, {}),         # Q.50:1:5
  ('MADD-sp-D', ((None, None), (None, None)), (r'^نٓ$', 'ن'), None, {}, {}, {}, {}),         # Q.68:1:5

  # ŠAMS  اللام الساكنة /(Aᵟ|lᵚ?ᵢ)l([TṯSrtDðndsṮzšl])ᵚ/\1ᵒl\2/   Q.3:3:10
  ('SHMS',  ((None, None), (None, None)), (r'(ٱ|لّ?ِ|وَلَ|ءَا)ل([طثصرتضذندسظزشل])ّ', r'\1لۡ\2'), 'N', {}, {}, {}, {}),

  # Al-Mithlayn المِثْلَين - two consecutive consonants are the same // al idgam al kabir
  ('MITHL-bb', (('ب', 'بّ'), ('بۡ', 'ب')),  (None, None), None, {}, {}, {}, {}),  # Q.2:60:7-8
  ('MITHL-dd', (('د', 'دّ'), ('دۡ', 'د')),  ('ددّ', 'دۡد'), None, {}, {}, {}, {}),  # Q.5:61:5-6 
  ('MITHL-kk', (('ك', 'كّ'), ('كۡ', 'ك')),  ('ككّ', 'كۡك'), None, {}, {}, {}, {}),  # Q.4:78:3
  ('MITHL-ll', (('ل', 'لّ'), ('لۡ', 'ل')),  ('للّ', 'لۡل'), None, {}, {}, {}, {}),  # Q.2:33:10-11
  ('MITHL-yy', ((None, None), (None, None)),  ('ییّ', 'یۡی'), None, MITHL_yy_EXCLUDE_INDEXES, {}, {}, {}),  # بِأَییِّكُمُ Q.68:6:1  ; the exception!! Q.51:47:3 بِأَیۡی۟دࣲ
  ('MITHL-hh', ((None, None), (None, None)),  ('ههّ', 'هۡه'), None, {}, {}, {}, {}),  # یُكۡرِههُّنَّ Q.24:33:41
  ('MITHL-ww', ((r'و(ا۟)?', 'وّ'), (r'وۡ\1', 'و')),  (None, None), None, {}, {}, {}, {}),  # Q.83:3:3-4; Q.2:61:57-58 (with alif)
  ('MITHL-tt', (('ت', 'تّ'), ('تۡ', 'ت')),  (None, None), None, {}, {}, {}, {}),  # Q.64:6:3-4
  ('MITHL-rr', (('ر', 'رّ'), ('رۡ', 'ر')),  (None, None), None, {}, {}, {}, {}),  # Q.3:41:15-16
  ('MITHL-ðð', (('ذ', 'ذّ'), ('ذۡ', 'ذ')),  (None, None), None, {}, {}, {}, {}),  # Q.21:87:3-4
  ('MITHL-ff', (('ف', 'فّ'), ('فۡ', 'ف')),  (None, None), None, {}, {}, {}, {}),  # Q.17:33:17-18
  ('MITHL-33', (('ع', 'عّ'), ('عۡ', 'ع')),  (None, None), None, {}, {}, {}, {}),  # Q.18:78:10-11

  # MTJNS Al-Mutajaanisayn  المُتَجَانِسَين - when a letter in a word with sukoon is followed by a letter with Shaddah and is from the same origin
  # // al idgam al sagir : the mode and/or place of articulation of the consonants in contact are similar
  ('MTJNS-dt', (('د', 'تّ'), ('دۡ', 'ت')),  ('دتّ', 'دۡت'), None, {}, {}, {}, {}), # Q.29:35:1-2
  ('MTJNS-td', (('ت', 'دّ'), ('تۡ', 'د')),  (None, None), None, {}, {}, {}, {}), # Q.29:35:1-2
  ('MTJNS-tT', (('ت', 'طّ'), ('تۡ', 'ط')),  (None, None), None, {}, {}, {}, {}), # Q.61:14:27-28
  ('MTJNS-ṯð', (('ث', 'ذّ'), ('ثۡ', 'ذ')),  (None, None), None, {}, {}, {}, {}), # Q.7:176:20-21
  ('MTJNS-lr', (('ل', 'رّ'), ('لۡ', 'ر')),  (None, None), None, {}, {}, {}, {}), # Q.4:158:1-2
  ('MTJNS-ðṮ', (('ذ', 'ظّ'), ('ذۡ', 'ظ')),  (None, None), None, {}, {}, {}, {}), # Q.4:64:12
  ('MTJNS-qk', ((None, None), (None, None)),  ('قكّ', 'قۡك'), None, {}, {}, {}, {}), # only one case Q.77:20:2
  ('MTJNS-bm', (('ب', 'مّ'), ('بۡ', 'م')),  (None, None), None, {}, {}, {}, {}), # ٱرۡكَب مَّعَنَا Q.11:42:14-15

  # (it does not assimilate with shadda)
  ('t-assim', ((None, None), (None, None)),  ('طت', 'طۡت'), None, {}, {}, {}, {}), # only 4 Q.5:28:2, Q.12:80:21, Q.27:22:5, Q.39:56:7


  # HU - prolongation  IMPORTANT! only for ha clitics, do not apply when ha is part of the LEMA (this is done in the code)
  #      https://tajweed.me/2011/05/11/al-madd-al-silah-kubra-amp-sughra-tajweed-rule
  ('HU',  ((r'(?<=[َُِ])هُۥ', r'[^ٱ]'), ('هُ', None)), (None, None), None, {(39,7,13)}, {}, {}, {}),  # Q.2:126:10


  ('min-u-1',  ((None, None), (None, None)), ('دَاوُۥد', 'دَاوُد'), None, {}, {}, {}, {}),  # Q.34:10:4
  ('min-u-2',  ((None, None), (None, None)), (r'([یت])َلۡوُۥنَ', r'\1َلۡوُنَ'), None, {}, {}, {}, {}),  # Q.3:78:4 ; Q.3:153:5
  ('min-u-3',  ((None, None), (None, None)), ('وُۥرِیَ', 'وُرِیَ'), None, {}, {}, {}, {}),  # Q.7:20:7
  ('min-u-4',  ((None, None), (None, None)), (r'(لِت|ی)َسۡتَوُۥ(ا۟|نَ)', r'\1َسۡتَوُ\2'), None, {}, {}, {}, {}),  # Q.9:19:18 ; Q.16:75:22 ; Q.32:18:8 ; Q.43:13:1
  ('min-u-5',  ((None, None), (None, None)), (r'(وَ)?ٱلۡغَاوُۥنَ', r'\1ٱلۡغَاوُنَ'), None, {}, {}, {}, {}),  # Q.26:94:4 ; Q.26:224:3
  ('min-u-6',  ((None, None), (None, None)), ('ٱلۡمَوۡءُۥدَةُ', 'ٱلۡمَوۡءُدَةُ'), None, {}, {}, {}, {}),  # Q.81:8:2
  ('min-u-7',  ((None, None), (None, None)), ('وُۥ', 'وُ'), None, {}, {}, {}, RESTRICT_INDEXES_MIN_U_7),  # تَلۡوُۥا۟ Q.4:135:30 ; فَأۡوُۥا۟ Q.18:16:7
  ('min-u-8',  ((None, None), (None, None)), (r'لِیَسُۥ(ـ)?ُٔوا', r'لِیَسُ\1ُٔوا'), None, {}, {}, {}, {(17,7,12)}),  # لِیَسُۥُٔوا Q.17:7:12

  ('HI',  ((r'(?<=[َُِ])هِۦ', '[^ٱ]'), ('هِ', None)), (None, None), None, {}, {}, {}, {}),

  ('min-y-1',  ((None, None), (None, None)), ('إِبۡرَٰهِۧم', 'إِبۡرَٰهِم'), None, {}, {}, {}, {}),  # Q.2:126:3
  ('min-y-2',  ((None, None), (None, None)), ('نَبِیِّۧ', 'نَبِیِّ'), None, EXCLUDE_INDEXES_MIN_Y_2, {}, {}, {}),  # Q.39:69:8
  ('min-y-3',  ((r'^یُحۡیِۦ$', r'[^ٱ]'), ('یُحۡیِ', None)), (None, None), None, {}, {}, {}, {}),  # Q.40:68:3
  ('min-y-4',  ((None, None), (None, None)), (r'ۦ$', r''), None, {}, {}, {}, RESTRICT_INDEXES_MIN_Y_4),
  ('min-y-5',  ((None, None), (None, None)), (r'ِۧنَ$', 'ِنَ'), None, {}, {}, {}, RESTRICT_INDEXES_MIN_5),
  ('min-y-6',  ((None, None), (None, None)), ('ءَاتَىٰنِۦ', 'ءَاتَىٰنِ'), None, {}, {}, {}, {(27,36,8)}), # ءَاتَىٰنِۦَ Q.27:36:8
  ('min-y-7',  ((None, None), (None, None)), ('إِۧلَٰفِهِمۡ', 'إِلَٰفِهِمۡ'), None, {}, {}, {}, {(106,2,1)}), # إِۧلَٰفِهِمۡ Q.106:2:1
  ('min-y-8',  ((None, None), (None, None)), ('حِۡۧی', 'حِۡی'), None, {}, {}, {}, {(25,49,1), (46,33,15), (75,40,6)}), # لِنُحِۡۧیَ Q.25:49:1 ; یُحِۡۧیَ Q.46:33:15 ; یُحِۡۧیَ Q.75:40:6
  ('min-y-9',  ((None, None), (None, None)), ('وَلِِّۧی', 'وَلِِّی'), None, {}, {}, {}, {(7,196,2)}), # وَلِِّۧیَ Q.7:196:2
  ('min-y-A',  ((None, None), (None, None)), ('یَسۡتَحۡیِۦ', 'یَسۡتَحۡیِ'), None, {}, {}, {}, {(2,26,5)}), # یَسۡتَحۡیِۦ Q.2:26:5

  # sakt - miniature sin - smooth pause (lexical)
  ('sakt-1',  ((None, None), (None, None)), ('صۜ', 'ص'), None, {}, {}, {}, {(2,245,14), (7,69,22)}), # وَیَبۡصُۜطُ Q.2:245:14 ; بَصۜۡطَةً Q.7:69:22
  ('sakt-2',  ((None, None), (None, None)), ('اۜ', 'ا'), None, {}, {}, {}, {(18,1,15), (36,52,6)}), # عِوَجَاۜ Q.18:1:15 ; مَرۡقَدِنَاۜ Q.36:52:6
  ('sakt-3',  ((None, None), (None, None)), ('ۡۜ', 'ۡ'), None, {}, {}, {}, {(69,28,4), (75,27,2), (83,14,2)}), # مَالِیَهۡۜ Q.69:28:4 ; مَنۡۜ Q.75:27:2 ; بَلۡۜ Q.83:14:2
  
  #pause_pro - al-ṣifr al-mustaṭīl al-qāʾim الصفر المستطيل القائم
  #     /۠/⁰/  U+06e0 ARABIC SMALL HIGH UPRIGHT RECTANGULAR ZERO - oval sign: above alif followed by a vowel letter,
  #                indicates that it is additional in consecutive reading but should be pronounced in pause
  # The Silent & Pronounced Alif - https://tajweed.me/2011/11/30/the-silent-and-pronounced-alif-tajweed-quran-reading-rules-2
  #         U+06e0 is added on alif: it is pronounced in connected speech, but not in pause  $ rasm -q all --pal | grep -P "\tAˀᵃB¹ᵃA[⁰\t]"
  #         أَنَا۠ ; وَأَنَا۠ ; فَأَنَا۠ Q.43:81:6 ; قَوَارِیرَا۠ Q.76:15:8 ; 
  #         Beaware that assimialtion shaddas has been removed in a previous step, so we quote the words without this shadda:
  #             لَٰكِنَّا۠ Q.18:38:1 ; ٱلۡظُنُونَا۠ Q.33:10:16 ; ٱلۡرَسُولَا۠ Q.33:66:11 ; ٱلۡسَبِیلَا۠ Q.33:67:8
  ('P-sil-1', ((None, None), (None, None)), (r'^((?:وَ|فَ)?أَنَا|لَٰكِنَّا|ٱلۡرَسُولَا|ٱلۡسَبِیلَا|ٱلۡظُنُونَا)۠$', r'\1'), None, {}, {}, {}, {}),
  ('P-sil-2', ((None, None), (None, None)), ('قَوَارِیرَا۠', 'قَوَارِیرَا'), None, {}, {}, {}, {(76,15,8)}), # قَوَارِیرَا۠ Q.76:15:8


  #SIL - al-ṣifr al-mustadīr الصفر المُستَدير
  #     /۟/°/  U+06df ARABIC SMALL HIGH ROUNDED ZERO - U+00B0 DEGREE SIGN / small circle: the letter is additional
  #                and should not be pronounced either in connection nor pause
  ('Sil-1', ((None, None), (None, None)), (r'وا۟$', r'وا'), None, {}, {}, {}, {}), # أَجۡرَمُوا۟ Q.6:124:21
  ('Sil-2', ((None, None), (None, None)), (r'َوۡا۟$', r'َوۡا'), None, {}, {}, {}, {}), # فَتَنَادَوۡا۟ Q.68:21:1
  ('Sil-3', ((None, None), (None, None)), ('أُو۟لَٰىِٕك', 'أُولَٰىِٕك'), None, {}, {}, {}, {}), # Q.56:11:1
  ('Sil-4', ((r'و([َُ])ا۟', 'ٱ'), (r'و\1ا', None)), (None, None), None, EXCLUDE_INDEXES_SIL_5, {}, {}, {}), #  Q.2:16:3 ; Q.22:41:8
  ('Sil-5', ((None, None), (None, None)), ('ؤُا۟', 'ؤُا'), None, {}, {}, {}, RESTRICT_INDEXES_SIL_6), # Q.5:18:5
  ('Sil-6', ((None, None), (None, None)), ('أُو۟', 'أُو'), None, {}, {}, {}, RESTRICT_INDEXES_SIL_7), # Q.20:84:3
  ('Sil-7', ((None, None), (None, None)), (r'ا۟(?!$)', 'ا'), None, {}, {}, {}, RESTRICT_INDEXES_SIL_8), # Q.8:65:17
  ('Sil-8', ((None, None), (None, None)), ('إِی۟', 'إِی'), None, {}, {}, {}, RESTRICT_INDEXES_SIL_9), # Q.21:34:7
  ('Sil-9', ((None, None), (None, None)), (r'ا۟$', 'ا'), None, {(76,16,1)}, {}, {}, RESTRICT_INDEXES_SIL_A), # Q.43:13:1
  ('Sil-A', ((None, None), (None, None)), ('ا۟', 'ا'), None, {}, {}, {}, {(39,69,7), (89,23,1)}), # وَجِا۟یءَ Q.39:69:7 ; وَجِا۟یءَ Q.89:23:1
  ('Sil-B', ((None, None), (None, None)), ('قَوَارِیرَا۟', 'قَوَارِیرَا'), None, {}, {}, {}, {(76,16,1)}), # قَوَارِیرَا۟ Q.76:16:1
  ('Sil-C', ((None, None), (None, None)), ('بِأَیۡی۟دٍ', 'بِأَیۡیدٍ'), None, {}, {}, {}, {(51,47,3)}), # بِأَیۡی۟دٍ Q.51:47:3
  ('Sil-D', ((None, None), (None, None)), (r'تَا۟یۡ(ـ)?َٔسُوا', r'تَایۡ\1َٔسُوا'), None, {}, {}, {}, {(12,87,8)}), # تَا۟یَۡٔسُوا Q.12:87:8
  ('Sil-E', ((None, None), (None, None)), ('لَأَا۟ذۡبَحَنَّهُ', 'لَأَاذۡبَحَنَّهُ'), None, {}, {}, {}, {(27,21,5)}), # لَأَا۟ذۡبَحَنَّهُ Q.27:21:5
  ('Sil-F', ((None, None), (None, None)), ('لِشَا۟یۡءٍ', 'لِشَایۡءٍ'), None, {}, {}, {}, {(18,23,3)}), # لِشَا۟یۡءٍ Q.18:23:3
  ('Sil-G', ((None, None), (None, None)), ('یَا۟', 'یَا'), None, {}, {}, {}, {(12,87,14), (13,31,20)}), # یَا۟یَۡٔسُ Q.12:87:14 ; یَا۟یَۡٔسُ Q.13:31:20

#FIXME WARNING-8! untreated tajweed traces! mark in alif for not pronouncing found in یَا۟یَۡٔسِ Q.13:31:20

  # hapax signs
  ('hapax-1', ((None, None), (None, None)), ('مَجۡر۪ىٰهَا', 'مَجۡرىٰهَا'), None, {}, {}, {}, {}), # U+06ea Q.11:41:7
  ('hapax-2', ((None, None), (None, None)), ('تَأۡمَ۫نَّا', 'تَأۡمَنَّا'), None, {}, {}, {}, {}), # U+06eb Q.12:11:6
  ('hapax-3', ((None, None), (None, None)), ('ءَا۬عۡجَمِیّ', 'ءَاعۡجَمِیّ'), None, {}, {}, {}, {}), # U+06ec Q.41:44:9

]

RESTORE_SANDHI_RULES = [

  ('hapax-1', ((None, None), (None, None)), ('مَجۡرىٰهَا', 'مَجۡر۪ىٰهَا'), None, {}, {}, {}, {}),
  ('hapax-2', ((None, None), (None, None)), ('تَأۡمَنَّا', 'تَأۡمَ۫نَّا'), None, {}, {}, {}, {}),
  ('hapax-3', ((None, None), (None, None)), ('ءَاعۡجَمِیّ', 'ءَا۬عۡجَمِیّ'), None, {}, {}, {}, {}),

                                          # Beaware! we add the shadda of assim. in لَّٰكِنَّا because it will have been restored processing the previous word
  ('P-sil-1',  ((None, None), (None, None)),  (r'^((?:وَ|فَ)?أَنَا|لَّٰكِنَّا|ٱلۡرَسُولَا|ٱلۡسَبِیلَا|ٱلۡظُنُونَا)$', r'\1۠'), None, EXCLUDE_INDEXES_SIL_1, {}, {}, {}),
  ('P-sil-2', ((None, None), (None, None)), ('قَوَارِیرَا', 'قَوَارِیرَا۠'), None, {}, {}, {}, {(76,15,8)}),

  ('sakt-1',  ((None, None), (None, None)), ('ص', 'صۜ'), None, {}, {}, {}, {(2,245,14), (7,69,22)}),
  ('sakt-2',  ((None, None), (None, None)), ('ا', 'اۜ'), None, {}, {}, {}, {(18,1,15), (36,52,6)}),
  ('sakt-3',  ((None, None), (None, None)), ('ۡ', 'ۡۜ'), None, {}, {}, {}, {(69,28,4), (75,27,2), (83,14,2)}),

  ('Sil-1',  ((None, None), (None, None)),  (r'وا$', 'وا۟'), None, {}, {}, {}, {}),
  ('Sil-2',  ((None, None), (None, None)),  (r'َوۡا$', 'َوۡا۟'), None, {}, {}, {}, {}),
  ('Sil-3', ((None, None), (None, None)), ('أُولَٰىِٕك', 'أُو۟لَٰىِٕك'), None, {}, {}, {}, {}),
  ('Sil-4', ((r'و([َُ])ا', 'ٱ'), (r'و\1ا۟', None)), (None, None), None, EXCLUDE_INDEXES_SIL_5, {}, {}, {}),
  ('Sil-5', ((None, None), (None, None)), ('ؤُا', 'ؤُا۟'), None, {}, {}, {}, RESTRICT_INDEXES_SIL_6),
  ('Sil-6', ((None, None), (None, None)), ('أُو', 'أُو۟'), None, {}, {}, {}, RESTRICT_INDEXES_SIL_7),
  ('Sil-7', ((None, None), (None, None)), (r'ا(?!$)', 'ا۟'), None, {}, {}, {}, RESTRICT_INDEXES_SIL_8),
  ('Sil-8', ((None, None), (None, None)), ('إِی', 'إِی۟'), None, {}, {}, {}, RESTRICT_INDEXES_SIL_9),
  ('Sil-9', ((None, None), (None, None)), (r'ا$', 'ا۟'), None, {(76,16,1)}, {}, {}, RESTRICT_INDEXES_SIL_A),
  ('Sil-A', ((None, None), (None, None)), ('ا', 'ا۟'), None, {}, {}, {}, {(39,69,7), (89,23,1)}),
  ('Sil-B', ((None, None), (None, None)), ('قَوَارِیرَا', 'قَوَارِیرَا۟'), None, {}, {}, {}, {(76,16,1)}),
  ('Sil-C', ((None, None), (None, None)), ('بِأَیۡیدٍ', 'بِأَیۡی۟دٍ'), None, {}, {}, {}, {(51,47,3)}),
  ('Sil-D', ((None, None), (None, None)), (r'تَایۡ(ـ)?َٔسُوا', r'تَا۟یۡ\1َٔسُوا'), None, {}, {}, {}, {(12,87,8)}),
  ('Sil-E', ((None, None), (None, None)), ('لَأَاذۡبَحَنَّهُ', 'لَأَا۟ذۡبَحَنَّهُ'), None, {}, {}, {}, {(27,21,5)}),
  ('Sil-F', ((None, None), (None, None)), ('لِشَایۡءٍ', 'لِشَا۟یۡءٍ'), None, {}, {}, {}, {(18,23,3)}),
  ('Sil-G', ((None, None), (None, None)), ('یَا', 'یَا۟'), None, {}, {}, {}, {(12,87,14), (13,31,20)}),

  ('M1', (('مۡ', 'ب'), ('م', 'ب')), (None, None), None, {}, {}, {}, {}),
  ('M2', (('مۡ', 'م'), ('م', 'مّ')), (None, None), None, {}, {}, {}, {}),
  ('N2.1.1.A', ((r'نۡ', r'([نم])'), (r'ن', r'\1ّ')), (None, None), None, {}, {}, {}, {}),
  ('N2.1.1.B', ((r'ً([ای]?)', r'([نم])'), (r'ࣰ\1', r'\1ّ')), (None, None), None, {}, {}, {}, {}),
  ('N2.1.1.C', ((r'ٌ(ا۟)?', r'([نم])'), (r'ࣱ\1', r'\1ّ')), (None, None) , None, {}, {}, {}, {}),
  ('N2.1.1.D', ((r'ٍ', r'([نم])'), (r'ࣲ', r'\1ّ')), (None, None), None, {}, {}, {}, {}),
  ('N2.1.2.A', ((r'نۡ', r'(?:[وی])'), (r'ن', None)), (None, None), None, {}, {}, {}, {}),
  ('N2.1.2.B', ((r'ً([ای]?)', r'(?:[وی])'), (r'ࣰ\1', None)), (None, None), None, {}, {}, {}, {}),
  ('N2.1.2.C', ((r'ٌ', r'(?:[وی])'), (r'ࣱ', None)), (None, None), None, {}, {}, {}, {}),
  ('N2.1.2.D', ((r'ٍ', r'(?:[وی])'), (r'ࣲ', None)), (None, None), None, {}, {}, {}, {}),
  ('N2.2.A', ((r'نۡ', r'([رل])'), (r'ن', r'\1ّ')), (None, None), None, {}, {}, {}, {}),
  ('N2.2.B', ((r'ً([ای]?)', r'([رل])'), (r'ࣰ\1', r'\1ّ')), (None, None), None, {}, {}, {}, {}),
  ('N2.2.C', ((r'ٌ', r'([رل])'), (r'ࣱ', r'\1ّ')), (None, None), None, {}, {}, {}, {}),
  ('N2.2.D', ((r'ٍ', r'([رل])'), (r'ࣲ', r'\1ّ')), (None, None), None, {}, {}, {}, {}),
  ('N3.A', ((r'نۡ', r'ب'), ('نۢ', None)), (r'نۡ(?=ب)', r'نۢ'), None, {}, {}, {}, {}),
  ('N3.B', ((r'ً(ا)?', r'ب'), (r'َۢ\1', None)), (None, None), None, {}, {}, {}, {}),
  ('N3.C', ((r'ٌ', r'ب'), (r'ُۢ', None)), (None, None), None, {}, {}, {}, {}),
  ('N3.D', ((r'ٍ', r'ب'), (r'ِۭ', None)), (None, None), None, {}, {}, {}, {}),
  ('N4.A', ((r'نۡ', rf'(?=[{IKHFA2}])'), (r'ن', None)), (rf'نۡ(?=[{IKHFA2}])', r'ن'), None, {}, {}, {}, {}),
  ('N4.B', ((rf'ً([ای])?', rf'(?=[{IKHFA2}])'), (r'ࣰ\1', None)),  (None, None), None, {}, {}, {}, {}),
  ('N4.C', ((rf'ٌ', rf'(?=[{IKHFA2}])'), (r'ࣱ', None)),  (None, None), None, {}, {}, {}, {}),
  ('N4.D', ((rf'ٍ', rf'(?=[{IKHFA2}])'), (r'ࣲ', None)),  (None, None), None, {}, {}, {}, {}),
  
  ('SHMS',  ((None, None), (None, None)),  (r'(ٱ|لّ?ِ|وَلَ|ءَا)لۡ([طثصرتضذندسظزشل])', r'\1ل\2ّ'), 'N', {}, {}, {}, {}),

  ('MITHL-bb', (('بۡ', 'ب'), ('ب', 'بّ')),  (None, None), None, {}, {}, {}, {}),
  ('MITHL-dd', (('دۡ', 'د'), ('د', 'دّ')),  ('دۡد', 'ددّ'), None, {}, {}, {}, {}),
  ('MITHL-kk', (('كۡ', 'ك'), ('ك', 'كّ')),  ('كۡك', 'ككّ'), None, {}, {}, {}, {}),
  ('MITHL-ll', (('لۡ', 'ل'), ('ل', 'لّ')),  ('لۡل', 'للّ'), None, {}, {}, {}, {}),
  ('MITHL-yy', ((None, None), (None, None)),  ('یۡی', 'ییّ'), None, MITHL_yy_EXCLUDE_INDEXES, {}, {}, {}),
  ('MITHL-hh', ((None, None), (None, None)),  ('هۡه', 'ههّ'), None, {}, {}, {}, {}),
  ('MITHL-ww', ((r'وۡ(ا۟)?', 'و'), (r'و\1', 'وّ')),  (None, None), None, {}, {}, {}, {}),
  ('MITHL-tt', (('تۡ', 'ت'), ('ت', 'تّ')),  (None, None), None, {}, {}, {}, {}),
  ('MITHL-rr', (('رۡ', 'ر'), ('ر', 'رّ')),  (None, None), None, {}, {}, {}, {}),
  ('MITHL-ðð', (('ذۡ', 'ذ'), ('ذ', 'ذّ')),  (None, None), None, {}, {}, {}, {}),
  ('MITHL-ff', (('فۡ', 'ف'), ('ف', 'فّ')),  (None, None), None, {}, {}, {}, {}),
  ('MITHL-33', (('عۡ', 'ع'), ('ع', 'عّ')),  (None, None), None, {}, {}, {}, {}),

  ('MTJNS-dt', (('دۡ', 'ت'), ('د', 'تّ')),  ('دۡت', 'دتّ'), None, {}, {}, {}, {}),
  ('MTJNS-td', (('تۡ', 'د'), ('ت', 'دّ')),  (None, None), None, {}, {}, {}, {}),
  ('MTJNS-tT', (('تۡ', 'ط'), ('ت', 'طّ')),  (None, None), None, {}, {}, {}, {}),
  ('MTJNS-ṯð', (('ثۡ', 'ذ'), ('ث', 'ذّ')),  (None, None), None, {}, {}, {}, {}),
  ('MTJNS-lr', (('لۡ', 'ر'), ('ل', 'رّ')),  ('لۡر', 'لرّ'), None, {}, {}, {}, {}),
  ('MTJNS-ðṮ', (('ذۡ', 'ظ'), ('ذ', 'ظّ')),  (None, None), None, {}, {}, {}, {}),
  ('MTJNS-qk', ((None, None), (None, None)),  ('قۡك', 'قكّ'), None, {}, {}, {}, {}),
  ('MTJNS-bm', (('بۡ', 'م'), ('ب', 'مّ')),  (None, None), None, {}, {}, {}, {}),

  ('t-assim', ((None, None), (None, None)),  ('طۡت', 'طت'), None, {}, {}, {}, {}),

  ('HU',  ((r'(?<=[َُِ])هُ', r'[^ٱ]'), ('هُۥ', None)), (None, None), None, {(39,7,13)}, {}, {}, {}),

  ('min-u-1',  ((None, None), (None, None)), ('دَاوُد', 'دَاوُۥد'), None, {}, {}, {}, {}),
  ('min-u-2',  ((None, None), (None, None)), (r'([یت])َلۡوُنَ', r'\1َلۡوُۥنَ'), None, {}, {}, {}, {}),
  ('min-u-3',  ((None, None), (None, None)), ('وُرِیَ', 'وُۥرِیَ'), None, {}, {}, {}, {}),
  ('min-u-4',  ((None, None), (None, None)), (r'(لِت|ی)َسۡتَوُ(ا۟|نَ)', r'\1َسۡتَوُۥ\2'), None, {}, {}, {}, {}),
  ('min-u-5',  ((None, None), (None, None)), (r'(وَ)?ٱلۡغَاوُنَ', r'\1ٱلۡغَاوُۥنَ'), None, {}, {}, {}, {}),
  ('min-u-6',  ((None, None), (None, None)), ('ٱلۡمَوۡءُدَةُ', 'ٱلۡمَوۡءُۥدَةُ'), None, {}, {}, {}, {}),
  ('min-u-7',  ((None, None), (None, None)), ('وُ', 'وُۥ'), None, {}, {}, {}, RESTRICT_INDEXES_MIN_U_7),
  ('min-u-8',  ((None, None), (None, None)), (r'لِیَسُ(ـ)?ُٔوا', r'لِیَسُۥ\1ُٔوا'), None, {}, {}, {}, {(17,7,12)}),

  ('HI',  ((r'(?<=[َُِ])هِ', '[^ٱ]'), ('هِۦ', None)), (None, None), None, {}, {}, {}, {}),

  ('min-y-1',  ((None, None), (None, None)), ('إِبۡرَٰهِم', 'إِبۡرَٰهِۧم'), None, {}, {}, {}, {}),
  ('min-y-2',  ((None, None), (None, None)), ('نَّبِیِّ', 'نَّبِیِّۧ'), None, EXCLUDE_INDEXES_MIN_Y_2, {}, {}, {}),
  ('min-y-3',  ((r'^یُحۡیِ$', r'[^ٱ]'), ('یُحۡیِۦ', None)), (None, None), None, {}, {}, {}, {}),
  ('min-y-4',  ((None, None), (None, None)), (r'(.)$', r'\1ۦ'), None, {}, {}, {}, RESTRICT_INDEXES_MIN_Y_4),
  ('min-y-5',  ((None, None), (None, None)), (r'ِنَ$', 'ِۧنَ'), None, {}, {}, {}, RESTRICT_INDEXES_MIN_5),
  ('min-y-6',  ((None, None), (None, None)), ('ءَاتَىٰنِ', 'ءَاتَىٰنِۦ'), None, {}, {}, {}, {(27,36,8)}),
  ('min-y-7',  ((None, None), (None, None)), ('إِلَٰفِهِمۡ', 'إِۧلَٰفِهِمۡ'), None, {}, {}, {}, {(106,2,1)}),
  ('min-y-8',  ((None, None), (None, None)), ('حِۡی', 'حِۡۧی'), None, {}, {}, {}, {(25,49,1), (46,33,15), (75,40,6)}),
  ('min-y-9',  ((None, None), (None, None)), ('وَلِِّی', 'وَلِِّۧی'), None, {}, {}, {}, {(7,196,2)}),
  ('min-y-A',  ((None, None), (None, None)), ('یَسۡتَحۡیِ', 'یَسۡتَحۡیِۦ'), None, {}, {}, {}, {(2,26,5)}),

  ('MADD-hmz',  ((r'(َا|َیٰ|ُ[وۥ]|ِ[یۦ])', fr'(?:[{HAMZA}]|[ىی]ٕ|ٔ)'), (r'\1ٓ', None)),  (fr'(َ[اٰ]|ُ[وۥ]|ِ[یۦ])(?=ـ?(?:[{HAMZA}]|[ىی]ٕ|ٔ))', r'\1ٓ'), None, MADD_HMZ_EXCEPTION, {}, {}, {}),
  ('MADD-hmz-A-sil',  ((r'ُوا۟', fr'(?:[{HAMZA}]|[ىی]ٕ)'), (r'ُوٓا۟', None)), (None, None), None, {}, {}, {}, {}),
  ('MADD-hmz-sp-1',  ((None, None), (None, None)), ('تَلۡوُۥا۟', 'تَلۡوُۥٓا۟'), None, {}, {}, {}, {}),
  ('MADD-hmz-sp-2',  ((None, None), (None, None)), ('فَأۡوُۥا۟', 'فَأۡوُۥٓا۟'), None, {}, {}, {}, {}),
  ('MADD-hmz-sp-3',  ((None, None), (None, None)), ('وَجِا۟یءَ', 'وَجِا۟یٓءَ'), None, {}, {}, {}, {}),
  ('MADD-hmz-sp-4',  (('ٱلرِّبَوٰا۟', fr'[{HAMZA}]'), ('ٱلرِّبَوٰٓا۟', None)), (None, None), None, {}, {}, {}, {}), # Q.2:278:10 ; Q.3:130:6
  # add the maddda only if the next word start with hamza: Q.2:275:3 ; Q.2:275:20 ; Q.2:275:25 ; Q.2:276:3 ; Q.4:161:2

  ('MADD-lzm',  ((None, None), (None, None)),  (fr'(َ[اٰ]|ُو|ِی)(?=[{CONS}](?:[ّْ]|[{CONS}]))', r'\1ٓ'), None, {}, {}, {}, {}),
  ('MADD-shdd-skn', ((None, None), (None, None)), (fr'َا([{CONS}])(?=[ّۡ])', r'َآ\1'), None, {}, {}, {}, {}),
  ('MADD-sp-1', ((None, None), (None, None)), (r'^الم$', 'الٓمٓ'), None, {}, {}, {}, {}),
  ('MADD-sp-2', ((None, None), (None, None)), (r'^طسم$', 'طسٓمٓ'), None, {}, {}, {}, {}),
  ('MADD-sp-3', ((None, None), (None, None)), (r'^طس$', 'طسٓ'), None, {}, {}, {}, {}),
  ('MADD-sp-4', ((None, None), (None, None)), (r'^یس$', 'یسٓ'), None, {}, {}, {}, {}),
  ('MADD-sp-5', ((None, None), (None, None)), (r'^حم$', 'حمٓ'), None, {}, {}, {}, {}),
  ('MADD-sp-6', ((None, None), (None, None)), (r'^كهیعص$', 'كٓهیعٓصٓ'), None, {}, {}, {}, {}),
  ('MADD-sp-7', ((None, None), (None, None)), (r'^الر$', 'الٓر'), None, {}, {}, {}, {}),
  ('MADD-sp-8', ((None, None), (None, None)), (r'^المص$', 'الٓمٓصٓ'), None, {}, {}, {}, {}),
  ('MADD-sp-9', ((None, None), (None, None)), (r'^المر$', 'الٓمٓر'), None, {}, {}, {}, {}),
  ('MADD-sp-A', ((None, None), (None, None)), (r'^ص$', 'صٓ'), None, {}, {}, {}, {}),
  ('MADD-sp-B', ((None, None), (None, None)), (r'^عسق$', 'عٓسٓقٓ'), None, {}, {}, {}, {}),
  ('MADD-sp-C', ((None, None), (None, None)), (r'^ق$', 'قٓ'), None, {}, {}, {}, {}),
  ('MADD-sp-D', ((None, None), (None, None)), (r'^ن$', 'نٓ'), None, {}, {}, {}, {}),
]

# indexes of special words that do not have harakat nor sukun even after removing tajweed and
# consequently are excluded for that checking
EXCEPTIONS_SUKUN = {(2,1,5), (3,1,5), (29,1,5), (30,1,5), (31,1,5), (32,1,5), # الٓمٓ
                    (26,1,5), (28,1,5), # طسٓمٓ
                    (27,1,5), # طسٓ
                    (36,1,5), # یسٓ
                    (40,1,5), (41,1,5), (42,1,5), (43,1,5), (44,1,5), (45,1,5), (46,1,5), # حمٓ
                    (40,1,5), (41,1,5), (42,1,5), (43,1,5), (44,1,5), (45,1,5), (46,1,5), # حمٓ
                    (19,1,5), # كٓهیعٓصٓ
                    (42,2,1), # عٓسٓقٓ
                    (10,1,5), (11,1,5), (12,1,5), (14,1,5), (15,1,5), # الٓر
                    (7,1,5), # الٓمٓصٓ
                    (13,1,5), # الٓمٓر
                    (38,1,5), # صٓ
                    (50,1,5), # قٓ
                    (68,1,5), # نٓ
                    (20,1,5), # طه
                    (39,69,7), (89,23,1),  # وَجِا۟یءَ Q.39:69:7 ; وَجِا۟یءَ Q.89:23:1
                    (51,47,3)  # بِأَیۡی۟دࣲ Q.51:47:3
}

def preproc(s):
    """remove quranic punctuation (U+06d6 - U+06db)

    Args:
        s(str): quranic text.
    Return:
        str: preprocessed quranic text.

    """
    return QSTOPS_REGEX.sub('', s)

def _qmorf_process():
    """ create json file containing all quran indexes and their token plus corresponding POS(s), LEMA(s) and derivational information.

      {(s, v, w) : {'tok': tok,
                    'pos': [POS, ...],
                    'lemas': [lema, ...],
                    'roots': [root, ...],
                    'derv': [derv, ...]},
       ...}

    """
    # we keep 3 main POS, N(oun), V(erb), P(article)
    POS_MAPPING = {p:POS for POS,pos in (
        ('N', {'PN', 'ADJ', 'LOC', 'DEM', 'EMPH', 'IMPV', 'PRP'}),
        ('P', {'IMPN', 'PRON', 'REL', 'T', 'CONJ' 'SUB', 'ACC', 'AMD', 'ANS', 'AVR', 'CAUS', 'CERT',
               'CIRC', 'COM', 'COND', 'EQ', 'EXH', 'EXL', 'EXP', 'FUT', 'INC', 'INT', 'INTG', 'NEG', 'PREV', 'PRO',
               'REM', 'RES', 'RET', 'RSLT', 'SUP', 'SUR', 'VOC', 'INL'})
    ) for p in pos}

    with open(QDT_FNAME) as infp, \
         open(QMORF_FNAME, 'w') as outfp:

        dt_quran = json.load(infp)

        qmorf = {}
        for item in dt_quran:

            ind = f'{item["sura"]},{item["vers"]},{item["word"]}'

            # unique list of normalised POS (i.e. only N, V or P metaclasses), keeping the order
            POS_list = tuple(dict.fromkeys([POS_MAPPING.get(morf['POS'], morf['POS']) for morf in item['morf']]))

            qmorf[ind] = {'tok': preproc(item['tok']),
                          'pos': POS_list,
                          'lemas': list(filter(None, (m['lema'] for m in item['morf']))),
                          'roots': list(filter(None, (m['root'] for m in item['morf']))),
                          'derv': list(filter(None, (m['derv'] for m in item['morf'])))}

        json.dump(qmorf, outfp)

def apply_rules(tokens, rules, qmorf, counts=None, debug=False):
    """ Remove or add the orthographic phonetic layer to the quranic text.

    Args:
        tokens_ (list): sequence of quranic token, index pairs.
        rules (iterator): rules to apply to text.
        qpos (dict): sequence of quranic type, list of normalised POS pairs.
            Possible POS are N(oun), V(erb) or P(artible).
        counts (dict): structure containing in which indexes a rule has been applied and how many times
            and if it is applied at word boundary.
                id_rule: [((s,v,w), count, is_boundary), ...]
        debug (bool): debug mode.

    """
    ntokens = len(tokens)

    for i in range(ntokens):

        wordform_rasm = next(rasm(io.StringIO(tokens[i][0])))[-1]

        for id_rule, ((tok_pre, tok_post), (repl_pre, repl_post)), (pat, repl), \
            FILTER_POS, except_ind, except_lemas, force_ind, restrict_ind in rules:

            ind = tokens[i][1][0], tokens[i][1][1], tokens[i][1][2]
            ind_key = ','.join(map(str,ind))

            if restrict_ind and ind not in restrict_ind:
                continue

            if ind in except_ind:
                continue

            if FILTER_POS and FILTER_POS not in qmorf[ind_key]['pos']:
                continue


            if ind not in force_ind and id_rule in ('HU', 'HI'):

                # madd rule for enclitic -h should not be applied to final -h belonging to lemma
                if qmorf[ind_key]['roots'] and any(r[-1]=='ه' for r in qmorf[ind_key]['roots']) and wordform_rasm[-2:] != 'هه':
                    if ind == (2,237,21): print('diff 1', qmorf[ind_key], wordform_rasm) #FIXME
                    continue
            
                # e.g. 19:46:9  تَنتَهِ pos=V  lemas=ٱنتَهَىٰ  root=نهي  derv=['IMPF', '(VIII)'] 
                if any(r[-2:]=='هي' for r in qmorf[ind_key]['roots']) and wordform_rasm[-2:] != 'هه':
                    if ind == (2,237,21): print('diff 2', qmorf[ind_key], wordform_rasm) #FIXME
                    continue

            # rule between word boundary
            if tok_pre and i<ntokens-1 and re.search(f'{tok_pre}$', tokens[i][0]) and re.search(f'^{tok_post}', tokens[i+1][0]):

                cur_tok_modif, cnt = re.subn(f'{tok_pre}$', repl_pre, tokens[i][0])

                if counts != None and cnt:
                    if id_rule in counts:
                        counts[id_rule].append((tokens[i][1], cnt, True))
                    else:
                        counts[id_rule] = [(tokens[i][1], cnt, True)]

                # the next word may have a change or not, depending on the rule
                if not repl_post:

                    if cnt and debug:
                        print(f'[[DEBUG::BND.1]] id_rule={id_rule} {tokens[i][1]} ori={tokens[i][0]} (next={tokens[i+1][0]}) '
                              f'new={cur_tok_modif} cnt={cnt} filter={FILTER_POS}', file=sys.stderr) #TRACE

                else:
                    next_tok_modif = re.sub(f'^{tok_post}', repl_post, tokens[i+1][0])
                    
                    if cnt and debug:
                        print(f'[[DEBUG::BND.2]] id_rule={id_rule} {tokens[i][1]} ori={tokens[i][0]} (next={tokens[i+1][0]}) '
                              f'new={cur_tok_modif} (next={next_tok_modif}) cnt={cnt} filter={FILTER_POS}', file=sys.stderr) #TRACE

                    tokens[i+1][0] = next_tok_modif

                tokens[i][0] = cur_tok_modif

            # rule inside a word
            if pat:

                cur_tok_modif, cnt = re.subn(pat, repl, tokens[i][0])

                if cnt and debug:
                    print(f'[[DEBUG::INSID]] id_rule={id_rule} {tokens[i][1]} ori={tokens[i][0]} new={cur_tok_modif} cnt={cnt} filter={FILTER_POS}', file=sys.stderr) #TRACE
                tokens[i][0] = cur_tok_modif

                if counts != None and cnt:
                    if id_rule in counts:
                        counts[id_rule].append((tokens[i][1], cnt, False))
                    else:
                        counts[id_rule] = [(tokens[i][1], cnt, False)]


if __name__ == '__main__':

    parser = ArgumentParser(description='add or remove tajweed phonetic layer to orthography in Quranic text')
    option = parser.add_mutually_exclusive_group(required=True)
    option.add_argument('--rm', action='store_true', help='remove tajweed layer')
    option.add_argument('--add', action='store_true', help='add tajweed layer')
    option.add_argument('--eval', action='store_true', help='remove and add tajweed layer and verify text match (verbose by default)')
    parser.add_argument('--infile', type=FileType('r'), help='read text from file instead of using `rasm` module')
    parser.add_argument('outfile', nargs='?', type=FileType('w'), default=sys.stdout, help='output stream')
    parser.add_argument('--force_qmorf', action='store_true', help='force generation of quran POS file and lemas file')
    parser.add_argument('--restrict', metavar='s[:v]', type=lambda x: list(map(int, x.split(':',1))) if ':' in x else [int(x), None],
                                      help='restrict to specific Quranic sura `s` or verse `s:v`')
    parser.add_argument('--json', action='store_true', help='print output in json (for --rm/--add)')
    parser.add_argument('--save_counts', metavar='FILE', dest='countsfp', type=FileType('w'), help='save counts of rules in json file (for --eval)')
    parser.add_argument('--debug', action='store_true', help='show debugging info')

    args = parser.parse_args()

    #
    # prepare list of quranic types associated to their POS and lemas
    #

    if args.force_qmorf or not os.path.exists(QMORF_FNAME):
        _qmorf_process()
    with open(QMORF_FNAME) as fp:
        QMORF = json.load(fp)

    #
    # prepare quranic data
    #

    if args.restrict:
        sura, verse = args.restrict
        qindex = ((sura, verse, None, None), 4*(None,))
    else:
        qindex = ((0, None, None, None), (114, None, None, None))

    if args.infile:
        qtokens = json.load(args.infile)
    else:
        qtokens = [[preproc(tok), ind] for tok, *_, ind in rasm(qindex, source='decotype', only_rasm=True)] #FIXME

    #
    # apply remove rules
    # 

    if args.rm:
        apply_rules(qtokens, REMOVE_SANDHI_RULES, QMORF, counts=None, debug=args.debug)
        if args.json:
            json.dump(qtokens, args.outfile)
        else:
            print(' '.join(t for t,i in qtokens), file=args.outfile)

    #
    # aply restore rules
    #

    elif args.add:
        apply_rules(qtokens, RESTORE_SANDHI_RULES, QMORF, counts=None, debug=args.debug)
        if args.json:
            json.dump(qtokens, args.outfile)
        else:
            print(' '.join(t for t,i in qtokens), file=args.outfile)

    #
    # perform evaluation: apply both remove and restore rules
    #
    
    else:
        print('>> applying remove rules...')
        counts_rm = {i[0]:[] for i in REMOVE_SANDHI_RULES}
        qtokens_detajweed = deepcopy(qtokens)
        apply_rules(qtokens_detajweed, REMOVE_SANDHI_RULES, QMORF, counts_rm, debug=args.debug)
        if args.debug:
            print('qtokens_detajweed =', ' '.join(t for t,_ in qtokens_detajweed))
        
        print('>> applying restore rules...')
        counts_add = {i[0]:[] for i in RESTORE_SANDHI_RULES}
        qtokens_restored = deepcopy(qtokens_detajweed)
        apply_rules(qtokens_restored, RESTORE_SANDHI_RULES, QMORF, counts_add, debug=args.debug)
        if args.debug:
            print('qtokens_restored =', ' '.join(t for t,_ in qtokens_restored))

        if args.countsfp:
            cnt_obj = {rule: [{'ind':i, 'cnt':c, 'bound':b} for i,c,b in ind_list] for rule, ind_list in counts_rm.items()}
            json.dump(cnt_obj, args.countsfp)

        for id_, traces_rm in counts_rm.items():
            traces_add = counts_add.get(id_, [])
            match = traces_rm == traces_add
            print(f'rule {id_}'.ljust(20),
                  f'rm applied {sum(c for _,c,_ in traces_rm):>4} times',
                  f'add {sum(c for _,c,_ in traces_add):>4} times',
                  ('- OK' if match else '- FAIL!'))

            if args.debug and not match:
                for t_rm, t_ad in zip(sorted(traces_rm, key=lambda x: x[0]), sorted(traces_add, key=lambda x: x[0])):
                    tok_rm = next(rasm(((*t_rm[0],None), 4*(None,)), source='decotype', paleo=True))[3]
                    tok_ad = next(rasm(((*t_ad[0],None), 4*(None,)), source='decotype', paleo=True))[3]
                    if t_rm != t_ad:
                        print(f'\n@debug@ FAIL!!  rule={id_} rm={str(t_rm):<20} tok={tok_rm:<20}  add={str(t_ad):<20} tok={tok_ad}', file=sys.stderr)
                    else:
                        print(f'\n@debug@   OK!!  rule={id_} rm={str(t_rm):<20} tok={tok_rm:<20}  add={str(t_ad):<20} tok={tok_ad}', file=sys.stderr)

        #
        # check original text and restored text are equal
        #

        if ' '.join(t for t,_ in qtokens) == ' '.join(t for t,_ in qtokens_restored):
            print('\n>> Original and restored qtexts match!')
        else:
            print('\n>> FAIL!! original and restored qtexts are different')
            for (word, ind), (word_rest, ind_rest) in zip(qtokens, qtokens_restored):
                if word != word_rest:
                    print(f' diff {word} {word_rest} ({":".join(map(str, ind))})')
                else:
                    print(f' oki {word} {word_rest} ({":".join(map(str, ind))})')
            sys.exit(1)

        #
        # check that there are no traces of the tajweed layer in the detajweed conversion
        #

        SUKUN_REGEX = re.compile(f'[{CONS}](?<!ُو|ِی)[{CONS}]')
        SHADDA_REGEX = re.compile(f'^[{CONS}]ّ')
        TANWIN_REGEX = re.compile(f'[ࣰࣱࣲ]|َۢ|ُۢ|ِۭ')

        cnt = 0

        #TODO compare rasm of detajweedised and tajweedised

        # if a word has several traces, show only one of them
        for tok, ind in qtokens_detajweed:
            if SUKUN_REGEX.search(tok) and ind not in EXCEPTIONS_SUKUN:
                print(f'WARNING-1! untreated tajweed traces! consonant without harakat nor sukun in {tok} Q.{":".join(map(str, ind))}')
                cnt += 1
            elif SHADDA_REGEX.search(tok):
                print(f'WARNING-2! untreated tajweed traces! shadda on initial consonant of word in {tok} Q.{":".join(map(str, ind))}')
                cnt += 1
            elif TANWIN_REGEX.search(tok):
                print(f'WARNING-3! untreated tajweed traces! tanwin with tajweed in {tok} Q.{":".join(map(str, ind))}')
                cnt += 1
            elif 'ٓ' in tok or 'آ' in tok:
                print(f'WARNING-4! untreated tajweed traces! madd sign found in {tok} Q.{":".join(map(str, ind))}')
                cnt += 1
            elif '۠' in tok:
                print(f'WARNING-5! untreated tajweed traces! mark for silent alif found in {tok} Q.{":".join(map(str, ind))}')
                cnt += 1
            elif 'ۦ' in tok or 'ۧ' in tok:
                print(f'WARNING-6! untreated tajweed traces! miniature ya found in {tok} Q.{":".join(map(str, ind))}')
                cnt += 1
            elif 'ۥ' in tok:
                print(f'WARNING-7! untreated tajweed traces! miniature waw found in {tok} Q.{":".join(map(str, ind))}')
                cnt += 1
            elif '۟' in tok:
                print(f'WARNING-8! untreated tajweed traces! mark in alif for not pronouncing found in {tok} Q.{":".join(map(str, ind))}')
                cnt += 1
            elif '۪' in tok:
                print(f'WARNING-9! untreated tajweed traces! hapax sign U+06ea found in {tok} Q.{":".join(map(str, ind))}')
                cnt += 1
            elif '۫' in tok:
                print(f'WARNING-A! untreated tajweed traces! hapax sign U+06eb found in {tok} Q.{":".join(map(str, ind))}')
                cnt += 1
            elif '۬' in tok:
                print(f'WARNING-B! untreated tajweed traces! hapax sign U+06ec found in {tok} Q.{":".join(map(str, ind))}')
                cnt += 1
            elif 'ۢ' in tok:
                print(f'WARNING-C! untreated tajweed traces! miniature mim U+06e2 found in {tok} Q.{":".join(map(str, ind))}')
                cnt += 1
            elif 'ۜ' in tok:
                print(f'WARNING-C! untreated tajweed traces! miniature sin U+06dc found in {tok} Q.{":".join(map(str, ind))}')
                cnt += 1

        print(f'Total {cnt} warnings')
