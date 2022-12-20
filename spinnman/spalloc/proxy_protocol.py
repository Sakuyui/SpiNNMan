# Copyright (c) 2021-2022 The University of Manchester
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
from enum import IntEnum


class ProxyProtocol(IntEnum):
    #: Message relating to opening a channel
    OPEN = 0
    #: Message relating to closing a channel
    CLOSE = 1
    #: Message sent on a channel
    MSG = 2
    #: Message relating to opening an unbound listen-only channel
    OPEN_UNBOUND = 3
    #: Message sent on an unbound channel to a given board
    MSG_TO = 4
