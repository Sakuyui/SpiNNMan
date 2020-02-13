# Copyright (c) 2017-2019 The University of Manchester
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

import os
import struct
import numpy
from spinnman.utilities.io.file_io import FileIO


def test_file_io():
    n_bytes = 1000
    read_start_offset = 5
    read_end_offset = -10
    my_file = "test"
    data = bytearray(numpy.random.randint(0, 256, n_bytes).astype("uint8"))
    memory = FileIO(my_file, 0, n_bytes)
    memory.write(bytes(data))
    memory = memory[read_start_offset:read_end_offset]
    read_data = bytearray(memory.read())
    compare_data = data[read_start_offset:read_end_offset]
    assert(compare_data == read_data)

    memory.seek(20)
    test_data = bytearray(list(range(10)))
    memory.write(bytes(test_data))
    memory.write(bytes(test_data))
    memory.seek(-10, os.SEEK_CUR)
    read_data = bytearray(memory.read(10))
    assert(test_data == read_data)

    _test_fill(memory, 100)
    _test_fill(memory, 101)
    _test_fill(memory, 102)
    _test_fill(memory, 103)

    memory.seek(0)
    sub_memory_1 = memory[0:10]
    sub_memory_2 = memory[0:10]
    sub_memory_1.write(b'test')
    result = sub_memory_2.read(4)
    assert(result == b'test')

    memory.close()
    os.remove(my_file)


def _test_fill(memory, offset):
    memory.seek(offset + 12)
    memory.write(struct.pack("B", 10))
    memory[offset:offset + 12].fill(5)
    memory.seek(offset)
    test_data = struct.unpack("<III", memory.read(12))
    assert(test_data == (5, 5, 5))
    assert(struct.unpack("B", memory.read(1))[0] == 10)
