# Copyright 2004-2025 Tom Rothamel <pytom@bishoujo.us>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from __future__ import division, absolute_import, with_statement, print_function, unicode_literals
from renpy.compat import PY2, basestring, bchr, bord, chr, open, pystr, range, round, str, tobytes, unicode  # *


import renpy

import hashlib
import re
import collections
import os
import time
import io
import codecs

################################################################################
# Script
################################################################################


class TranslateInfo(object):
    """
    This is the object that returns information about the a translation.
    """

    def __init__(self, node):
        self.language = node.language
        self.identifier = node.identifier
        self.filename = node.filename
        self.linenumber = node.linenumber

        if isinstance(node, renpy.ast.TranslateSay):
            block = [node]
        else:
            block = node.block

        self.source = []

        for i in block:
            try:
                self.source.append(i.get_code())
            except Exception as e:
                pass


class ScriptTranslator(object):
    def __init__(self):
        # All languages we know about.
        self.languages = set()

        # A map from the translate identifier to the translate object used when the
        # language is None.
        self.default_translates = {}

        # A map from (identifier, language) to the translate object used for that
        # language.
        self.language_translates = {}

        # A list of (identifier, language) tuples that we need to chain together.
        self.chain_worklist = []

        # A map from filename to a list of (label, translate) pairs found in
        # that file.
        self.file_translates = collections.defaultdict(list)

        # A map from language to the StringTranslator for that language.
        self.strings = collections.defaultdict(StringTranslator)

        # A map from language to a list of TranslateBlock objects for
        # that language.
        self.block = collections.defaultdict(list)

        # A map from language to a list of TranslateEarlyBlock objects for
        # that language.
        self.early_block = collections.defaultdict(list)

        # A map from language to a list of TranslatePython objects for
        # that language.
        self.python = collections.defaultdict(list)

        # A map from filename to a list of additional strings we've found
        # in that file.
        self.additional_strings = collections.defaultdict(list)

        # Scan for languages.

        for i in renpy.exports.list_files():
            parts = i.split("/")
            if parts[0] == "tl":
                if len(parts) >= 3 and parts[1] != "None":
                    self.languages.add(parts[1])

    def count_translates(self):
        """
        Return the number of dialogue blocks in the game.
        """

        return len(self.default_translates)

    def take_translates(self, nodes: list[renpy.ast.Node]):
        """
        Takes the translates out of the flattened list of statements, and stores
        them into the dicts above.
        """

        if not nodes:
            return

        from renpy.ast import (
            TranslatePython,
            TranslateBlock,
            TranslateEarlyBlock,
            Translate,
            TranslateSay,
        )

        filename = renpy.lexer.unelide_filename(nodes[0].filename)
        filename = os.path.normpath(os.path.abspath(filename))

        label = None

        for n in nodes:
            if not n.translation_relevant:
                continue

            if isinstance(n.name, str):
                label = n.name

            if isinstance(n, TranslatePython):
                if n.language is not None:
                    self.languages.add(n.language)
                self.python[n.language].append(n)

            elif isinstance(n, TranslateEarlyBlock):
                if n.language is not None:
                    self.languages.add(n.language)
                self.early_block[n.language].append(n)

            elif isinstance(n, TranslateBlock):
                if n.language is not None:
                    self.languages.add(n.language)
                self.block[n.language].append(n)

            elif isinstance(n, (Translate, TranslateSay)):
                if n.language is None:
                    if n.identifier in self.default_translates:
                        old_node = self.default_translates[n.identifier]

                        err = renpy.lexer.ParseError(
                            f"Line with id {n.identifier} appears twice. "
                            f"The other line is {old_node.filename}:{old_node.linenumber}",
                            n.filename,
                            n.linenumber,
                        )
                        err.defer("duplicate_id")

                    self.default_translates[n.identifier] = n
                    self.file_translates[filename].append((label, n))
                else:
                    self.languages.add(n.language)
                    self.language_translates[n.identifier, n.language] = n
                    self.chain_worklist.append((n.identifier, n.language))

            else:
                for line in n.get_translation_strings():
                    self.additional_strings[filename].append(line)

    def chain_translates(self):
        """
        Chains nodes in non-default translates together.
        """

        unchained = []

        for identifier, language in self.chain_worklist:
            if identifier not in self.default_translates:
                unchained.append((identifier, language))
                continue

            translate = self.language_translates[identifier, language]
            next_node = self.default_translates[identifier].after

            if isinstance(translate, renpy.ast.TranslateSay):
                translate.chain(next_node)
            else:
                renpy.ast.chain_block(translate.block, next_node)

        self.chain_worklist = unchained

    def lookup_translate(self, identifier, alternate=None) -> tuple[renpy.ast.Node, bool]:
        identifier = identifier.replace(".", "_")
        language = renpy.game.preferences.language

        if language is not None:
            tl = self.language_translates.get((identifier, language), None)

            if (tl is None) and alternate:
                tl = self.language_translates.get((identifier, alternate), None)

        else:
            tl = None

        if tl is None:
            tl = self.default_translates[identifier]
            translated = False
        else:
            translated = True

        if isinstance(tl, renpy.ast.TranslateSay):
            return tl, translated
        else:
            return tl.block[0], translated

    def get_all_translates(self, identifier: str):
        """
        Return a dict of all existing translates for the given identifier.

        The dict keys are language names, or None for the default language.
        """

        identifier = identifier.replace(".", "_")
        language = renpy.game.preferences.language

        rv: dict[str | None, renpy.ast.Translate | renpy.ast.TranslateSay] = {}

        for language in self.languages:
            try:
                rv[language] = self.language_translates[(identifier, language)]
            except KeyError:
                pass

        rv[None] = self.default_translates[identifier]
        return rv

    def get_translate_info(self, identifier, language):
        identifier = identifier.replace(".", "_")

        if language is not None:
            tl = self.language_translates.get((identifier, language), None)
        else:
            tl = self.default_translates.get(identifier, None)

        if tl is None:
            return None

        return TranslateInfo(tl)

    def requires_init(self, language):
        return bool(
            self.python[language]
            or self.block[language]
            or self.early_block[language]
            or renpy.config.language_callbacks[language]
        )


