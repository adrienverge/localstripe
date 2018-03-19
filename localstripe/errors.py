# -*- coding: utf-8 -*-
# Copyright 2017 Adrien Vergé
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json

from aiohttp import web


def json_response(*args, **kwargs):
    return web.json_response(
        *args,
        dumps=lambda x: json.dumps(x, indent=2, sort_keys=True) + '\n',
        **kwargs)


class UserError(Exception):
    def __init__(self, code, message=None, contents=None):
        Exception.__init__(self)
        self.code = code
        self.body = {'error': contents or {}}
        self.body['error']['type'] = 'invalid_request_error'
        if message is not None:
            self.body['error']['message'] = message

    def to_response(self):
        return json_response(self.body, status=self.code)
