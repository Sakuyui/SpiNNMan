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

import logging
import socket
from spinn_utilities.log import FormatAdapter
from spinnman.exceptions import SpinnmanIOException

logger = FormatAdapter(logging.getLogger(__name__))


def get_udp_socket():
    """ Wrapper round socket() system call to produce UDP/IPv4 sockets.
    """
    try:
        # Create a UDP Socket
        return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except Exception as exception:  # pylint: disable=broad-except
        raise SpinnmanIOException(
            "Error setting up socket: {}".format(exception)) from exception


def get_tcp_socket():
    """ Wrapper round socket() system call to produce TCP/IPv4 sockets.

    .. note::
        TCP sockets cannot be used to talk to a SpiNNaker board.
    """
    try:
        # Create a UDP Socket
        return socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except Exception as exception:  # pylint: disable=broad-except
        raise SpinnmanIOException(
            "Error setting up socket: {}".format(exception)) from exception


def set_receive_buffer_size(sock, size):
    """ Wrapper round setsockopt() system call.
    """
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, size)
    except Exception:  # pylint: disable=broad-except
        # The OS said no, but we might still be able to work right with
        # the defaults. Just warn and hope...
        logger.warning("failed to configure UDP socket to have a large "
                       "receive buffer", exc_info=True)


def bind_socket(sock, host, port):
    """ Wrapper round bind() system call.
    """
    try:
        # Bind the socket
        sock.bind((str(host), int(port)))
    except Exception as exception:  # pylint: disable=broad-except
        raise SpinnmanIOException(
            "Error binding socket to {}:{}: {}".format(
                host, port, exception)) from exception


def resolve_host(host):
    """ Wrapper round gethostbyname() system call.
    """
    try:
        return socket.gethostbyname(host)
    except Exception as exception:  # pylint: disable=broad-except
        raise SpinnmanIOException(
            "Error getting IP address for {}: {}".format(
                host, exception)) from exception


def connect_socket(sock, remote_address, remote_port):
    """ Wrapper round connect() system call.
    """
    try:
        sock.connect((str(remote_address), int(remote_port)))
    except Exception as exception:  # pylint: disable=broad-except
        raise SpinnmanIOException(
            "Error connecting to {}:{}: {}".format(
                remote_address, remote_port, exception)) from exception


def get_socket_address(sock):
    """ Wrapper round getsockname() system call.
    """
    try:
        addr, port = sock.getsockname()
        # Ensure that a standard address is used for the INADDR_ANY
        # hostname
        if addr is None or addr == "":
            addr = "0.0.0.0"
        return addr, port
    except Exception as exception:  # pylint: disable=broad-except
        raise SpinnmanIOException("Error querying socket: {}".format(
            exception)) from exception