def encode_say_string(s):
    """
    Encodes a string in the format used by Ren'Py say statements.
    """

    s = s.replace("\\", "\\\\")
    s = s.replace("\n", "\\n")
    s = s.replace('"', '\\"')
    s = re.sub(r"(?<= ) ", "\\ ", s)

    return '"' + s + '"'


class Restructurer(object):
    def __init__(self, children):
        self.label = None
        self.alternate = None

        self.preexisting_identifiers = set()
        self.identifiers = set()

        # Search for identifiers that have been set to the user, and add them
        # to self.preexisting_identifiers.
        for i in renpy.script.collapse_stmts(children):
            if isinstance(i, renpy.ast.Say):
                identifier = getattr(i, "identifier", None)
                if identifier is not None:
                    self.preexisting_identifiers.add(identifier)

        self.callback(children)

    def id_exists(self, identifier):
        if identifier in self.identifiers:
            return True

        if identifier in renpy.game.script.translator.default_translates:  # @UndefinedVariable
            return True

        return False

    def unique_identifier(self, label, digest):
        if label is None:
            base = digest
        else:
            base = label.replace(".", "_") + "_" + digest

        i = 0
        suffix = ""

        while True:
            identifier = base + suffix

            if not self.id_exists(identifier) and not (identifier in self.preexisting_identifiers):
                break

            i += 1
            suffix = "_{0}".format(i)

        return identifier

    def create_translate(self, block):
        """
        Creates an ast.Translate that wraps `block`. The block may only contain
        translatable statements.
        """

        md5 = hashlib.md5()

        for i in block:
            code = i.get_code()
            md5.update((code + "\r\n").encode("utf-8"))

        digest = md5.hexdigest()[:8]

        identifier = self.unique_identifier(self.label, digest)

        # Take id clause from the block if the last statement is Say statement
        id_identifier = None
        for i in block:
            if isinstance(i, renpy.ast.Say):
                id_identifier = getattr(i, "identifier", id_identifier)

        if self.alternate is not None:
            alternate = self.unique_identifier(self.alternate, digest)
            identifier = id_identifier or identifier

        elif id_identifier is not None:
            alternate = identifier
            identifier = id_identifier

        else:
            alternate = None

        self.identifiers.add(identifier)
        if alternate is not None:
            self.identifiers.add(alternate)

        loc = (block[0].filename, block[0].linenumber)

        tl = renpy.ast.Translate(loc, identifier, None, block, alternate=alternate)
        tl.name = block[0].name + ("translate",)

        ed = renpy.ast.EndTranslate(loc)
        ed.name = block[0].name + ("end_translate",)

        return [tl, ed]

    def combine_translate(self, node):
        """
        If we have a Translate containing a Say statement and an EndTranslate,
        combine them into a TranslateSay statement.
        """

        if not isinstance(node, renpy.ast.Translate):
            return node

        if not len(node.block) == 1:
            return node

        if not isinstance(node.block[0], renpy.ast.Say):
            return node

        say = node.block[0]

        rv = renpy.ast.TranslateSay(
            (say.filename, say.linenumber),
            say.who,
            say.what,
            say.with_,
            interact=say.interact,
            attributes=say.attributes,
            arguments=say.arguments,
            temporary_attributes=say.temporary_attributes,
            identifier=node.identifier,
            language=node.language,
            alternate=node.alternate,
        )

        rv.name = say.name
        rv.explicit_identifier = say.explicit_identifier

        return rv

    def callback(self, children):
        """
        This should be called with a list of statements. It restructures the statements
        in the list so that translatable statements are contained within translation blocks.
        """

        new_children = []
        group = []

        for i in children:
            if isinstance(i, renpy.ast.Label):
                if not i.hide:
                    if i.name.startswith("_"):
                        self.alternate = i.name
                    else:
                        self.label = i.name
                        self.alternate = None

            if not isinstance(i, renpy.ast.Translate):
                i.restructure(self.callback)

            if isinstance(i, renpy.ast.Say):
                group.append(i)
                tl = self.create_translate(group)
                new_children.extend(tl)
                group = []

            elif i.translatable:
                group.append(i)

            else:
                if group:
                    tl = self.create_translate(group)
                    new_children.extend(tl)
                    group = []

                new_children.append(i)

        if group:
            nodes = self.create_translate(group)
            new_children.extend(nodes)
            group = []

        # Combine translate and say into TranslateSay.
        new_children = [self.combine_translate(node) for node in new_children]

        # Remove EndTranslater when not required.

        new_new_children = []

        old_node = None

        for node in new_children:
            if isinstance(old_node, renpy.ast.TranslateSay) and isinstance(node, renpy.ast.EndTranslate):
                old_node.next = node.next
                old_node = None
                continue

            new_new_children.append(node)
            old_node = node

        children[:] = new_new_children


