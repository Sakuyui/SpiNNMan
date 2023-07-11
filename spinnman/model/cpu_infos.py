# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from typing import Dict, Iterable, Iterator, Tuple
from spinn_utilities.typing.coords import XYP
from .cpu_info import CPUInfo

from spinnman.model.enums import CPUState


class CPUInfos(object):
    """
    A set of CPU information objects.
    """
    __slots__ = [
        "_cpu_infos"]

    def __init__(self) -> None:
        self._cpu_infos: Dict[XYP, CPUInfo] = dict()

    def add_info(self, cpu_info: CPUInfo):
        """
        Add a info on using its core coordinates.

        :param ~spinnman.model.CPUInfo cpu_info:
        """
        self._cpu_infos[cpu_info.x, cpu_info.y, cpu_info.p] = cpu_info

    def add_processor(self, x: int, y: int, processor_id: int,
                      cpu_info: CPUInfo):
        """
        Add a info on a given core.

        :param int x: The x-coordinate of the chip
        :param int y: The y-coordinate of the chip
        :param int processor_id: A processor ID
        :param CPUInfo cpu_info:
            The CPU information for the core.
            Not checked so could be None at test own risk
        """
        self._cpu_infos[x, y, processor_id] = cpu_info

    @property
    def cpu_infos(self) -> Iterator[Tuple[XYP, CPUInfo]]:
        """
        The one per core core info.

        :return: iterable of x,y,p core info
        :rtype: iterable(~spinnman.model.CPUInfo)
        """
        return iter(self._cpu_infos.items())

    def __iter__(self) -> Iterator[XYP]:
        return iter(self._cpu_infos)

    def iteritems(self) -> Iterator[Tuple[XYP, CPUInfo]]:
        """
        Get an iterable of (x, y, p), cpu_info.
        :rtype: (iterable(tuple(int, int, int),  ~spinnman.model.CPUInfo)
        """
        return iter(self._cpu_infos.items())

    def items(self) -> Iterable[Tuple[XYP, CPUInfo]]:
        return self._cpu_infos.items()

    def values(self) -> Iterable[CPUInfo]:
        return self._cpu_infos.values()

    def itervalues(self) -> Iterator[CPUInfo]:
        """
        Get an iterable of cpu_info.
        """
        return iter(self._cpu_infos.values())

    def keys(self) -> Iterable[XYP]:
        return self._cpu_infos.keys()

    def iterkeys(self) -> Iterator[XYP]:
        """
        Get an iterable of (x, y, p).
        """
        return iter(self._cpu_infos.keys())

    def __len__(self) -> int:
        """
        The total number of processors that are in these core subsets.
        """
        return len(self._cpu_infos)

    def is_core(self, x: int, y: int, p: int) -> bool:
        """
        Determine if there is a CPU Info for x, y, p.
        """
        return (x, y, p) in self._cpu_infos

    def get_cpu_info(self, x: int, y: int, p: int) -> CPUInfo:
        """
        Get the information for the given core on the given core

        :rtype: CpuInfo
        """
        return self._cpu_infos[x, y, p]

    def infos_for_state(self, state: CPUState) -> 'CPUInfos':
        """
        Creates a new CpuInfos object with Just the Infos that match the state.

        :param ~spinnman.model.enums.CPUState state:
        :return: New Infos object with the filtered infos if any
        :rtype: CPUInfos
        """
        for_state = CPUInfos()
        for info in self._cpu_infos.values():
            if info.state == state:
                for_state.add_info(info)
        return for_state

    def get_status_string(self) -> str:
        """
        Get a string indicating the status of the given cores.

        :rtype: str
        """
        break_down = "\n"
        for (x, y, p), core_info in self.cpu_infos:
            if core_info.state == CPUState.RUN_TIME_EXCEPTION:
                break_down += "    {}:{}:{} (ph: {}) in state {}:{}\n".format(
                    x, y, p, core_info.physical_cpu_id, core_info.state.name,
                    core_info.run_time_error.name)
                break_down += "        r0={}, r1={}, r2={}, r3={}\n".format(
                    core_info.registers[0], core_info.registers[1],
                    core_info.registers[2], core_info.registers[3])
                break_down += "        r4={}, r5={}, r6={}, r7={}\n".format(
                    core_info.registers[4], core_info.registers[5],
                    core_info.registers[6], core_info.registers[7])
                break_down += "        PSR={}, SP={}, LR={}\n".format(
                    core_info.processor_state_register,
                    core_info.stack_pointer, core_info.link_register)
            else:
                break_down += "    {}:{}:{} in state {}\n".format(
                    x, y, p, core_info.state.name)
        return break_down

    def __str__(self) -> str:
        return str([f"{x}, {y}, {p} (ph: {info.physical_cpu_id})"
                    for (x, y, p), info in self._cpu_infos.items()])

    def __repr__(self) -> str:
        return self.__str__()
