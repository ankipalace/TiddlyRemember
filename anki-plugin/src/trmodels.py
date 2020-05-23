from abc import ABC
import inspect
from textwrap import dedent
from typing import Dict, Iterable, List, Optional, Tuple, Type, Union
import sys

import aqt
from anki.consts import MODEL_CLOZE


class TemplateData(ABC):
    """
    Self-constructing definition for templates.
    """
    name: str
    front: str
    back: str

    @classmethod
    def to_template(cls):
        "Create and return an Anki template object for this model definition."
        mm = aqt.mw.col.models
        t = mm.newTemplate(cls.name)
        t['qfmt'] = dedent(cls.front).strip()
        t['afmt'] = dedent(cls.back).strip()
        return t


class ModelData(ABC):
    """
    Self-constructing definition for models.
    """
    name: str
    fields: Tuple[str, ...]
    templates: Tuple[Type[TemplateData]]
    styling: str
    sort_field: str
    is_cloze: bool

    @classmethod
    def to_model(cls):
        "Create and return an Anki model object for this model definition."
        mm = aqt.mw.col.models
        model = mm.new(cls.name)
        for i in cls.fields:
            field = mm.newField(i)
            mm.addField(model, field)
        for template in cls.templates:
            t = template.to_template()
            mm.addTemplate(model, t)
        model['css'] = dedent(cls.styling).strip()
        model['sortf'] = cls.fields.index(cls.sort_field)
        if cls.is_cloze:
            model['type'] = MODEL_CLOZE
        return model

    @classmethod
    def in_collection(cls):
        """
        Determine if a model by this name exists already in the current
        Anki collection.
        """
        mm = aqt.mw.col.models
        model = mm.byName(cls.name)
        return model is not None

    @classmethod
    def field_remap(cls, other: 'Type[ModelData]') -> Dict[int, Optional[int]]:
        """
        Produce a field mapping to be used to change a note of this note type
        to that of the /other/ note type. Fields are mapped by index, the old
        note type's index to the new type's index.

        If a field with exactly the same name is found, that is assumed to be
        the correct mapping; otherwise, the check is delegated to the
        other.field_index() class method, which returns None by default
        (simply discard this field). This method can be overridden to support
        maintaining information from certain other note types or fields; for
        TiddlyRemember's purposes right now, we simply let the fields be
        discarded since after changing the note type we will do a
        unidirectional sync that will repopulate them anyway.
        """
        mapping: Dict[int, Optional[int]] = {}
        for idx, field in enumerate(cls.fields):
            try:
                mapping[idx] = other.fields.index(field)
            except ValueError:
                mapping[idx] = other.field_index(cls, field)
        return mapping

    @classmethod
    def field_index(cls, from_type: 'Type[ModelData]',
                    from_field_name: str) -> Optional[int]:
        """
        Return the index of the field in *this* note type that the field
        from_field_name in the note type from_type maps onto, or None if the content
        should be discarded.
        """
        return None


class TiddlyRememberQuestionAnswer(ModelData):
    class TiddlyRememberQuestionAnswerTemplate(TemplateData):
        name = "Forward"
        front = """
            {{Question}}
        """
        back = """
            {{FrontSide}}

            <hr id=answer>

            {{Answer}}

            <div class="note-id">
                {{#Permalink}}
                    [<a href="{{text:Permalink}}">{{Wiki}}/{{Reference}}</a> {{ID}}]
                {{/Permalink}}
                {{^Permalink}}
                    [{{Wiki}}/{{Reference}} {{ID}}]
                {{/Permalink}}
            </div>
        """

    name = "TiddlyRemember Q&A v1"
    fields = ("Question", "Answer", "ID", "Wiki", "Reference", "Permalink")
    templates = (TiddlyRememberQuestionAnswerTemplate,)
    styling = """
        .card {
            font-family: arial;
            font-size: 20px;
            text-align: center;
            color: black;
            background-color: white;
        }

        .note-id {
            font-size: 70%;
            margin-top: 1ex;
            text-align: right;
            color: grey;
        }

        .note-id a {
            color: grey;
        }
    """
    sort_field = "Question"
    is_cloze = False


class TiddlyRememberCloze(ModelData):
    class TiddlyRememberClozeTemplate(TemplateData):
        name = "Cloze"
        front = """
            {{cloze:Text}}
        """
        back = """
            {{cloze:Text}}

            <div class="note-id">
                {{#Permalink}}
                    [<a href="{{text:Permalink}}">{{Wiki}}/{{Reference}}</a> {{ID}}]
                {{/Permalink}}
                {{^Permalink}}
                    [{{Wiki}}/{{Reference}} {{ID}}]
                {{/Permalink}}
            </div>
        """

    name = "TiddlyRemember Cloze v1"
    fields = ("Text", "ID", "Wiki", "Reference", "Permalink")
    templates = (TiddlyRememberClozeTemplate,)
    styling = """
        .card {
            font-family: arial;
            font-size: 20px;
            text-align: center;
            color: black;
            background-color: white;
        }

        .cloze {
            font-weight: bold;
            color: blue;
        }

        .nightMode .cloze {
            filter: invert(85%);
        }

        .note-id {
            font-size: 70%;
            margin-top: 1ex;
            text-align: right;
            color: grey;
        }

        .note-id a {
            color: grey;
        }
    """
    sort_field = "Text"
    is_cloze = True


def _itermodels() -> Iterable[Type[ModelData]]:
    "Iterable over the set of all model definitions in this file."
    def is_model(obj):
        return (inspect.isclass(obj)
                and any('ModelData' == b.__name__ for b in obj.__bases__))
    return (i for _, i in inspect.getmembers(sys.modules[__name__], is_model))


def ensure_note_types():
    """
    For all note types defined in this file, add them to the collection if
    they aren't in there already.
    """
    for model in _itermodels():
        if not model.in_collection():
            aqt.mw.col.models.add(model.to_model())


def all_note_types() -> List[Type[ModelData]]:
    """
    Return a list of all note types defined in this file.
    """
    return list(_itermodels())


def by_name(model_name: str) -> Optional[Type[ModelData]]:
    """
    Return a note type defined in this file by its name, or None if no such note
    type exists.
    """
    try:
        return next(i for i in all_note_types() if i.name == model_name)
    except StopIteration:
        return None
