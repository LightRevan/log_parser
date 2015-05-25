# -*- coding: utf-8 -*-
__author__ = 'lightrevan'

import re
import functools


def create_row_parser(cls, **kwargs):
    return functools.partial(cls, **kwargs)


def not_none_transform(match):
    if match is None:
        raise AttributeError
    else:
        return match


int_timestamp = ('^\d+', lambda x: int(not_none_transform(x)))


class AbstractRowParser(object):
    @classmethod
    def _compile_pattern(cls, pattern):
        return pattern if isinstance(pattern, re._pattern_type) else re.compile(pattern)

    def parse_row(self, row):
        raise NotImplemented


class UniversalRowParser(AbstractRowParser):
    def __init__(self, match_pattern, **kwargs):
        assert 'timestamp' in kwargs, 'Must have timestamp pattern in row parser'

        match_pattern = match_pattern
        self.patterns = {'match': (self._compile_pattern(match_pattern), lambda x: x)}
        for name, data in kwargs.items():
            if isinstance(data, tuple):
                pattern, transform = data
            else:
                pattern = data
                transform = not_none_transform

            self.patterns[name] = (self._compile_pattern(pattern), transform)

    def parse_row(self, row):
        res = {}
        for name, data in self.patterns.items():
            pattern, transform = data
            match = pattern.search(row)
            res[name] = transform(match.group(0) if match else None)

        return res


class SinglePatternThreadParser(AbstractRowParser):
    def __init__(self, match_pattern, row_pattern, group_transform):
        self._match_pattern = self._compile_pattern(match_pattern)
        self._row_pattern = self._compile_pattern(row_pattern)

    def parse_row(self, row):
        params_match = self._row_pattern.search(row)
        match = self._match_pattern.search(row)
        return {'match': match.group(0) if match else None,
                'timestamp': params_match.group(1),
                'thread': params_match.group(2)}


class SimpleRowGetter(object):
    def __init__(self, f, row_parser):
        self._f = f
        self.row_parser = row_parser

    def __iter__(self):
        return self

    def next(self):
        row = self._f.next().strip()
        return row, self.row_parser.parse_row(row)


class MergingRowGetter(SimpleRowGetter):
    def __init__(self, *args):
        super(MergingRowGetter, self).__init__(*args)

        self._next_row = None
        self._next_params = None

    def next(self):
        if self._next_row is None:
            row = self._f.next().strip()
            params = self.row_parser.parse_row(row)
        else:
            row, params = self._next_row, self._next_params

        try:
            next_row_valid = False
            self._next_row = None
            while not next_row_valid:
                next_row = self._f.next()
                try:
                    next_params = self.row_parser.parse_row(next_row)

                    next_row_valid = True
                    self._next_row = next_row
                    self._next_params = next_params
                except AttributeError:
                    row += '\n' + next_row
        except StopIteration:
            pass

        return row, params