def restructure(children):
    Restructurer(children)


################################################################################
# String Translation
################################################################################


update_translations = "RENPY_UPDATE_STRINGS" in os.environ


def quote_unicode(s):
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\a", "\\a")
    s = s.replace("\b", "\\b")
    s = s.replace("\f", "\\f")
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    s = s.replace("\v", "\\v")

    return s


class StringTranslator(object):
    """
    This object stores the translations for a single language. It can also
    buffer unknown translations, and write them to a file at game's end, if
    we want that to happen.
    """

    def __init__(self):
        # A map from translation to translated string.
        self.translations = {}

        # A map from translation to the location of the translated string.
        self.translation_loc = {}

        # A list of unknown translations.
        self.unknown = []

    def add(self, old, new, newloc):
        if old in self.translations:
            if old in self.translation_loc:
                fn, line = self.translation_loc[old]
                raise Exception('A translation for "{}" already exists at {}:{}.'.format(quote_unicode(old), fn, line))
            else:
                raise Exception('A translation for "{}" already exists.'.format(quote_unicode(old)))

        self.translations[old] = new

        if newloc is not None:
            self.translation_loc[old] = newloc

    def translate(self, old):
        new = self.translations.get(old, None)

        if new is not None:
            return new

        if update_translations:
            self.translations[old] = old
            self.unknown.append(old)

        # Remove {#...} tags.
        if new is None:
            notags = re.sub(r"\{\#.*?\}", "", old)
            new = self.translations.get(notags, None)

        if new is not None:
            return new

        return old

    def write_updated_strings(self, language):
        if not self.unknown:
            return

        if language is None:
            fn = os.path.join(renpy.config.gamedir, "strings.rpy")
        else:
            fn = os.path.join(renpy.config.gamedir, renpy.config.tl_directory, language, "strings.rpy")

        with renpy.translation.generation.open_tl_file(fn) as f:
            f.write("translate {} strings:\n".format(language))
            f.write("\n")

            for i in self.unknown:
                i = quote_unicode(i)

                f.write('    old "{}"\n'.format(i))
                f.write('    new "{}"\n'.format(i))
                f.write("\n")


