#!/usr/bin/env python3
#
#    build_html.py
#
# create static html with the output data
#
# usage:
#   $ python3 build_html.py data/tajweed_groups_30.csv site
#
############################################################

import os
import glob
import pandas as pd
from typing import IO
from pathlib import Path
from functools import partial
from argparse import ArgumentParser


MYPATH = Path(__file__).resolve().parent
INDEX_FILE = MYPATH / "index.html"


CSS = """
<style>
    body {
        body {
            font-family: 'Lora', serif;
    }
</style>
"""

HEADER = """
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" crossorigin="anonymous">
    <link href="https://fonts.googleapis.com/css2?family=Lora:wght@400;700&display=swap" rel="stylesheet">
    {css}
</head>
"""


HTML = """
<!DOCTYPE html>
<html lang="en">
{header}
<body>
    <nav class="navbar navbar-expand-lg navbar-light bg-light">
        <div class="container-fluid">
            <a class="navbar-brand" href="{index}">TAJWEED RULES</a>
            <div class="collapse navbar-collapse">
                <ul class="navbar-nav nav-pills">
                    {menu}
                </ul>
            </div>
        </div>
    </nav>
    <div class="container my-2">
        <h3 class="text-center mb-4">{title}</h3>
        <p>{description}</p>
        <table class="table table-bordered table-striped">
            <thead class="table-dark">
                {columns}
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    </div>
    <footer class="bg-light text-center text-lg-start">
        <div class="text-center p-3">
            &copy; 2024 Alicia González Martínez
        </div>
    </footer>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js" integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz" crossorigin="anonymous"></script>
    </script>
</body>
</html>
"""


TAB = """
<li class="nav-item">
    <a class="nav-link {active}" href="{link}">{tab}</a>
</li>
"""

RULES_DESC = {
    "ALL":          "Counts of tajwīd orthographic rules shown in groups of every 30 words",
    "ASSIM-M_B":    "Assimilation rules for al-mīm al-sākinah in word-boundary position",
    "ASSIM-N_B":    "Assimilation rules for al-nūn al-sākinah in word-boundary position",
    "ASSIM-N_I":    "Assimilation rules for al-nūn al-sākinah in word-internal position",
    "ASSIM_B":      "Assimilation rules other than al-mīm or al-nūn al-sākinah in word-bundary position",
    "ASSIM_I":      "Assimilation rules other than al-mīm or al-nūn al-sākinah in word-internal position",
    "MADDA_B":      "Elongation rules of long vowels in word-boundary position",
    "MADDA_I":      "Elongation rules of long vowels in word-internal position",
    "SHAMS_I":      "Assimilation rule of al-lām al-sākinah",
    "CLIT-H_B":     "Elongation rule on third-person clitic",
    "MIN-W_I":      "Elongation rule with miniature wāw in word-internal position",
    "MIN-Y_B":      "Elongation rule with miniature yā in word-boundary position",
    "MIN-Y_I":      "Elongation rule with miniature yā in word-internal position",
    "P_SIL_I":      "Pausal mark rule al-ṣifr al-mustaṭīl al-qāʾim in word-internal position (pronounced in pause but not in consecutive reading)",
    "SIL_B":        "Pausal mark rule al-ṣifr al-mustadīr in word-boundary position (should not be pronounced either in connection nor pause)",
    "SIL_I":        "Pausal mark rule al-ṣifr al-mustadīr in word-internal position (should not be pronounced either in connection nor pause)",
    "SAKT_I":       "Pausal mark rules indicated with miniature sīn in word-internal position"
}


def get_columns(df: pd.DataFrame, bold_pos: int = -1) -> str:
    """ create columns for html tables from df
    """
    return "<tr>" + "\n".join(f"<th>{f"<b>{col}</b>" if i == bold_pos else col}</th>"
           for i, col in enumerate(df.columns)) + "</tr>"


def get_rows(df: pd.DataFrame, bold_pos: int = -1) -> str:
    """ create rows for html tables from df
    """
    return "\n".join("<tr>" + "".join(f"<td>{f'<b>{val}</b>' if bold_pos == i else val}</td>"
            for i, val in enumerate(row.tolist())) + "</tr>"
            for _, row in df.iterrows())


def create_page(
        df: pd.DataFrame,
        desc: str,
        ibold: int,
        out: IO[str],
        title: str,
        menu: str
    ):
    """ convert df into html and save it in output
    """
    html = HTML.format(
        header=HEADER.format(title=title, css=CSS),
        index="#" if ibold == -1 else "../index.html",
        menu=menu,
        title=title,
        description="" if desc is None else desc,
        columns=get_columns(df, bold_pos=ibold),
        rows=get_rows(df, bold_pos=ibold)
    )
    out.write(html)


def create_menu(tabs_links: list[tuple[str, str]], ibold: int = -1) -> str:
    """ create the top menu with the links to all rules
    """
    return "\n".join(TAB.format(
        active="active bg-secondary text-white" if i == ibold-1 else "",
        link=link,
        tab=tab
        ) for i, (tab, link) in enumerate(tabs_links))


if __name__ == "__main__":

    parser = ArgumentParser(
        description="create static html with the output data")
    parser.add_argument(
        "input",
        help="data in csv format")
    parser.add_argument(
        "out",
        help="output folder")
    args = parser.parse_args()

    site_path = str(MYPATH / f"{args.out}/*")
    print(f"Remove previous contents of output dir {site_path}")
    for f in glob.glob(site_path):
        os.remove(f)

    df = pd.read_csv(args.input)

    df.qindex = df.qindex.apply(lambda x: f"Q{x}")
    df.rename(columns={"qindex": "Quran Index"}, inplace=True)

    # reorder columns
    df = df[list(RULES_DESC.keys())[1:]]

    files = enumerate(df.columns)

    # skip qindex column
    next(files)

    files = [(i, col, f"{i}.html") for i, col in files]

    print(f"Create html page {INDEX_FILE}")
    with open(INDEX_FILE, "w") as outfp:
        create_page(
            df=df,
            desc=RULES_DESC["ALL"],
            ibold=-1,
            out=outfp,
            title="All Rules",
            menu=create_menu(
                tabs_links=[
                    (col, Path(args.out) / file_path) for i, col, file_path in files
                ]
            )
        )
    
    create_menu = partial(
        create_menu,
        tabs_links=[(col, file_path) for i, col, file_path in files]
    )

    for i, col, file_name in files:
        
        filtered_df = df[df[col] != 0]
        bold_pos = filtered_df.columns.get_loc(col)

        outpath = MYPATH / args.out / file_name

        print(f"Create html page {outpath}")
        with open(outpath, "w") as outfp:
            create_page(
                df=filtered_df,
                desc=RULES_DESC[col],
                ibold=i,
                out=outfp,
                title=f"Rule {col}",
                menu=create_menu(ibold=i)
        )

