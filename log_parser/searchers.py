# -*- coding: utf-8 -*-

import re
import collections


class InvalidParsing(ValueError): pass


class AbstractSearchInstance(object):
    def process_row(self, row, row_params):
        raise NotImplementedError

    def finished(self):
        raise NotImplementedError

    def get_output(self):
        raise NotImplementedError


class AbstractSearchQuery(object):
    def __init__(self, instance_cls):
        self._instance_cls = instance_cls

    def can_start(self, row, row_params):
        raise NotImplementedError

    def create_instance(self, row, row_params):
        raise NotImplementedError


class SimpleSearcher(object):
    def __init__(self, data, queries):
        self._data = data
        self._output_buffer = collections.deque()
        self._instances = {}
        self._queries = queries
        self._input_empty = False

    def __iter__(self):
        return self

    def next(self):
        while True:
            try:
                row, row_params = self._data.next()
                thread = row_params['thread']

                thread_instances = self._instances.get(thread, None)
                if thread_instances is None:
                    thread_instances = []
                    self._instances[thread] = thread_instances

                for instance in thread_instances:
                    instance.process_row(row, row_params)

                for query in self._queries:
                    if query.can_start(row, row_params):
                        thread_instances.append(query.create_instance(row, row_params))

                finished_instances = []
                for instance in thread_instances:
                    if instance.finished():
                        self._output_buffer.extend(instance.get_output())
                        finished_instances.append(instance)

                for instance in finished_instances:
                    thread_instances.remove(instance)
            except StopIteration:
                self._input_empty = True
                pass

            if self._output_buffer:
                return self._output_buffer.popleft()
            elif self._input_empty:
                raise StopIteration


class SimpleSQLSearchQuery(AbstractSearchQuery):
    def __init__(self, instance_cls, param_name=None):
        super(SimpleSQLSearchQuery, self).__init__(instance_cls)
        self._sql_pattern = re.compile('delete|update.*set|insert.*into|select.*from', re.I)
        self._param_name = '\w*' if param_name is None else param_name

    def can_start(self, row, row_params):
        return self._sql_pattern.search(row) is not None

    def create_instance(self, row, row_params):
        return self._instance_cls(self._param_name, row)


class SimpleSQLSearchInstance(AbstractSearchInstance):
    def __init__(self, param_name, found_sql):
        self._output_buffer = collections.deque()
        self._param_name = param_name
        self._found_sql = found_sql

    def process_row(self, row, row_params):
        if row_params['match']:
            param_pattern = re.compile(r"{.*'%s': ?%s.*}" % (self._param_name, row_params['match']))

            if param_pattern.search(row):
                self._output_buffer.append(self._found_sql)
                self._output_buffer.append(row)

    def finished(self):
        return len(self._output_buffer) > 0

    def get_output(self):
        return self._output_buffer