def add_string_translation(language, old, new, newloc):
    tl = renpy.game.script.translator
    stl = tl.strings[language]
    tl.languages.add(language)
    stl.add(old, new, newloc)


Default = renpy.object.Sentinel("default")


def translate_string(s, language=Default):  # type (str, str|renpy.object.Sentinel|None) -> str
    """
    :doc: translate_string
    :name: renpy.translate_string

    Returns `s` immediately translated into `language`. If `language`
    is Default, uses the language set in the preferences.
    Strings enclosed in this function will **not** be added
    to the list of translatable strings. Note that the string may be
    double-translated, if it matches a string translation when it
    is displayed.
    """

    if language is Default:
        language = renpy.game.preferences.language

    stl = renpy.game.script.translator.strings[language]  # @UndefinedVariable
    return stl.translate(s)


def write_updated_strings():
    stl = renpy.game.script.translator.strings[renpy.game.preferences.language]  # @UndefinedVariable
    stl.write_updated_strings(renpy.game.preferences.language)


################################################################################
# RPT Support
#
# RPT was the translation format used before 6.15.
################################################################################


def load_rpt(fn):
    """
    Loads the .rpt file `fn`.
    """

    def unquote(s):
        s = s.replace("\\n", "\n")
        s = s.replace("\\\\", "\\")
        return s

    language = os.path.basename(fn).replace(".rpt", "")

    old = None

    with renpy.loader.load(fn) as f:
        for l in f:
            l = l.decode("utf-8")
            l = l.rstrip()

            if not l:
                continue

            if l[0] == "#":
                continue

            s = unquote(l[2:])

            if l[0] == "<":
                if old:
                    raise Exception("{0} string {1!r} does not have a translation.".format(language, old))

                old = s

            if l[0] == ">":
                if old is None:
                    raise Exception("{0} translation {1!r} doesn't belong to a string.".format(language, s))

                add_string_translation(language, old, s, None)
                old = None

    if old is not None:
        raise Exception("{0} string {1!r} does not have a translation.".format(language, old))


def load_all_rpts():
    """
    Loads all .rpt files.
    """

    for fn in renpy.exports.list_files():
        if fn.endswith(".rpt"):
            load_rpt(fn)


################################################################################
# Changing language
################################################################################


style_backup = None


def init_translation():
    """
    Called before the game starts.
    """

    global style_backup
    style_backup = renpy.style.backup()  # @UndefinedVariable

    load_all_rpts()


old_language = "language never set"

# A list of styles that have beend deferred to right before translate
# styles are run.
deferred_styles = []


