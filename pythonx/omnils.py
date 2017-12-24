# -*- coding: utf-8 -*-
"""
ncm-R: tools to convert omnils to NCM matches

by Gabriel Alcaras
"""

import re


class Function(object):  # pylint: disable=too-few-public-methods

    """Function object to generate snippet and arguments."""

    def __init__(self, word='', info=''):
        """Initialize function object with match data"""

        self._word = word
        self._info = info

        self.args = list()
        self.snippet = ''

        self._get_args()
        self._make_snippet()

    def _get_args(self):
        """Get function arguments based on omniline info"""

        if not self._info:
            return

        if re.search('\x08', self._info):
            splits = re.split('\x08', self._info)
            args = splits[0]
        else:
            args = self._info

        args = re.split('\t', args)
        args = [arg.replace('\x07', ' = ') for arg in args]

        self.args = args

    def _make_snippet(self):
        """Create function snippet with its arguments"""

        self.snippet = self._word + '('

        if self.args[0] == 'NO_ARGS':
            self.snippet += ')'
            return

        # Get arguments without no default value (usually mandatory arguments)
        mand_args = [a for a in self.args if '=' not in a]

        for numarg, arg in enumerate(mand_args):
            if arg in ('...') and numarg > 0:
                continue

            self.snippet += '${' + str(numarg+1) + ':' + arg + '}, '

        if len(mand_args) >= 1:
            self.snippet = self.snippet[:-2]
        else:
            self.snippet += '$1'

        self.snippet += ')'


class Match(object):  # pylint: disable=too-few-public-methods

    """NCM match"""

    MIN_LEN = dict(col1=7, col2=7)

    def __init__(self):

        self.len = dict(col1=11, col2=11)

    def setup(self, settings):
        """Change Match setup"""

        self.len['col1'] = settings['col1_len']
        self.len['col2'] = settings['col2_len']

    def _col(self, value='', col_nb=1, brackets=False):
        """Return formatted column value

        :value: content of the column
        :col_nb: position of the column
        :brackets: add brackets to the column
        :returns: formatted column value
        """

        column = 'col' + str(col_nb)

        if self.len[column] < self.MIN_LEN[column]:
            return ''
        else:
            if brackets:
                return '{' + value[0:self.len[column]-3] + '}'

            return value[0:self.len[column]-1]

    def _menu(self, col1='', col2='', col3=''):
        """Return formatted menu depending with column values"""

        # Return whole column if there's only one
        if col1 and not col2 and not col3:
            return col1

        menu = ''

        # If there's a first column and it's wide enough
        if col1 and self.len['col1'] >= self.MIN_LEN['col1']:
            form = '{:' + str(self.len['col1']-1) + '} '
            menu += form.format(col1)

        # If there's a second column and it's wide enough
        if col2 and self.len['col2'] >= self.MIN_LEN['col2']:
            form = '{:' + str(self.len['col2']-1) + '} '
            menu += form.format(col2)

        # Always add the third column if it exists
        if col3:
            menu += col3

        return menu.strip()

    def build(self, word='', struct='', pkg='', info=''):
        """Return NCM match

        :word: word (appears in menu)
        :struct: type (str() in R)
        :pkg: pkg
        :info: additional information about the object (args, doc, etc.)
        :returns: NCM match
        """

        match = dict(word=word, struct=struct, pkg=pkg, info=info)

        if match['info']:
            obj_title = re.search(r'\x08(.*)\x05', match['info'])

            if obj_title:
                match['title'] = obj_title.group(1).strip()

        title = ''

        if 'title' in match:
            title = match['title']
            del match['title']

        match['menu'] = self._menu(self._col(match['pkg'], 1, brackets=True),
                                   self._col(match['struct'], 2),
                                   title)

        if struct == 'function':
            match = self._process_function(match)
        elif struct in ('data.frame', 'tbl_df'):
            match = self._process_df(match)
        elif struct == 'package':
            match = self._process_package(match)
        elif struct == 'argument':
            match = self._process_argument(match)
        else:
            pass

        if '$' in word:
            match = self._process_variable(match)

        del match['info']

        return match

    def _process_function(self, match):
        """Process match when it's a function."""

        function = Function(word=match['word'], info=match['info'])

        match['args'] = list()
        for arg in function.args:
            if arg in ('NO_ARGS', '...'):
                continue

            match['args'].append(self.build(word=arg, struct='argument'))

        match['snippet'] = function.snippet

        return match

    def _process_df(self, match):
        """Process match when it's a data.frame or a tibble."""

        match['snippet'] = match['word'] + ' %>%$1'

        return match

    def _process_package(self, match):
        """Process match when it's an R package."""

        match['snippet'] = match['word'] + '::$1'
        match['menu'] = self._menu(self._col('package', 1),
                                   match['info'])

        return match

    def _process_argument(self, match):
        """Process match when it's a function argument."""

        word_parts = [w.strip() for w in match['word'].split('=')]
        lhs = word_parts[0]
        rhs = word_parts[1] if len(word_parts) == 2 else ''

        match['word'] = lhs

        col2 = '= ' + rhs if rhs else ''
        match['menu'] = self._menu(self._col('argument', 1), col2)

        if rhs:
            quotes = re.search(r'^"(.*)"$', rhs)

            if quotes:
                match['snippet'] = lhs + ' = "${1:' + quotes.group(1) + '}"'
            else:
                match['snippet'] = lhs + ' = ${1:' + rhs + '}'
        else:
            match['snippet'] = lhs + ' = $1'

        return match

    def _process_variable(self, match):
        """Process match when it's a variable of a data.frame."""

        match['menu'] = self._menu(self._col('variable', 1),
                                   match['struct'])

        return match


class Matches(object):

    """Transform omnils lines into list of NCM matches"""

    def __init__(self):
        self.match = Match()

    def setup(self, settings):
        """Change Matches setup"""

        self.match.setup(settings)

    def from_omnils(self, lines):
        """Return list matches given lines of an omnils file"""

        matches = list()

        for line in lines:
            parts = re.split('\x06', line)

            if len(parts) >= 5:
                matches.append(self.match.build(word=parts[0],
                                                struct=parts[1],
                                                pkg=parts[3],
                                                info=parts[4]))

        return matches

    def from_pkg_desc(self, lines):
        """Return list of matches given lines of package description file"""

        matches = list()

        for line in lines:
            parts = re.split('\t', line)

            if len(parts) >= 2:
                matches.append(self.match.build(word=parts[0],
                                                info=parts[1],
                                                struct='package'))

        return matches
