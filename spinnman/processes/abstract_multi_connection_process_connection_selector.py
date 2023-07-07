# Copyright (c) 2015 The University of Manchester
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

from spinn_utilities.abstract_base import (
    AbstractBase, abstractmethod)
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.connections.udp_packet_connections import SCAMPConnection


class ConnectionSelector(object, metaclass=AbstractBase):
    """
    A connection selector for multi-connection processes.
    """
    __slots__ = ()

    @abstractmethod
    def get_next_connection(
            self, message: AbstractSCPRequest) -> SCAMPConnection:
        """
        Get the index of the  next connection for the process from a list
        of connections.

        :param AbstractSCPRequest message: The SCP message to be sent
        :rtype: SCAMPConnection
        """
        raise NotImplementedError
