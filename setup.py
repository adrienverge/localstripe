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

from setuptools import setup

from localstripe import __author__, __version__


setup(
    name='localstripe',
    version=__version__,
    author=__author__,
    url='https://github.com/adrienverge/localstripe',
    description=('A fake but stateful Stripe server that you can run locally, '
                 'for testing purposes.'),

    packages=['localstripe'],
    entry_points={'console_scripts':
                  ['localstripe=localstripe.server:start']},
    package_data={
        'localstripe': ['localstripe-v3.js'],
    },
    install_requires=[
        'aiohttp >=2.3.2',
        'python-dateutil >=2.6.1',
    ],
)
