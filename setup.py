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

from stripe_mock_server import __author__, __version__


setup(
    name='stripe_mock_server',
    version=__version__,
    author=__author__,
    url='https://github.com/tolteck/stripe_mock_server',

    packages=['stripe_mock_server'],
    entry_points={'console_scripts':
                  ['stripe_mock_server=stripe_mock_server.server:start']},
    package_data={
        'stripe_mock_server': ['fake-stripe-v3.js'],
    },
    install_requires=[
        'Flask >=0.11.1',
        'python-dateutil >=2.6.1',
    ],
)