def old_change_language(tl, language, changed):
    if changed:
        for i in deferred_styles:
            i.apply()

    def run_blocks():
        for i in tl.early_block[language]:
            renpy.game.context().run(i.block[0])

        for i in tl.block[language]:
            renpy.game.context().run(i.block[0])

    renpy.game.invoke_in_new_context(run_blocks)

    for i in tl.python[language]:
        renpy.python.py_exec_bytecode(i.code.bytecode)

    for i in renpy.config.language_callbacks[language]:
        i()


def new_change_language(tl, language, changed):
    for i in tl.python[language]:
        renpy.python.py_exec_bytecode(i.code.bytecode)

    def run_early_blocks():
        for i in tl.early_block[language]:
            renpy.game.context().run(i.block[0])

    renpy.game.invoke_in_new_context(run_early_blocks)

    for i in renpy.config.language_callbacks[language]:
        i()

    if changed:
        for i in deferred_styles:
            i.apply()

    def run_blocks():
        for i in tl.block[language]:
            renpy.game.context().run(i.block[0])

    renpy.game.invoke_in_new_context(run_blocks)

    if changed:
        renpy.config.init_system_styles()


def clean_data():
    """
    This cleans out data that's dependent on the language.
    """

    if renpy.config.clear_history_on_language_change:
        renpy.store._history_list = renpy.store.list()  # type: ignore

    renpy.store.nvl_list = renpy.store.list()  # type: ignore
    renpy.game.log.forward = []


def change_language(language, force=False):
    """
    :doc: translation_functions

    Changes the current language to `language`, which can be a string or
    None to use the default language.
    """

    global old_language

    renpy.exports.load_language(language)

    renpy.game.preferences.language = language
    changed = language != old_language

    if not changed and not force:
        return

    tl = renpy.game.script.translator

    if changed:
        renpy.style.restore(style_backup)  # @UndefinedVariable
        renpy.style.rebuild(False)  # @UndefinedVariable

        for i in renpy.config.translate_clean_stores:
            renpy.python.clean_store(i)

    elif not tl.requires_init(language):
        return

    else:
        # Prevent memory leak by ignoring any style changes from translate
        # blocks when language hasn't changed.
        current_styles = renpy.style.backup()

    if renpy.config.new_translate_order:
        new_change_language(tl, language, changed)
    else:
        old_change_language(tl, language, changed)

    if changed:
        for i in renpy.config.change_language_callbacks:
            i()

        # Reset various parts of the system. Most notably, this clears the image
        # cache, letting us load translated images.
        renpy.exports.free_memory()

        # Rebuild the styles.
        renpy.style.rebuild()  # @UndefinedVariable

        # Re-init tts.
        renpy.display.tts.init()

        for i in renpy.config.translate_clean_stores:
            renpy.python.reset_store_changes(i)

        renpy.exports.block_rollback()

        old_language = language

    else:
        renpy.style.restore(current_styles)

    # Restart the interaction.
    renpy.exports.restart_interaction()


def check_language():
    """
    Checks to see if the language has changed. If it has, jump to the start
    of the current translation block.
    """

    ctx = renpy.game.contexts[-1]
    preferences = renpy.game.preferences

    # Deal with a changed language.
    if ctx.translate_language != preferences.language:
        clean_data()

        ctx.translate_language = preferences.language

        tid = ctx.translate_identifier or ctx.deferred_translate_identifier

        if tid is not None:
            node, _ = renpy.game.script.translator.lookup_translate(tid)  # @UndefinedVariable

            if node is not None:
                # This is necessary for the menu-with-say case. ADVCharacter needs
                # identifier to set deferred_translate_identifier again, but EndTranslation
                # has already set translate_identifier to None.
                ctx.translate_identifier = tid

                clean_data()

                raise renpy.game.JumpException(node.name)


def get_translation_identifier():
    """
    :doc: translation_functions

    Returns the translation identifier for the current statement.
    """

    ctx = renpy.game.contexts[-1]
    return ctx.translate_identifier or ctx.deferred_translate_identifier


