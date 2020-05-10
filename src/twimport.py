#!/usr/bin/env python3

from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from typing import Callable, Iterable, Optional, Set, Sequence

from bs4 import BeautifulSoup

from twnote import TwNote

RENDERED_FILE_EXTENSION = "html"


def render_wiki(tw_binary: str, wiki_path: str, output_directory: str, filter_: str) -> None:
    """
    Request that TiddlyWiki render the specified tiddlers as html to a
    location where we can inspect them for notes.

    :param tw_binary: Path to the TiddlyWiki node executable.
    :param wiki_path: Path of the wiki folder to render.
    :param output_directory: Directory to render html files into.
    :param filter_: TiddlyWiki filter describing which tiddlers we want
                    to search for notes.
    """
    cmd = [
        tw_binary,
        "--output",
        output_directory,
        "--render",
        filter_,
        f"[is[tiddler]addsuffix[.{RENDERED_FILE_EXTENSION}]]",
        "text/html",
        "$:/sib/macros/remember"]

    #TODO: Error handling
    subprocess.call(cmd, cwd=wiki_path)


def notes_from_tiddler(tiddler: str, name: str) -> Set[TwNote]:
    """
    Given the text of a tiddler, parse the contents and return a set
    containing all the TwNotes found within that tiddler.

    :param tiddler: The rendered text of a tiddler as a string.
    :param name: The name of the tiddler, for traceability purposes.
    :return: A (possibly empty) set of all the notes found in this tiddler.
    """
    notes = set()
    soup = BeautifulSoup(tiddler, 'html.parser')
    pairs = soup.find_all("div", class_="rememberq")
    for pair in pairs:
        question = pair.find("div", class_="rquestion").p.get_text()
        answer = pair.find("div", class_="ranswer").p.get_text()
        id_ = pair.find("div", class_="rid").get_text().strip().lstrip('[').rstrip(']')
        notes.add(TwNote(id_, name, question, answer))

    return notes


def notes_from_paths(
    paths: Sequence[Path],
    callback: Optional[Callable[[int, int], None]]) -> Set[TwNote]:
    """
    Given an iterable of paths, compile the notes found in all those tiddlers.

    :param paths:
    :param callback: Optional callable passing back progress. See :func:`find_notes`.
    :return: A set of all the notes found in the tiddler files passed.
    """
    notes = set()
    for index, tiddler in enumerate(paths, 0):
        with open(tiddler, 'r') as f:
            tid_text = f.read()
        tid_name = tiddler.name[:tiddler.name.find(f".{RENDERED_FILE_EXTENSION}")]
        notes.update(notes_from_tiddler(tid_text, tid_name))

        if callback is not None and not index % 50:
            callback(index+1, len(paths))

    if callback is not None:
        callback(len(paths), len(paths))
    return notes


def find_notes(tw_binary: str, wiki_path: str, filter_: str,
               callback: Optional[Callable[[int, int], None]] = None) -> Set[TwNote]:
    """
    Return a set of TwNotes parsed out of a TiddlyWiki.

    :param tw_binary: Path to the TiddlyWiki node executable.
    :param wiki_path: Path of the wiki folder to render.
    :param filter_: TiddlyWiki filter describing which tiddlers
                    to search for notes.
    :param callback: Optional callable receiving two integers, the first representing
                     the number of tiddlers processed and the second the total number.
                     It will be called every 50 tiddlers. The first call is made at
                     tiddler 1, once the wiki has been rendered.
    """
    with TemporaryDirectory() as tmpdir:
        render_wiki(tw_binary, wiki_path, tmpdir, filter_)
        notes = notes_from_paths(
            list(Path(tmpdir).glob(f"*.{RENDERED_FILE_EXTENSION}")),
            callback)

    return notes


if __name__ == '__main__':
    notes = find_notes(
        tw_binary="/home/soren/cabinet/Me/Records/zettelkasten/node_modules/.bin/tiddlywiki",
        wiki_path="/home/soren/cabinet/Me/Records/zettelkasten/zk-wiki",
        filter_="[!is[system]type[text/vnd.tiddlywiki]]",
        callback=lambda cur, tot: print(f"{cur}/{tot}"))
    print(notes)
