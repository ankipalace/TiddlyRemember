from abc import ABCMeta, abstractmethod, abstractclassmethod
from typing import Any, List, Optional, Set, Tuple
from urllib.parse import quote as urlquote

from anki.notes import Note
import aqt
from bs4 import BeautifulSoup

from .trmodels import TiddlyRememberQuestionAnswer, TiddlyRememberCloze
from .util import Twid

class TwNote(metaclass=ABCMeta):
    model: Any = None  #: The ModelData class for the Anki note generated by this type

    def __init__(self, id_: Twid, tidref: str, 
                 target_tags: Set[str], target_deck: Optional[str]) -> None:
        self.id_ = id_
        self.tidref = tidref
        self.target_tags = target_tags
        self.target_deck = target_deck
        self.permalink: Optional[str] = None

    def __eq__(self, other):
        return self.id_ == other.id_

    def __hash__(self):
        return hash(self.id_)

    @classmethod
    def notes_from_soup(cls, soup: BeautifulSoup, tiddler_name: str) -> Set['TwNote']:
        """
        Given soup for a tiddler and the tiddler's name, create notes by calling
        the wants_soup and parse_html methods of each candidate subclass.
        """
        notes: Set[TwNote] = set()
        for subclass in cls.__subclasses__():
            wanted_soup = subclass.wants_soup(soup)  # type: ignore
            if wanted_soup:
                notes.update(subclass.parse_html(soup, tiddler_name))  # type: ignore
        return notes

    def _assert_correct_model(self, anki_note: Note) -> None:
        """
        Raise an assertion error if the :attr:`anki_note` doesn't match
        the current class's model.
        """
        # pylint: disable=no-member
        model = anki_note.model()
        assert model is not None
        assert self.model is not None, \
             f"Class {self.__class__} does not specify a 'model' attribute."
        assert model['name'] == self.model.name, \
             f"Expected note of type {self.model.name}, but got {model['name']}."

    @property
    def anki_tags(self) -> List[str]:
        """
        Munge tags and return a list suitable for use in Anki.

        A quick test shows most if not all special characters are valid in tags;
        I cannot find further documentation on any issues these may cause.
        Spaces aren't, though, since tags are separated by spaces.
        """
        assert aqt.mw is not None, "Anki not initialized prior to TiddlyWiki sync!"
        # Canonify seems to be returning empty strings as part of the list,
        # perhaps due to a bug. Strip them so our equality checks don't get
        # goofed up.
        canon = aqt.mw.col.tags.canonify(
            [t.replace(' ', '_') for t in self.target_tags])
        return [i for i in canon if i.strip()]

    def fields_equal(self, anki_note: Note) -> bool:
        """
        Compare the fields on this TwNote to an Anki note. Return True if all
        are equal.
        """
        self._assert_correct_model(anki_note)
        return self._fields_equal(anki_note)

    def set_permalink(self, base_url: str) -> None:
        """
        Build and add the permalink field to this note given the base URL of
        the wiki. May be used to replace an existing permalink.
        """
        if not base_url.endswith('/'):
            base_url += '/'
        self.permalink = base_url + "#" + urlquote(self.tidref)

    def update_fields(self, anki_note: Note) -> None:
        """
        Alter the Anki note to match this TiddlyWiki note.
        """
        self._assert_correct_model(anki_note)
        self._update_fields(anki_note)


    ### Abstract methods ###
    @abstractclassmethod
    def parse_html(cls, soup: BeautifulSoup, name: str):
        """
        Given soup and the name of a tiddler, construct and return any TwNotes
        of this subclass's type that can be extracted from it.
        """
        raise NotImplementedError

    @abstractclassmethod
    def wants_soup(cls, soup: BeautifulSoup) -> bool:
        """
        Whether this subclass wants an opportunity to parse the provided
        :attr:`soup` and return TwNotes of its type through the parse_html() method;
        presumably, true if there are any notes of the provided type in the soup.
        """
        raise NotImplementedError

    @abstractmethod
    def _fields_equal(self, anki_note: Note) -> bool:
        "Check field equality for the given note type."
        raise NotImplementedError

    @abstractmethod
    def _update_fields(self, anki_note: Note) -> None:
        "Update fields for the given note type."
        raise NotImplementedError