def get_translation_info(identifier=None, language=None):
    """
    :doc: translation_functions

    Returns information about the translation with the given identifier, or about the default
    text if `language` is None.

    `identifier`
        The translation identifier, or None to get information about currently displayed
        text.

    `language`
        Either a language name, or None to get information about the default text.

    If no information is available, returns None. Else returns an object with the following
    attributes:

    .. attribute:: language
        The language of the translation.

    .. attribute:: identifier
        The identifier of the translation.

    .. attribute:: filename
        The filename the translation is found in.

    .. attribute:: linenumber
        The line number the translation is found on.

    .. attribute:: source
        A list of strings that make up the translation. Only some statements can be included here,
        including the say statements that make up most translations.
    """

    if identifier is None:
        identifier = get_translation_identifier()

    if identifier is None:
        return None

    tl = renpy.game.script.translator
    return tl.get_translate_info(identifier, language)


def known_languages():
    """
    :doc: translation_functions

    Returns the set of known languages. This does not include the default
    language, None.
    """

    return {i for i in renpy.game.script.translator.languages if i is not None}  # @UndefinedVariable


################################################################################
# Detect language
################################################################################


locales = {
    "ab": "abkhazian",
    "aa": "afar",
    "af": "afrikaans",
    "ak": "akan",
    "sq": "albanian",
    "am": "amharic",
    "ar": "arabic",
    "an": "aragonese",
    "hy": "armenian",
    "as": "assamese",
    "av": "avaric",
    "ae": "avestan",
    "ay": "aymara",
    "az": "azerbaijani",
    "bm": "bambara",
    "ba": "bashkir",
    "eu": "basque",
    "be": "belarusian",
    "bn": "bengali",
    "bh": "bihari",
    "bi": "bislama",
    "bs": "bosnian",
    "br": "breton",
    "bg": "bulgarian",
    "my": "burmese",
    "ca": "catalan",
    "ch": "chamorro",
    "ce": "chechen",
    "ny": "chewa",
    "cv": "chuvash",
    "kw": "cornish",
    "co": "corsican",
    "cr": "cree",
    "hr": "croatian",
    "cs": "czech",
    "da": "danish",
    "dv": "maldivian",
    "nl": "dutch",
    "dz": "dzongkha",
    "en": "english",
    "et": "estonian",
    "ee": "ewe",
    "fo": "faroese",
    "fj": "fijian",
    "fi": "finnish",
    "fr": "french",
    "ff": "fulah",
    "gl": "galician",
    "ka": "georgian",
    "de": "german",
    "el": "greek",
    "gn": "guaran",
    "gu": "gujarati",
    "ht": "haitian",
    "ha": "hausa",
    "he": "hebrew",
    "hz": "herero",
    "hi": "hindi",
    "ho": "hiri_motu",
    "hu": "hungarian",
    "id": "indonesian",
    "ga": "irish",
    "ig": "igbo",
    "ik": "inupiaq",
    "is": "icelandic",
    "it": "italian",
    "iu": "inuktitut",
    "ja": "japanese",
    "jv": "javanese",
    "kl": "greenlandic",
    "kn": "kannada",
    "kr": "kanuri",
    "ks": "kashmiri",
    "kk": "kazakh",
    "km": "khmer",
    "ki": "kikuyu",
    "rw": "kinyarwanda",
    "ky": "kirghiz",
    "kv": "komi",
    "kg": "kongo",
    "ko": "korean",
    "ku": "kurdish",
    "kj": "kuanyama",
    "la": "latin",
    "lb": "luxembourgish",
    "lg": "ganda",
    "li": "limburgan",
    "ln": "lingala",
    "lo": "lao",
    "lt": "lithuanian",
    "lv": "latvian",
    "gv": "manx",
    "mk": "macedonian",
    "mg": "malagasy",
    "ms": "malay",
    "ml": "malayalam",
    "mt": "maltese",
    "mi": "maori",
    "mr": "marathi",
    "mh": "marshallese",
    "mn": "mongolian",
    "na": "nauru",
    "nv": "navaho",
    "ne": "nepali",
    "ng": "ndonga",
    "no": "norwegian",
    "ii": "nuosu",
    "nr": "ndebele",
    "oc": "occitan",
    "oj": "ojibwa",
    "om": "oromo",
    "or": "oriya",
    "os": "ossetian",
    "pa": "panjabi",
    "pi": "pali",
    "fa": "persian",
    "pl": "polish",
    "ps": "pashto",
    "pt": "portuguese",
    "qu": "quechua",
    "rm": "romansh",
    "rn": "rundi",
    "ro": "romanian",
    "ru": "russian",
    "sa": "sanskrit",
    "sc": "sardinian",
    "sd": "sindhi",
    "se": "sami",
    "sm": "samoan",
    "sg": "sango",
    "sr": "serbian",
    "gd": "gaelic",
    "sn": "shona",
    "si": "sinhala",
    "sk": "slovak",
    "sl": "slovene",
    "so": "somali",
    "st": "sotho",
    "es": "spanish",
    "su": "sundanese",
    "sw": "swahili",
    "ss": "swati",
    "sv": "swedish",
    "ta": "tamil",
    "te": "telugu",
    "tg": "tajik",
    "th": "thai",
    "ti": "tigrinya",
    "bo": "tibetan",
    "tk": "turkmen",
    "tl": "tagalog",
    "tn": "tswana",
    "to": "tongan",
    "tr": "turkish",
    "ts": "tsonga",
    "tt": "tatar",
    "tw": "twi",
    "ty": "tahitian",
    "ug": "uighur",
    "uk": "ukrainian",
    "ur": "urdu",
    "uz": "uzbek",
    "ve": "venda",
    "vi": "vietnamese",
    "wa": "walloon",
    "cy": "welsh",
    "wo": "wolof",
    "fy": "frisian",
    "xh": "xhosa",
    "yi": "yiddish",
    "yo": "yoruba",
    "za": "zhuang",
    "zu": "zulu",
    "chs": "simplified_chinese",
    "cht": "traditional_chinese",
    "zh": "traditional_chinese",
    "zh_tw": "traditional_chinese",
    "zh_cn": "simplified_chinese",
    "zh_hk": "traditional_chinese",
    "zh_sg": "simplified_chinese",
    "zh_mo": "traditional_chinese",
}


def detect_user_locale():
    import locale

    if renpy.windows:
        import ctypes

        windll = ctypes.windll.kernel32  # type: ignore
        locale_name = locale.windows_locale.get(windll.GetUserDefaultUILanguage())
    elif renpy.android:
        from jnius import autoclass  # type: ignore

        Locale = autoclass("java.util.Locale")
        locale_name = str(Locale.getDefault().getLanguage())
    elif renpy.ios:
        import pyobjus  # type: ignore

        NSLocale = pyobjus.autoclass("NSLocale")
        languages = NSLocale.preferredLanguages()

        locale_name = languages.objectAtIndex_(0).UTF8String()
        if isinstance(locale_name, bytes):
            locale_name = locale_name.decode("utf-8")

        locale_name = locale_name.replace("-", "_")
    else:
        locale_name = locale.getdefaultlocale()
        if locale_name is not None:
            locale_name = locale_name[0]

    if locale_name is None:
        return None, None

    normalize = locale.normalize(locale_name)
    if normalize == locale_name:
        language = region = locale_name
    else:
        locale_name = normalize
        if "." in locale_name:
            locale_name, _ = locale_name.split(".", 1)
        language, region = locale_name.lower().split("_")
    return language, region


# Generated by scripts/relative_imports.py, do not edit below this line.
import typing

if typing.TYPE_CHECKING:
    from . import dialogue as dialogue
    from . import extract as extract
    from . import generation as generation
    from . import merge as merge
    from . import scanstrings as scanstrings