class QuestionNote(TwNote):
    model = TiddlyRememberQuestionAnswer

    def __init__(self, id_: Twid, tidref: str, question: str, answer: str,
                 target_tags: Set[str], target_deck: Optional[str]) -> None:
        super().__init__(id_, tidref, target_tags, target_deck)
        self.question = question
        self.answer = answer

    def __repr__(self):
        return (f"TwNote(id_={self.id_!r}, tidref={self.tidref!r}, "
                f"question={self.question!r}, answer={self.answer!r}, "
                f"target_tags={self.target_tags!r}, target_deck={self.target_deck!r})")

    @classmethod
    def parse_html(cls, soup: BeautifulSoup, name: str) -> Set['QuestionNote']:
        notes = set()
        deck, tags = get_deck_and_tags(soup)

        pairs = soup.find_all("div", class_="rememberq")
        for pair in pairs:
            question = pair.find("div", class_="rquestion").p.get_text()
            answer = pair.find("div", class_="ranswer").p.get_text()
            id_raw = pair.find("div", class_="rid").get_text()
            id_ = id_raw.strip().lstrip('[').rstrip(']')
            notes.add(cls(id_, name, question, answer, tags, deck))

        return notes

    @classmethod
    def wants_soup(cls, soup: BeautifulSoup) -> bool:
        return bool(soup.find("div", class_="rememberq"))

    def _fields_equal(self, anki_note: Note) -> bool:
        return (
            self.question == anki_note.fields[0]
            and self.answer == anki_note.fields[1]
            and self.id_ == anki_note.fields[2]
            and self.tidref == anki_note.fields[3]
            and self.permalink == anki_note.fields[4]
            and self.anki_tags == anki_note.tags
        )

    def _update_fields(self, anki_note: Note) -> None:
        """
        Alter the Anki note to match this TiddlyWiki note.
        """
        anki_note.fields[0] = self.question
        anki_note.fields[1] = self.answer
        anki_note.fields[3] = self.tidref
        anki_note.fields[4] = self.permalink if self.permalink is not None else ""
        anki_note['ID'] = self.id_
        anki_note.tags = self.anki_tags


class ClozeNote(TwNote):
    model = TiddlyRememberCloze

    def __init__(self, id_: Twid, tidref: str, text: str,
                 target_tags: Set[str], target_deck: Optional[str]) -> None:
        super().__init__(id_, tidref, target_tags, target_deck)
        self.text = text

    def __repr__(self):
        return (f"TwNote(id_={self.id_!r}, tidref={self.tidref!r}, "
                f"text={self.text!r}, target_tags={self.target_tags!r}, "
                f"target_deck={self.target_deck!r})")

    @classmethod
    def parse_html(cls, soup: BeautifulSoup, name: str) -> Set['ClozeNote']:
        notes = set()
        deck, tags = get_deck_and_tags(soup)

        pairs = soup.find_all(class_="remembercz")
        for pair in pairs:
            text = pair.find("span", class_="cloze-text").get_text()
            id_raw = pair.find("div", class_="rid").get_text()
            id_ = id_raw.strip().lstrip('[').rstrip(']')
            notes.add(cls(id_, name, text, tags, deck))

        return notes

    @classmethod
    def wants_soup(cls, soup: BeautifulSoup) -> bool:
        return bool(soup.find("div", class_="remembercz"))

    def _fields_equal(self, anki_note: Note) -> bool:
        return (
            self.text == anki_note['Text']
            and self.id_ == anki_note['ID']
            and self.tidref == anki_note['Reference']
            and self.permalink == anki_note['Permalink']
            and self.anki_tags == anki_note.tags
        )

    def _update_fields(self, anki_note: Note) -> None:
        """
        Alter the Anki note to match this TiddlyWiki note.
        """
        anki_note['Text'] = self.text
        anki_note['ID'] = self.id_
        anki_note['Permalink'] = self.permalink if self.permalink is not None else ""
        anki_note['Reference'] = self.tidref
        anki_note.tags = self.anki_tags


def get_deck_and_tags(tiddler_soup: BeautifulSoup) -> Tuple[Optional[str], Set[str]]:
    """
    Given the soup of a tiddler, extract its deck and list of tags.
    """
    deckList = tiddler_soup.find("ul", id="anki-decks")
    if deckList:
        firstItem = deckList.find("li")
        deck = firstItem.get_text() if firstItem is not None else None
    else:
        deck = None

    tagList = tiddler_soup.find("ul", id="anki-tags")
    if tagList:
        tags = set(i.get_text() for i in tagList.find_all("li"))
    else:
        tags = set()

    return deck, tags
