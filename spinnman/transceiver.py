
from spinnman.connections.udp_packet_connections.iptag_connection import \
    IPTagConnection
from spinnman.connections.udp_packet_connections.udp_bmp_connection import \
    UDPBMPConnection
from spinnman.messages.scp.impl.scp_bmp_set_led_request import \
    SCPBMPSetLedRequest
from spinnman.messages.scp.impl.scp_bmp_version_request import \
    SCPBMPVersionRequest
from spinnman.messages.scp.impl.scp_power_request import SCPPowerRequest
from spinnman.messages.scp.impl.scp_read_adc_request import SCPReadADCRequest
from spinnman.messages.scp.impl.scp_read_fpga_register_request import \
    SCPReadFPGARegisterRequest
from spinnman.messages.scp.impl.scp_write_fpga_register_request import \
    ScpWriteFPGARegisterRequest
from spinnman.model.diagnostic_filter import DiagnosticFilter
from spinnman.connections.udp_packet_connections.stripped_iptag_connection \
    import StrippedIPTagConnection
from spinnman.connections.udp_packet_connections.udp_boot_connection \
    import UDPBootConnection
from spinnman import constants
from spinnman.connections.udp_packet_connections.udp_spinnaker_connection \
    import UDPSpinnakerConnection
from spinnman.connections.abstract_classes.abstract_udp_connection \
    import AbstractUDPConnection
from spinnman import exceptions
from spinnman.messages.eieio.command_messages.eieio_command_message \
    import EIEIOCommandMessage
from spinnman.messages.scp.impl.scp_reverse_iptag_set_request import \
    SCPReverseIPTagSetRequest
from spinnman.messages.sdp.sdp_message import SDPMessage

from spinnman.model.chip_info import ChipInfo
from spinnman.model.cpu_info import CPUInfo
from spinnman.model.machine_dimensions import MachineDimensions
from spinnman.model.core_subsets import CoreSubsets
from spinnman.model.router_diagnostics import RouterDiagnostics

from spinnman.messages.spinnaker_boot.spinnaker_boot_messages \
    import SpinnakerBootMessages
from spinnman.messages.scp.impl.scp_read_link_request \
    import SCPReadLinkRequest
from spinnman.messages.scp.impl.scp_write_link_request \
    import SCPWriteLinkRequest
from spinnman.messages.scp.impl.scp_read_memory_request \
    import SCPReadMemoryRequest
from spinnman.messages.scp.impl.scp_version_request \
    import SCPVersionRequest
from spinnman.messages.scp.impl.scp_count_state_request \
    import SCPCountStateRequest
from spinnman.messages.scp.impl.scp_write_memory_request \
    import SCPWriteMemoryRequest
from spinnman.messages.scp.impl.scp_flood_fill_start_request \
    import SCPFloodFillStartRequest
from spinnman.messages.scp.impl.scp_flood_fill_data_request \
    import SCPFloodFillDataRequest
from spinnman.messages.scp.impl.scp_flood_fill_end_request \
    import SCPFloodFillEndRequest
from spinnman.messages.scp.impl.scp_application_run_request \
    import SCPApplicationRunRequest
from spinnman.messages.scp.impl.scp_send_signal_request \
    import SCPSendSignalRequest
from spinnman.messages.scp.impl.scp_iptag_set_request \
    import SCPIPTagSetRequest
from spinnman.messages.scp.impl.scp_iptag_clear_request \
    import SCPIPTagClearRequest
from spinnman.messages.scp.impl.scp_router_alloc_request \
    import SCPRouterAllocRequest
from spinnman.messages.scp.impl.scp_router_init_request \
    import SCPRouterInitRequest
from spinnman.messages.scp.impl.scp_router_clear_request \
    import SCPRouterClearRequest
from spinnman.messages.scp.impl.scp_read_memory_words_request \
    import SCPReadMemoryWordsRequest
from spinnman.messages.scp.impl.scp_write_memory_words_request \
    import SCPWriteMemoryWordsRequest
from spinnman.messages.scp.impl.scp_led_request \
    import SCPLEDRequest
from spinnman.messages.scp.impl.scp_app_stop_request import SCPAppStopRequest
from spinnman.messages.scp.scp_result import SCPResult

from spinnman.data.abstract_data_reader import AbstractDataReader
from spinnman.data.little_endian_byte_array_byte_writer \
    import LittleEndianByteArrayByteWriter
from spinnman.data.little_endian_byte_array_byte_reader \
    import LittleEndianByteArrayByteReader

from spinnman import _utils

# noinspection
from spinnman.connections.listeners._connection_queue import _ConnectionQueue
from _threads._scp_message_interface import SCPMessageInterface
from _threads._iobuf_interface import IOBufInterface
from _threads._get_tags_interface import GetTagsInterface

from spinn_machine.machine import Machine
from spinn_machine.chip import Chip
from spinn_machine.sdram import SDRAM
from spinn_machine.processor import Processor
from spinn_machine.router import Router
from spinn_machine.link import Link
from spinn_machine.multicast_routing_entry import MulticastRoutingEntry

from collections import deque
from threading import Condition
from multiprocessing.pool import ThreadPool

import logging
import math
import time
import socket


logger = logging.getLogger(__name__)

_SCAMP_NAME = "SC&MP"
_SCAMP_VERSION = 1.33

_BMP_NAME = "BC&MP"
_BMP_VERSIONS = [1.37, 1.36]


def create_transceiver_from_hostname(
        hostname, bmp_ip_addresses, version, number_of_boards,
        ignore_chips=None, ignore_cores=None, max_core_id=None):
    """ Create a Transceiver by creating a UDPConnection to the given\
        hostname on port 17893 (the default SCAMP port), and a\
        UDPBootConnection on port 54321 (the default boot port),
        optionally discovering any additional links using the UDPConnection,\
        and then returning the transceiver created with the conjunction of the\
        created UDPConnection and the discovered connections

    :param hostname: The hostname or IP address of the board
    :type hostname: str
    :param number_of_boards: a numebr o boards expected to eb supported, or None
    :type number_of_boards: int or None
    :param ignore_chips: An optional set of chips to ignore in the\
                machine.  Requests for a "machine" will have these chips\
                excluded, as if they never existed.  The processor_ids of\
                the specified chips are ignored.
    :type ignore_chips: :py:class:`spinnman.model.core_subsets.CoreSubsets`
    :param ignore_cores: An optional set of cores to ignore in the\
                machine.  Requests for a "machine" will have these cores\
                excluded, as if they never existed.
    :type ignore_cores: :py:class:`spinnman.model.core_subsets.CoreSubsets`
    :param max_core_id: The maximum core id in any discovered machine.\
                Requests for a "machine" will only have core ids up to\
                this value.
    :type max_core_id: int
    :param version: the type of spinnaker board used within the spinnaker
                    machine being used. If a spinn-5 board, then the version
                    will be 5, spinn-3 would equal 3 and so on.
    :param bmp_ip_addresses: the ip-addresses of the bmp connection used to boot
                           multi-board systems.
    :type bmp_ip_addresses: iterable of str
    :return: The created transceiver
    :rtype: :py:class:`spinnman.transceiver.Transceiver`
    :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                communicating with the board
    :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                is received that is not in the valid format
    :raise spinnman.exceptions.SpinnmanInvalidParameterException: If a\
                packet is received that has invalid parameters
    :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                a response indicates an error during the exchange
    """
    connections = list()
    bmp_to_data_mapping = dict()
    cabinat_frame_to_connection_mapping = dict()

    # if no bmp has been supplied, but the board is a spinn4 or a spinn5
    # machine, then an assumption can be made that the bmp is at -1 on the
    # final value of the ipaddress
    if len(bmp_ip_addresses) == 0 and version >= 4:
        bmp_connection_data = \
            _utils.sort_out_bmp_from_machine(hostname, number_of_boards)
        udp_bmp_connection = \
            UDPBMPConnection(remote_host=bmp_connection_data.ip_address)
        # update dictonaries
        _utils.update_mappers(
            bmp_to_data_mapping, cabinat_frame_to_connection_mapping,
            bmp_connection_data, udp_bmp_connection)
        connections.append(udp_bmp_connection)
    else:
        # handle the possible multiple bmp connections
        for bmp_string in bmp_ip_addresses:
            # split the ipadress from the board scope and define the dict
            # accordingly
            bmp_connection_data = _utils.sort_out_bmp_string(bmp_string)
            udp_bmp_connection = UDPBMPConnection(
                remote_host=bmp_connection_data.ip_address)
            # update dictonaries
            _utils.update_mappers(
                bmp_to_data_mapping, cabinat_frame_to_connection_mapping,
                bmp_connection_data, udp_bmp_connection)
            # add connection to list of connections
            connections.append(udp_bmp_connection)

    # handle the spinnaker connection
    connections.append(UDPSpinnakerConnection(remote_host=hostname))
    # handle the boot connection
    connections.append(UDPBootConnection(remote_host=hostname))

    return Transceiver(
        connections=connections, bmp_to_bmp_data_mapping=bmp_to_data_mapping,
        cabinat_frame_to_connection_mapping=cabinat_frame_to_connection_mapping,
        shut_down_connections=True, ignore_chips=ignore_chips,
        ignore_cores=ignore_cores, max_core_id=max_core_id)


class Transceiver(object):
    """ An encapsulation of various communications with the spinnaker board.

        The methods of this class are designed to be thread-safe;\
        thus you can make multiple calls to the same (or different) methods\
        from multiple threads and expect each call to work as if it had been\
        called sequentially, although the order of returns is not guaranteed.\
        Note also that with multiple connections to the board, using multiple\
        threads in this way may result in an increase in the overall speed of\
        operation, since the multiple calls may be made separately over the\
        set of given connections.


    """

    def __init__(self, connections=None, bmp_to_bmp_data_mapping=None,
                 cabinat_frame_to_connection_mapping=None,
                 ignore_chips=None, ignore_cores=None, max_core_id=None,
                 shut_down_connections=False, n_scp_threads=16,
                 n_other_threads=16):
        """

        :param connections: An iterable of connections to the board.  If not\
                    specified, no communication will be possible until\
                    connections are found.
        :type connections: iterable of\
                    :py:class:`spinnman.connections.abstract_connection.AbstractConnection`
        :param bmp_to_bmp_data_mapping: dictonary containing the board mapping
                    used via each bmp connection
        :type bmp_to_bmp_data_mapping: dictonary with bmp-ipaddress as key and
                    a int where each bit says if the board is covered in scope
        :param ignore_chips: An optional set of chips to ignore in the\
                    machine.  Requests for a "machine" will have these chips\
                    excluded, as if they never existed.  The processor_ids of\
                    the specified chips are ignored.
        :type ignore_chips: :py:class:`spinnman.model.core_subsets.CoreSubsets`
        :param ignore_cores: An optional set of cores to ignore in the\
                    machine.  Requests for a "machine" will have these cores\
                    excluded, as if they never existed.
        :type ignore_cores: :py:class:`spinnman.model.core_subsets.CoreSubsets`
        :param max_core_id: The maximum core id in any discovered machine.\
                    Requests for a "machine" will only have core ids up to and\
                    including this value.
        :type max_core_id: int
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board, or if no connections to the\
                    board can be found (if connections is None)
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException: If a\
                    packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """

        # Place to keep the current machine
        self._machine = None
        self._ignore_chips = ignore_chips
        self._ignore_cores = ignore_cores
        self._max_core_id = max_core_id

        # Place to keep the known chip information
        self._chip_info = dict()

        # sort out thread pools for the entire transciever
        self._scp_message_thread_pool = ThreadPool(processes=n_scp_threads)
        self._other_thread_pool = ThreadPool(processes=n_other_threads)

        # Update the lists of connections
        if connections is None:
            connections = list()
        self.connections_to_not_shut_down = set()
        if not shut_down_connections:
            self.connections_to_not_shut_down = set(connections)
        self._boot_connection = None

        # bmp connectors data structures
        self._bmp_connections = dict()
        self._bmp_connection_to_bmp_data_mapping = bmp_to_bmp_data_mapping
        self._cabinat_frame_to_connection_mapping = \
            cabinat_frame_to_connection_mapping
        self._receiving_connections = dict()
        self._sending_connections = dict()

        # Update the listeners for the given connections
        self._connection_queues = dict()

        # The nearest neighbour start id and lock
        self._next_nearest_neighbour_id = 2
        self._next_nearest_neighbour_condition = Condition()

        # A lock against multiple flood fill writes - needed as SCAMP cannot
        # cope with this
        self._flood_write_lock = Condition()

        # A lock against single chip executions (entry is (x, y))
        # The condition should be acquired before the locks are
        # checked or updated
        # The write lock condition should also be acquired to avoid a flood
        # fill during an individual chip execute
        self._chip_execute_locks = dict()
        self._chip_execute_lock_condition = Condition()
        self._n_chip_execute_locks = 0

        # sort out the connections so that they are all valid and identified
        self._sort_out_connections(connections)
        self._update_connection_queues()
        self._check_udp_bmp_connections()
        self.power_off_machine()

    def _sort_out_connections(self, connections):
        for connection in connections:

            # validate that we're using udp connections
            if not isinstance(connection, AbstractUDPConnection):
                raise exceptions.SpinnmanInvalidParameterException(
                    "this connection format is currently not supported in this"
                    "version of SpinnMan", "", "")
            else:
                self._sort_out_udp_connections(connection)

    def _sort_out_udp_connections(self, connection):
        """
        looks though the udp conenctions and sorts them into bmp, scamp and
        other types of connections
        :param connection: the connection to check for its type of
        :return:
        """
        # locate the only boot connection
        if isinstance(connection, UDPBootConnection):
            if self._boot_connection is not None:
                raise exceptions.SpinnmanInvalidParameterException(
                    "this version of Spinnman only supports one boot"
                    "connection", "", "")
            else:
                self._boot_connection = connection

        # locate the bmp connections
        if isinstance(connection, UDPBMPConnection):
            self._bmp_connections[connection.local_port] = connection

        # check if connection is a receive or sender or both connection
        # check if the connection can receive and is not using a already
        # used port
        if connection.local_port in self._receiving_connections:
            raise exceptions.SpinnmanInvalidParameterException(
                "two connections are listening to packets from the "
                "same port. This is deemed an error", "", "")
        else:
            self._receiving_connections[connection.local_port] = connection

        # check if the connection can send and is not using a already
        # used port
        if (connection.can_send and
                not isinstance(connection, UDPBootConnection)):
            if connection.remote_port in self._sending_connections:
                raise exceptions.SpinnmanInvalidParameterException(
                    "two connections are listening to packets from the "
                    "same port. This is deemed an error", "", "")
            else:
                key = (connection.remote_ip_address, connection.remote_port)
                self._sending_connections[key] = connection

    def _check_udp_bmp_connections(self):
        """
        helper method that check that the bmp connections are actually connected
        to bmps
        :return: None
        :raises SpinnmanUnexpectedResponseCodeException: when the connection is
        not linked to a bmp
        """
        # check that the udp bmp connection is actually connected to a bmp
        #  via the sver command
        for connection_port in self._bmp_connections:
            # try to send a bmp sver to check if it responds as expected
            try:
                response = self.send_scp_message(
                    SCPBMPVersionRequest(board=0),
                    connection=self._bmp_connections[connection_port])

                if (response.version_info.name != _BMP_NAME or
                        response.version_info.version_number not in _BMP_VERSIONS):
                    raise exceptions.SpinnmanUnexpectedResponseCodeException(
                        operation="calling bmp connection with sver",
                        command="",
                        response=
                        "got the wrong version information. recieved "
                        "{}:{} instead of {}:{}".format(
                            response.version_info.name,
                            response.version_info.version_number,
                            _BMP_NAME, _BMP_VERSIONS),)
            # if it fails to respond due to timeout, maybe that the connection
            # isnt valid
            except exceptions.SpinnmanTimeoutException:
                raise exceptions.SpinnmanException(
                    "It seems that your bmp connection is not responding, "
                    "please check that its connected and that the cfg file has "
                    "been configured correctly")

    def _check_scamp_connections(self, retries=3):
        """
        checks that the discovered scamp connections are acutally usable
        :return: None
        """
        invalid_connections = dict()
        for connection_key in self._sending_connections:
            connection = self._sending_connections[connection_key]
            if isinstance(connection, UDPSpinnakerConnection):
                self._try_sver_though_scamp_connection(
                    connection, connection_key, retries, invalid_connections)
        for connection_key in invalid_connections:
            self._sending_connections.pop(connection_key)
            self._connection_queues.pop(invalid_connections[connection_key])

    def _try_sver_though_scamp_connection(
            self, connection, connection_key, retries, invalid_connections):
        """
        tryies to query chip 0 0  from whatever chip this connection is conencted
         to
        :param connection: the connection to use for querying chip 0 0
        :param connection_key: the connection key used in invalid_conenctions
        :param retries: how many attemtps to do before giving up
        :param invalid_connections: the list of invalid conenctions to remove
        :return: None
        """
        response = None
        current_retries = retries
        while response is None and current_retries > 0:
            try:
                response = self.send_scp_message(
                    message=SCPVersionRequest(x=0, y=0, p=0),
                    connection=connection)
            except exceptions.SpinnmanTimeoutException:
                invalid_connections[connection_key] = connection  # drop connection
            except exceptions.SpinnmanUnexpectedResponseCodeException:
                current_retries -= 1
            except exceptions.SpinnmanIOException:
                invalid_connections[connection_key] = connection  # drop connection
        if (response is not None and
                (response.version_info.name != _SCAMP_NAME or
                 response.version_info.version_number != _SCAMP_VERSION)):
            raise exceptions.SpinnmanUnexpectedResponseCodeException(
                "version", "The version returned from a scamp connection is not"
                           " recongised!, please fix and try again", response)

    def _get_chip_execute_lock(self, x, y):
        """ Get a lock for executing an executable on a chip
        """

        # Check if there is a lock for the given chip
        self._chip_execute_lock_condition.acquire()
        if not (x, y) in self._chip_execute_locks:
            chip_lock = Condition()
            self._chip_execute_locks[(x, y)] = chip_lock
        else:
            chip_lock = self._chip_execute_locks[(x, y)]
        self._chip_execute_lock_condition.release()

        # Get the lock for the chip
        chip_lock.acquire()

        # Increment the lock counter (used for the flood lock)
        self._chip_execute_lock_condition.acquire()
        self._n_chip_execute_locks += 1
        self._chip_execute_lock_condition.release()

    def _release_chip_execute_lock(self, x, y):
        """ Release the lock for executing on a chip
        """

        # Get the chip lock
        self._chip_execute_lock_condition.acquire()
        chip_lock = self._chip_execute_locks[(x, y)]

        # Release the chip lock
        chip_lock.release()

        # Decrement the lock and notify
        self._n_chip_execute_locks -= 1
        self._chip_execute_lock_condition.notify_all()
        self._chip_execute_lock_condition.release()

    def _get_flood_execute_lock(self):
        """ Get a lock for executing a flood fill of an executable
        """

        # Get the execute lock all together, so nothing can access it
        self._chip_execute_lock_condition.acquire()

        # Wait until nothing is executing
        while self._n_chip_execute_locks > 0:
            self._chip_execute_lock_condition.wait()

            # When nothing is executing, we can return here

    def _release_flood_execute_lock(self):
        """ Release the lock for executing a flood fill
        """

        # Release the execute lock
        self._chip_execute_lock_condition.release()

    def _update_connection_queues(self):
        """ Creates and deletes queues of connections depending upon what\
            connections are now available

        :return: Nothing is returned
        :rtype: None
        :raise None: No known exceptions are raised
        """
        for connection in self._sending_connections.values():
            # Only add a new _queue if there isn't one currently
            if connection not in self._connection_queues:
                self._connection_queues[connection] = \
                    _ConnectionQueue(connection)
                self._connection_queues[connection].start()
        if self._boot_connection not in self._connection_queues:
            self._connection_queues[self._boot_connection] = \
                _ConnectionQueue(self._boot_connection)
            self._connection_queues[self._boot_connection].start()

    def _find_best_connection_queue(self, message, connection=None):
        """ Finds the best connection _queue to use to send a message

        :param message: The message to send
        :type message: One of:
                    * :py:class:`spinnman.messages.sdp.sdp_message.SDPMessage`
                    * \
                    :py:class:`spinnman.messages.scp.abstract_scp_request.AbstractSCPRequest`
                    * \
                    :py:class:`spinnman.messages.multicast_message.MulticastMessage`
                    * \
                    :py:class:`spinnman.messages.spinnaker_boot.spinnaker_boot_message.SpinnakerBootMessage`
        :param connection: An optional connection to use
        :type connection:\
                    :py:class:`spinnman.connections.abstract_connection.AbstractConnection`
        :return: The best connection queue
        :rtype:\
                    :py:class:`spinnman.connections._connection_queue.ConnectionQueue`
        :raise spinnman.exceptions.SpinnmanUnsupportedOperationException: If\
                    no connection can send the type of message given
        """
        best_connection_queue = None

        # If a connection is given, use it
        if connection is not None:
            best_connection_queue = self._connection_queues[connection]

            # If the connection doesn't support the message,
            # reject the connection, and allow the error to be raised later
            if not connection.supports_sends_message(message):
                best_connection_queue = None
        else:

            # Find the least congested way that supports the message type
            connections = list(self._sending_connections.values())
            connections.append(self._boot_connection)
            best_connection_queue_size = None
            for connection in connections:
                if connection.supports_sends_message(message):
                    connection_queue = self._connection_queues[connection]
                    connection_queue_size = connection_queue.queue_length
                    if (best_connection_queue is None or
                        connection_queue_size <
                            best_connection_queue_size):
                        best_connection_queue = connection_queue
                        best_connection_queue_size = connection_queue_size

        # If no supported queue was found, raise an exception
        if best_connection_queue is None:
            raise exceptions.SpinnmanUnsupportedOperationException(
                "Sending and receiving {}".format(message.__class__))

        return best_connection_queue

    def send_eieio_command_message(self, message, connection=None):
        """ Sends a EIEIO command message using one of the connections.

        :param message: The message to send
        :type message: EIEIOCommandMessage
        :param connection: An optional connection to use
        :type connection:\
                    :py:class:`spinnman.connections.abstract_connection.AbstractConnection`
        :return: None
        """
        if isinstance(message, EIEIOCommandMessage):
            self._send_message(message, False, connection)
        else:
            raise exceptions.SpinnmanUnsupportedOperationException(
                "Sending and receiving {}".format(message.__class__))

    def send_sdp_message(self, message, connection=None):
        """ Sends a EIEIO command message using one of the connections.

        :param message: The message to send
        :type message: SDPMessage
        :param connection: An optional connection to use
        :type connection:\
                    :py:class:`spinnman.connections.abstract_connection.AbstractConnection`
        :return: None
        """
        if isinstance(message, SDPMessage):
            self._send_message(message, False, connection)
        else:
            raise exceptions.SpinnmanUnsupportedOperationException(
                "Sending and receiving {}".format(message.__class__))

    def _send_message(self, message, response_required, connection=None,
                      timeout=1, get_callback=False):
        """ Sends a message using one of the connections, and gets a response\
            if requested

        :param message: The message to send
        :type message: One of:
                    * :py:class:`spinnman.messages.sdp.sdp_message.SDPMessage`
                    * \
                    :py:class:`spinnman.messages.scp.abstract_scp_request.AbstractSCPRequest`
                    * \
                    :py:class:`spinnman.messages.multicast_message.MulticastMessage`
                    * \
                    :py:class:`spinnman.messages.spinnaker_boot.spinnaker_boot_message.SpinnakerBootMessage`
        :param response_required: True if a response is required, False\
                    otherwise
        :type response_required: bool
        :param connection: An optional connection to use
        :type connection:\
                    :py:class:`spinnman.connections.abstract_connection.AbstractConnection`
        :param timeout: Timeout to use when waiting for a response
        :type timeout: int
        :param get_callback: Determines if the function should return the\
                    callback which can be used to send messages asynchronously
        :type get_callback: bool
        :return:
                    * If get_callback is False, and response_required is True,\
                      the response
                    * If get_callback is False, and response_required is\
                      False, None
                    * If get_callback is True, the callback
        :rtype:
                    * If get_callback is False, and response_required is True,
                      and the message type is AbstractSCPRequest then\
                      :py:class:`spinnman.messages.scp.abstract_scp_response.AbstractSCPResponse`
                    * If get_callback is False, and response_required is True,
                      then the same type as the message
                    * If get_callback is False, and response_required is False,
                      then None
                    * If get_callback is True, then\
                      :py:class:`spinnman.connections._message_callback._MessageCallback`
        :raise spinnman.exceptions.SpinnmanTimeoutException: If there is a\
                    timeout before a message is received
        :raise spinnman.exceptions.SpinnmanInvalidParameterException: If one\
                    of the fields of the received message is invalid
        :raise spinnman.exceptions.SpinnmanInvalidPacketException:
                    * If the message is not one of the indicated types
                    * If a packet is received is not a valid response
        :raise spinnman.exceptions.SpinnmanUnsupportedOperationException: If\
                    no connection can send the type of message given
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    sending the message or receiving the response
        """
        best_connection_queue = self._find_best_connection_queue(message,
                                                                 connection)
        logger.debug("Sending message with {}".format(best_connection_queue))

        # Send the message with the best queue
        if get_callback or not response_required:
            return best_connection_queue.send_message_non_blocking(
                message, response_required, timeout)
        return best_connection_queue.send_message(
            message, response_required, timeout)

    def send_scp_message(
            self, message, retry_codes=(
                SCPResult.RC_P2P_TIMEOUT, SCPResult.RC_TIMEOUT,
                SCPResult.RC_LEN),
            n_retries=10, timeout=1, connection=None):
        """ Sends an SCP message, and gets a response

        :param message: The message to send
        :type message:\
                    :py:class:`spinnman.messages.scp.abstract_scp_request.AbstractSCPRequest`
        :param retry_codes: The response codes which will result in a\
                    retry if received as a response
        :type retry_codes: iterable of\
                    :py:class:`spinnman.messages.scp.scp_result.SCPResult`
        :param n_retries: The number of times to retry when a retry code is\
                received
        :type n_retries: int
        :param timeout: The timeout to use when receiving a response
        :type timeout: int
        :param connection: The connection to use
        :type connection:\
                    :py:class:`spinnman.connections.abstract_connection.AbstractConnection`
        :return: The received response, or the callback if get_callback is True
        :rtype:\
                    :py:class:`spinnman.messages.scp.abstract_scp_response.AbstractSCPResponse`
        :raise spinnman.exceptions.SpinnmanTimeoutException: If there is a\
                    timeout before a message is received
        :raise spinnman.exceptions.SpinnmanInvalidParameterException: If one\
                    of the fields of the received message is invalid
        :raise spinnman.exceptions.SpinnmanInvalidPacketException:
                    * If the message is not a recognized packet type
                    * If a packet is received that is not a valid response
        :raise spinnman.exceptions.SpinnmanUnsupportedOperationException: If\
                    no connection can send the type of message given
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    sending the message or receiving the response
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    the response is not one of the expected codes
        """
        thread = SCPMessageInterface(
            transceiver=self, message=message, retry_codes=retry_codes,
            n_retries=n_retries, timeout=timeout, connection=connection)
        self._scp_message_thread_pool.apply_async(thread.run)
        return thread.get_response()

    def _make_chip(self, chip_details):
        """ Creates a chip from a ChipInfo structure

        :param chip_details: The ChipInfo structure to create the chip\
                    from
        :type chip_details: \
                    :py:class:`spinnman.model.chip_info.ChipInfo`
        :return: The created chip
        :rtype: :py:class:`spinn_machine.chip.Chip`
        """

        # Create the processor list
        processors = list()
        for virtual_core_id in chip_details.virtual_core_ids:
            if (self._ignore_cores is not None and
                    self._ignore_cores.is_core(
                        chip_details.x, chip_details.y, virtual_core_id)):
                logger.debug("Ignoring core {} on chip {}, {}".format(
                             chip_details.x, chip_details.y, virtual_core_id))
                continue
            if (self._max_core_id is not None and
                    virtual_core_id > self._max_core_id):
                logger.debug("Ignoring core {} on chip {}, {} as > {}"
                             .format(chip_details.x, chip_details.y,
                                     virtual_core_id, self._max_core_id))
                continue

            processors.append(Processor(
                virtual_core_id, chip_details.cpu_clock_mhz * 1000000,
                virtual_core_id == 0))

        # Create the router - add the links later during search
        router = Router(
            links=list(), emergency_routing_enabled=False,
            clock_speed=Router.ROUTER_DEFAULT_CLOCK_SPEED,
            n_available_multicast_entries=(
                Router.ROUTER_DEFAULT_AVAILABLE_ENTRIES -
                chip_details.first_free_router_entry))

        # Create the chip
        chip = Chip(
            x=chip_details.x, y=chip_details.y, processors=processors,
            router=router, sdram=SDRAM(SDRAM.DEFAULT_SDRAM_BYTES),
            ip_address=chip_details.ip_address,
            nearest_ethernet_x=chip_details.nearest_ethernet_x,
            nearest_ethernet_y=chip_details.nearest_ethernet_y)
        return chip

    def _update_machine(self):
        """ Get the current machine status and store it
        """

        # Ask the chip at 0, 0 for details
        logger.debug("Getting details of chip 0, 0")
        response = self.send_scp_message(SCPReadMemoryRequest(
            x=0, y=0, base_address=constants.SYSTEM_VARIABLE_BASE_ADDRESS,
            size=constants.SYSTEM_VARIABLE_BYTES))
        chip_0_0_details = ChipInfo(response.data)
        self._chip_info[(0, 0)] = chip_0_0_details
        chip_0_0 = self._make_chip(chip_0_0_details)

        # Create a machine with chip 0, 0
        self._machine = Machine([chip_0_0])

        # Perform a search of the chips via the links
        search = deque([(chip_0_0, chip_0_0_details.links_available)])
        while len(search) > 0:
            (chip, links) = search.pop()

            # Examine the links of the chip to find the next chips
            for link in links:
                try:
                    logger.debug(
                        "Searching down link {} from chip {}, {}".format(
                            link, chip.x, chip.y))
                    response = self.send_scp_message(SCPReadLinkRequest(
                        x=chip.x, y=chip.y, cpu=0, link=link,
                        base_address=constants.SYSTEM_VARIABLE_BASE_ADDRESS,
                        size=constants.SYSTEM_VARIABLE_BYTES))
                    new_chip_details = ChipInfo(response.data)
                    logger.debug("Found chip {}, {}"
                                 .format(new_chip_details.x,
                                         new_chip_details.y))
                    if (self._ignore_chips is not None and
                            self._ignore_chips.is_chip(
                                new_chip_details.x, new_chip_details.y)):
                        logger.debug("Ignoring chip {}, {}"
                                     .format(new_chip_details.x,
                                             new_chip_details.y))
                        continue

                    # Standard links use the opposite link id (with ids between
                    # 0 and 5) as default
                    opposite_link_id = (link + 3) % 6

                    # Update the defaults of any existing link
                    if chip.router.is_link(opposite_link_id):
                        logger.debug("Opposite link {} found"
                                     .format(opposite_link_id))
                        opposite_link = chip.router.get_link(opposite_link_id)
                        opposite_link.multicast_default_to = link
                        opposite_link.multicast_default_from = link
                    else:

                        # If the link doesn't exist, don't set a default for
                        # this link yet
                        opposite_link_id = None

                    # Add the link to the current chip
                    new_link = Link(
                        source_x=chip.x, source_y=chip.y,
                        source_link_id=link,
                        destination_x=new_chip_details.x,
                        destination_y=new_chip_details.y,
                        multicast_default_from=opposite_link_id,
                        multicast_default_to=opposite_link_id)
                    chip.router.add_link(new_link)

                    # Add the new chip if it doesn't exist
                    if not self._machine.is_chip_at(
                            new_chip_details.x, new_chip_details.y):
                        logger.debug("Found new chip {}, {}".format(
                            new_chip_details.x, new_chip_details.y))
                        new_chip = self._make_chip(new_chip_details)
                        self._machine.add_chip(new_chip)
                        self._chip_info[(new_chip.x,
                                         new_chip.y)] = new_chip_details
                        search.append(
                            (new_chip, new_chip_details.links_available))

                except exceptions.SpinnmanUnexpectedResponseCodeException \
                        as error:

                    # If there is an error, assume the link is down
                    logger.debug("Error searching down link {}".format(link))
                    logger.debug(error)

    def discover_scamp_connections(self):
        """ Find connections to the board and store these for future use.\
            Note that connections can be empty, in which case another local\
            discovery mechanism will be used.  Note that an exception will be\
            thrown if no initial connections can be found to the board.

        :return: An iterable of discovered connections, not including the\
                    initially given connections in the constructor
        :rtype: iterable of\
                    :py:class:`spinnman.connections.abstract_connection.AbstractConnection`
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException: If a\
                    packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """

        # Currently, this only finds other UDP connections given a connection
        # that supports SCP - this is _done via the machine
        if len(self._sending_connections) == 0:
            return list()
        if self._machine is None:
            self._update_machine()

        # Find all the new connections via the machine ethernet-connected chips
        new_connections = list()
        for ethernet_connected_chip in self._machine.ethernet_connected_chips:
            key = (ethernet_connected_chip.ip_address,
                   constants.SCP_SCAMP_PORT)
            if key not in self._sending_connections.keys():
                new_connection = UDPSpinnakerConnection(
                    remote_host=ethernet_connected_chip.ip_address,
                    chip_x=ethernet_connected_chip.x,
                    chip_y=ethernet_connected_chip.y)
                new_connections.append(new_connection)
                if key in self._sending_connections.keys():
                    raise exceptions.SpinnmanInvalidParameterException(
                        "The new spinnaker connection is using a remote port "
                        "and hostname that is already in use, please adjust "
                        "this and try again ", "", "")
                else:
                    self._sending_connections[key] = new_connection

                # test receiving side of connection
                if new_connection.local_port in self._receiving_connections:
                    raise exceptions.SpinnmanInvalidParameterException(
                        "The new spinnaker connection is using a local port "
                        "that is already in use, please adjust "
                        "this and try again ", "", "")
                else:
                    self._receiving_connections[new_connection.local_port] = \
                        new_connection

        # Update the connection queues after finding new connections
        self._update_connection_queues()
        self._check_scamp_connections()
        logger.info(self._machine.cores_and_link_output_string())
        return new_connections

    def get_connections(self, include_boot_connection=False):
        """ Get the currently known connections to the board, made up of those\
            passed in to the transceiver and those that are discovered during\
            calls to discover_connections.  No further discovery is done here.

        :param include_boot_connection: this parameter signals if the returned\
               list of connections should include also the boot connection to\
               SpiNNaker
        :type include_boot_connection: bool
        :return: An iterable of connections known to the transceiver
        :rtype: iterable of\
                    :py:class:`spinnman.connections.abstract_connection.AbstractConnection`
        :raise None: No known exceptions are raised
        """
        connections = self._sending_connections.values()
        if include_boot_connection:
            connections.append(self._boot_connection)
        return connections

    def get_machine_dimensions(self):
        """ Get the maximum chip x-coordinate and maximum chip y-coordinate of\
            the chips in the machine

        :return: The dimensions of the machine
        :rtype: :py:class:`spinnman.model.machine_dimensions.MachineDimensions`
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException: If a\
                    packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        if self._machine is None:
            self._update_machine()
        return MachineDimensions(self._machine.max_chip_x,
                                 self._machine.max_chip_y)

    def get_machine_details(self):
        """ Get the details of the machine made up of chips on a board and how\
            they are connected to each other.

        :return: A machine description
        :rtype: :py:class:`spinn_machine.machine.Machine`
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException: If a\
                    packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        if self._machine is None:
            self._update_machine()
        return self._machine

    def is_connected(self, connection=None):
        """ Determines if the board can be contacted

        :param connection: The connection which is to be tested.  If none,\
                    all connections will be tested, and the board will be\
                    considered to be connected if any one connection works.
        :type connection:\
                    :py:class:`spinnman.connections.abstract_connection.AbstractConnection`
        :return: True if the board can be contacted, False otherwise
        :rtype: bool
        :raise None: No known exceptions are raised
        """
        if connection is not None:
            if connection.is_connected():
                return True
            return False
        else:
            for connection in self._sending_connections.values():
                if connection.is_connected():
                    return True
            return False

    def get_scamp_version(self, n_retries=3, timeout=1, chip_x=0, chip_y=0):
        """ Get the version of scamp which is running on the board

        :param n_retries: The number of times to retry getting the version
        :type n_retries: int
        :param timeout: The timeout for each retry in seconds
        :type timeout: int
        :param chip_x: the chip's x coordinate to query for scamp version
        :type chip_x: int
        :param chip_y: the chip's y coordinate to query for scamp version
        :return: The version identifier
        :rtype: :py:class:`spinnman.model.version_info.VersionInfo`
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidParameterException: If the\
                    timeout is less than 1
        :raise spinnman.exceptions.SpinnmanTimeoutException: If none of the\
                    retries resulted in a response before the timeout\
                    (suggesting that the board is not booted)
        """
        response = self.send_scp_message(
            message=SCPVersionRequest(x=chip_x, y=chip_y, p=0),
            n_retries=n_retries, timeout=timeout)
        return response.version_info

    def boot_board(
            self, board_version, max_machines_x_dimension,
            max_machines_y_dimension, number_of_boards):
        """ Attempt to boot the board.  No check is performed to see if the\
            board is already booted.

        :param board_version: The version of the board e.g. 3 for a SpiNN-3\
                    board or 5 for a SpiNN-5 board.
        :type board_version: int
        :param number_of_boards: the number of boards that this machine is made
        out of
        :type number_of_boards: int
        :param max_machines_x_dimension: the max size dimension this machine
                when booted should be in the x dimension
        :type max_machines_x_dimension: int or None
        :param max_machines_y_dimension: the max size dimension this machine
                when booted should be in the y dimension
        :type max_machines_y_dimension: int
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanInvalidParameterException: If the\
                    board version is not known
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        """
        logger.debug("Attempting to boot version {} board".format(
            board_version))
        boot_messages = SpinnakerBootMessages(
            board_version,
            max_machines_x_dimension=max_machines_x_dimension,
            max_machines_y_dimension=max_machines_y_dimension,
            number_of_boards=number_of_boards)
        for boot_message in boot_messages.messages:
            self._send_message(boot_message, response_required=False)

    def ensure_board_is_ready(
            self, board_version, number_of_boards,
            max_machines_x_dimension=None, max_machines_y_dimension=None,
            n_retries=5):
        """ Ensure that the board is ready to interact with this version\
            of the transceiver.  Boots the board if not already booted and\
            verifies that the version of SCAMP running is compatible with\
            this transceiver.

        :param board_version: The version of the board e.g. 3 for a SpiNN-3\
                    board or 5 for a SpiNN-5 board.
        :type board_version: int
        :param max_machines_x_dimension: the max size dimension this machine
                when booted should be in the x dimension
        :type max_machines_x_dimension: int or None
        :param max_machines_y_dimension: the max size dimension this machine
                when booted should be in the y dimension
        :type max_machines_y_dimension: int
        :param number_of_boards: the number of boards that this machine is
                    constructed out of
        :type number_of_boards: int
        :param n_retries: The number of times to retry booting
        :type n_retries: int
        :return: The version identifier
        :rtype: :py:class:`spinnman.model.version_info.VersionInfo`
        :raise: spinnman.exceptions.SpinnmanIOException:
                    * If there is a problem booting the board
                    * If the version of software on the board is not\
                      compatible with this transceiver
        """

        # if the machine sizes not been given, calculate from assumption
        if (max_machines_x_dimension is None or
                max_machines_y_dimension is None):
            sizes = _utils.get_idead_size(number_of_boards, board_version)
            max_machines_x_dimension = sizes['x']
            max_machines_y_dimension = sizes['y']

        # try to get a scamp version
        logger.info("going to try to boot the machine with scamp")
        version_info = self._try_to_find_scamp_and_boot(
            n_retries, board_version, number_of_boards,
            max_machines_x_dimension, max_machines_y_dimension)
        if version_info is None:
            logger.info(
                "failed to boot machine with scamp, trying to power on machine")
            # start by powering up each bmp connection
            self._try_power_up_machine()
            logger.info("going to try to boot the machine with scamp")
            # retry to get a scamp version
            version_info = self._try_to_find_scamp_and_boot(
                n_retries, board_version, number_of_boards,
                max_machines_x_dimension, max_machines_y_dimension)

        # verify that the version is the expected one for this trnasciever
        if version_info is None:
            raise exceptions.SpinnmanIOException("Could not boot the board")
        if (version_info.name != _SCAMP_NAME or
                version_info.version_number != _SCAMP_VERSION):
            raise exceptions.SpinnmanIOException(
                "The board is currently booted with {}"
                " {} which is incompatible with this transceiver, "
                "required version is {} {}".format(
                    version_info.name, version_info.version_number,
                    _SCAMP_NAME, _SCAMP_VERSION))
        else:
            if self._machine is None:
                self._update_machine()
            logger.info("successfully booted the machine with scamp")
        return version_info

    def _try_power_up_machine(self):
        """
        run though the bmp conenctions and power them up one by one
        :return:
        """
        for bmp_connection_port in self._bmp_connections:
            bmp_connection = self._bmp_connections[bmp_connection_port]
            bmp_connection_data = \
                self._bmp_connection_to_bmp_data_mapping[bmp_connection]
            self.power_on(
                bmp_connection_data.boards, bmp_connection_data.cabinate,
                bmp_connection_data.frame)

    def _try_to_find_scamp_and_boot(
            self, tries_to_go, board_version, number_of_boards,
            max_machines_x_dimension, max_machines_y_dimension):
        """
        tries to locate a version of scamp by booting scamp
        :param tries_to_go: how many attemtps should be supported
        :param board_version: what version of boards are being used to
        represnet the machine
        :param number_of_boards: the number of boards that this spinnaker
        machine is built out of
        :param max_machines_x_dimension: the max size in x dimension this
        machine can be
        :param max_machines_y_dimension:the max size in y dimension this
        machine can be
        :return: version_info
        :raises SpinnmanUnexpectedResponseCodeException: if there is some
        strnage response from the machine
        """
        version_info = None
        current_tries_to_go = tries_to_go
        while version_info is None and current_tries_to_go > 0:
            try:
                version_info = self.get_scamp_version()
            except exceptions.SpinnmanTimeoutException:
                self.boot_board(
                    board_version, max_machines_x_dimension,
                    max_machines_y_dimension, number_of_boards)
                current_tries_to_go -= 1
            except exceptions.SpinnmanIOException:
                raise exceptions.SpinnmanUnexpectedResponseCodeException(
                    "We currently cannot communicate with your board, please "
                    "rectify this, and try again", "", "")
        # boot has been sent, and 0 0 is up and running, but there will need to
        # be a delay whilst all the other chips complete boot.
        if version_info is not None:
            current_tries_to_go = tries_to_go
            version_info = self._wait_till_important_chips_are_fully_booted(
                max_machines_x_dimension, max_machines_y_dimension,
                current_tries_to_go)
        return version_info

    def _wait_till_important_chips_are_fully_booted(
            self, max_machines_x_dimension, max_machines_y_dimension,
            current_tries_to_go):
        """
        locate what it decides are important chips and waits till they are
        booted
        :param max_machines_x_dimension: the max dimension of the machine in the
        x axis
        :param max_machines_y_dimension: the max dimension of the machine in the
        y axis
        :return: the version info of the last important chip
        """
        version_info = None
        found_version_info = None
        # check if the machine is wrap arounds
        chips_to_check = list()
        if self._check_if_machine_has_wrap_arounds():
            # locate the set of middle chips that need to be checked
            # before boot is finished
            chips_to_check = _utils.locate_middle_chips_to_query(
                max_machines_x_dimension, max_machines_y_dimension,
                self._ignore_chips)
        else:
            # locate the top most corner chip
            chips_to_check.append(self._machine.get_chip_at(
                max_machines_x_dimension - 1, max_machines_y_dimension - 1))

        # check each chip required to ensure boot is finished
        for chip_to_check in chips_to_check:
            version_info = None
            while version_info is None and current_tries_to_go > 0:
                try:
                    version_info = self.get_scamp_version(
                        chip_x=chip_to_check['x'],
                        chip_y=chip_to_check['y'])
                    if version_info is not None:
                        found_version_info = version_info
                except exceptions.SpinnmanTimeoutException:
                    # back off a little and try again
                    current_tries_to_go -= 1
                    time.sleep(4.0)
                except exceptions.SpinnmanUnexpectedResponseCodeException:
                    # back off a little and try again
                    current_tries_to_go -= 1
                    time.sleep(4.0)
                except exceptions.SpinnmanIOException:
                    raise exceptions.SpinnmanUnexpectedResponseCodeException(
                        "We currently cannot communicate with your board, "
                        "please rectify this, and try again", "", "")
            if version_info is None:
                logger.warn(
                    "we could not get a sver from chip {}:{}. It may not be "
                    "operating properly".format(
                        chip_to_check['x'], chip_to_check['y']))
        return found_version_info

    def _check_if_machine_has_wrap_arounds(self):
        """
        queries the machine's 0 0  chip's links to ensure if the machine is
        acutally a torioid and thus has wrap around links or is a flat fabric
        :return: true if a wraparound torioud, false otherwise
         :rtype: bool
        """
        left_wrap_around = False
        try:
            # try the left and then bottom link
            self.send_scp_message(SCPReadLinkRequest(
                x=0, y=0, cpu=0, link=3,
                base_address=constants.SYSTEM_VARIABLE_BASE_ADDRESS,
                size=constants.SYSTEM_VARIABLE_BYTES))
            left = True
            self.send_scp_message(SCPReadLinkRequest(
                x=0, y=0, cpu=0, link=4,
                base_address=constants.SYSTEM_VARIABLE_BASE_ADDRESS,
                size=constants.SYSTEM_VARIABLE_BYTES))
            return True
        except exceptions.SpinnmanUnexpectedResponseCodeException:
            # if the left wrap around works, but bottom does not, then some
            # sort of wrapa round exists, better to be save and say it does
            if left_wrap_around:
                return True
            else:
                # left doesnt exist, but not tested bottom
                try:
                    self.send_scp_message(SCPReadLinkRequest(
                        x=0, y=0, cpu=0, link=4,
                        base_address=constants.SYSTEM_VARIABLE_BASE_ADDRESS,
                        size=constants.SYSTEM_VARIABLE_BYTES))
                    # some sort of wrap around exists, better be save and say
                    # there is a wrap around
                    return True
                except exceptions.SpinnmanUnexpectedResponseCodeException:
                    return False

    def get_cpu_information(self, core_subsets=None):
        """ Get information about the processors on the board

        :param core_subsets: A set of chips and cores from which to get\
                    the information.  If not specified, the information from\
                    all of the cores on all of the chips on the board are\
                    obtained
        :type core_subsets: :py:class:`spinnman.model.core_subsets.CoreSubsets`
        :return: An iterable of the cpu information for the selected cores, or\
                    all cores if core_subsets is not specified
        :rtype: iterable of :py:class:`spinnman.model.cpu_info.CPUInfo`
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If chip_and_cores contains invalid items
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        # Ensure that the information about each chip is present
        if self._machine is None:
            self._update_machine()

        # Get all the cores if the subsets are not given
        if core_subsets is None:
            core_subsets = CoreSubsets()
            for chip_info in self._chip_info.itervalues():
                x = chip_info.x
                y = chip_info.y
                for p in chip_info.virtual_core_ids:
                    core_subsets.add_processor(x, y, p)

        # Go through the requested chips
        callbacks = list()
        callback_coordinates = list()
        for core_subset in core_subsets:
            x = core_subset.x
            y = core_subset.y

            if not (x, y) in self._chip_info:
                raise exceptions.SpinnmanInvalidParameterException(
                    "x, y", "{}, {}".format(x, y),
                    "Not a valid chip on the current machine")
            chip_info = self._chip_info[(x, y)]

            for p in core_subset.processor_ids:
                if p not in chip_info.virtual_core_ids:
                    raise exceptions.SpinnmanInvalidParameterException(
                        "p", p, "Not a valid core on chip {}, {}".format(
                            x, y))
                base_address = (chip_info.cpu_information_base_address +
                                (constants.CPU_INFO_BYTES * p))
                callbacks.append(SCPMessageInterface(
                    self, SCPReadMemoryRequest(
                        x, y, base_address, constants.CPU_INFO_BYTES)))
                callback_coordinates.append((x, y, p))

        # Start all the callbacks (not done before to ensure that no errors
        # occur first
        for callback in callbacks:
            self._scp_message_thread_pool.apply_async(callback.run)

        # Gather the results
        for callback, (x, y, p) in zip(callbacks, callback_coordinates):
            yield CPUInfo(x, y, p, callback.get_response().data)

    def get_user_0_register_address_from_core(self, x, y, p):
        """Get the address of user 0 for a given processor on the board

        :param x: the x-coordinate of the chip containing the processor
        :param y: the y-coordinate of the chip containing the processor
        :param p: The id of the processor to get the user 0 address from
        :type x: int
        :type y: int
        :type p: int
        :return:The address for user 0 register for this processor
        :rtype: int
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If x, y, p is not a valid processor
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        # Ensure that the information about each chip is present
        if self._machine is None:
            self._update_machine()

        # check the chip exists in the infos
        if not (x, y) in self._chip_info:
            raise exceptions.SpinnmanInvalidParameterException(
                "x, y", "{}, {}".format(x, y),
                "Not a valid chip on the current machine")

        # collect the chip info for the associated chip
        chip_info = self._chip_info[(x, y)]

        # check that p is a valid processor for this chip
        if p not in chip_info.virtual_core_ids:
            raise exceptions.SpinnmanInvalidParameterException(
                "p", str(p), "Not a valid core on chip {}, {}".format(x, y))

        # locate the base address for this chip info
        base_address = (chip_info.cpu_information_base_address +
                        (constants.CPU_INFO_BYTES * p))
        base_address += constants.CPU_USER_0_START_ADDRESS
        return base_address

    def get_cpu_information_from_core(self, x, y, p):
        """ Get information about a specific processor on the board

        :param x: The x-coordinate of the chip containing the processor
        :type x: int
        :param y: The y-coordinate of the chip containing the processor
        :type y: int
        :param p: The id of the processor to get the information about
        :type p: int
        :return: The cpu information for the selected core
        :rtype: :py:class:`spinnman.model.cpu_info.CPUInfo`
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If x, y, p is not a valid processor
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """

        core_subsets = CoreSubsets()
        core_subsets.add_processor(x, y, p)
        return list(self.get_cpu_information(core_subsets))[0]

    def get_iobuf(self, core_subsets=None):
        """ Get the contents of the IOBUF buffer for a number of processors

        :param core_subsets: A set of chips and cores from which to get\
                    the buffers.  If not specified, the buffers from\
                    all of the cores on all of the chips on the board are\
                    obtained
        :type core_subsets: :py:class:`spinnman.model.core_subsets.CoreSubsets`
        :return: An iterable of the buffers, which may not be in the order\
                    of core_subsets
        :rtype: iterable of :py:class:`spinnman.model.io_buffer.IOBuffer`
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If chip_and_cores contains invalid items
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        # Ensure that the information about each chip is present
        if self._machine is None:
            self._update_machine()

        # Get CPU Information for the requested chips
        cpu_information = self.get_cpu_information(core_subsets)

        # Go through the requested chips
        callbacks = list()
        for cpu_info in cpu_information:
            chip_info = self._chip_info[(cpu_info.x, cpu_info.y)]
            iobuf_bytes = chip_info.iobuf_size

            thread = IOBufInterface(
                self, cpu_info.x, cpu_info.y, cpu_info.p,
                cpu_info.iobuf_address, iobuf_bytes,
                self._scp_message_thread_pool)
            self._other_thread_pool.apply_async(thread.run)
            callbacks.append(thread)

        # Gather the results
        for callback in callbacks:
            yield callback.get_iobuf()

    def get_iobuf_from_core(self, x, y, p):
        """ Get the contents of IOBUF for a given core

        :param x: The x-coordinate of the chip containing the processor
        :type x: int
        :param y: The y-coordinate of the chip containing the processor
        :type y: int
        :param p: The id of the processor to get the IOBUF for
        :type p: int
        :return: An IOBUF buffer
        :rtype: :py:class:`spinnman.model.io_buffer.IOBuffer`
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If chip_and_cores contains invalid items
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        core_subsets = CoreSubsets()
        core_subsets.add_processor(x, y, p)
        return self.get_iobuf(core_subsets).next()

    def get_core_state_count(self, app_id, state):
        """ Get a count of the number of cores which have a given state

        :param app_id: The id of the application from which to get the count.
        :type app_id: int
        :param state: The state count to get
        :type state: :py:class:`spinnman.model.cpu_state.CPUState`
        :return: A count of the cores with the given status
        :rtype: int
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If state is not a valid status
                    * If app_id is not a valid application id
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        response = self.send_scp_message(SCPCountStateRequest(app_id, state))
        return response.count

    def execute(self, x, y, processors, executable, app_id, n_bytes=None):
        """ Start an executable running on a single core

        :param x: The x-coordinate of the chip on which to run the executable
        :type x: int
        :param y: The y-coordinate of the chip on which to run the executable
        :type y: int
        :param processors: The cores on the chip on which to run the\
                    application
        :type processors: iterable of int
        :param executable: The data that is to be executed.  Should be one of\
                    the following:
                    * An instance of AbstractDataReader
                    * A bytearray
        :type executable:\
                    :py:class:`spinnman.data.abstract_data_reader.AbstractDataReader`\
                    or bytearray
        :param app_id: The id of the application with which to associate the\
                    executable
        :type app_id: int
        :param n_bytes: The size of the executable data in bytes.  If not\
                    specified:
                        * If data is an AbstractDataReader, an error is raised
                        * If data is a bytearray, the length of the bytearray\
                          will be used
                        * If data is an int, 4 will be used
        :type n_bytes: int
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException:
                    * If there is an error communicating with the board
                    * If there is an error reading the executable
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If x, y, p does not lead to a valid core
                    * If app_id is an invalid application id
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """

        # Lock against updates
        self._get_chip_execute_lock(x, y)

        # Write the executable
        self.write_memory(x, y, 0x67800000, executable, n_bytes)

        # Request the start of the executable
        self.send_scp_message(SCPApplicationRunRequest(app_id, x, y,
                                                       processors))

        # Release the lock
        self._release_chip_execute_lock(x, y)

    def _get_next_nearest_neighbour_id(self):
        self._next_nearest_neighbour_condition.acquire()
        next_nearest_neighbour_id = self._next_nearest_neighbour_id
        self._next_nearest_neighbour_id = \
            (self._next_nearest_neighbour_id + 1) % 127
        self._next_nearest_neighbour_condition.release()
        return next_nearest_neighbour_id

    def execute_flood(self, core_subsets, executable, app_id, n_bytes=None):
        """ Start an executable running on multiple places on the board.  This\
            will be optimized based on the selected cores, but it may still\
            require a number of communications with the board to execute.

        :param core_subsets: Which cores on which chips to start the executable
        :type core_subsets: :py:class:`spinnman.model.core_subsets.CoreSubsets`
        :param executable: The data that is to be executed.  Should be one of\
                    the following:
                    * An instance of AbstractDataReader
                    * A bytearray
        :type executable:\
                    :py:class:`spinnman.data.abstract_data_reader.AbstractDataReader`\
                    or bytearray
        :param app_id: The id of the application with which to associate the\
                    executable
        :type app_id: int
        :param n_bytes: The size of the executable data in bytes.  If not\
                    specified:
                        * If data is an AbstractDataReader, an error is raised
                        * If data is a bytearray, the length of the bytearray\
                          will be used
                        * If data is an int, 4 will be used
        :type n_bytes: int
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException:
                    * If there is an error communicating with the board
                    * If there is an error reading the executable
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If one of the specified cores is not valid
                    * If app_id is an invalid application id
                    * If a packet is received that has invalid parameters
                    * If data is an AbstractDataReader but n_bytes is not\
                      specified
                    * If data is an int and n_bytes is more than 4
                    * If n_bytes is less than 0
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        # Lock against other executables
        self._get_flood_execute_lock()

        # Flood fill the system with the binary
        self.write_memory_flood(0x67800000, executable, n_bytes)

        # Execute the binary on the cores on the chips where required
        callbacks = list()
        for core_subset in core_subsets:
            x = core_subset.x
            y = core_subset.y
            thread = SCPMessageInterface(self, SCPApplicationRunRequest(
                app_id, x, y, core_subset.processor_ids))
            self._scp_message_thread_pool.apply_async(thread.run)
            callbacks.append(thread)

        # Go through the callbacks and check that the responses are OK
        for callback in callbacks:
            callback.get_response()

        # Release the lock
        self._release_flood_execute_lock()

    @staticmethod
    def _get_bytes_to_write_and_data_to_write(data, n_bytes):
        """ Converts a given data item an a number of bytes into the data\
            and the amount of data to write

        :param data: The data to write.  Should be one of the following:
                    * An instance of AbstractDataReader
                    * A bytearray
                    * A single integer - will be written using little-endian\
                      byte ordering
        :type data:\
                    :py:class:`spinnman.data.abstract_data_reader.AbstractDataReader`\
                    or bytearray or int
        :param n_bytes: The amount of data to be written in bytes.  If not\
                    specified:
                        * If data is an AbstractDataReader, an error is raised
                        * If data is a bytearray, the length of the bytearray\
                          will be used
                        * If data is an int, 4 will be used
        :type n_bytes: int
        :return: The number of bytes and the data to write
        :rtype: (int, int)
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If data is an AbstractDataReader but n_bytes is not\
                      specified
                    * If data is an int and n_bytes is more than 4
                    * If n_bytes is less than 0
        """
        if n_bytes is not None and n_bytes < 0:
            raise exceptions.SpinnmanInvalidParameterException(
                "n_bytes", str(n_bytes), "Must be a positive integer")

        bytes_to_write = n_bytes
        data_to_write = data
        if isinstance(data, AbstractDataReader) and n_bytes is None:
            raise exceptions.SpinnmanInvalidParameterException(
                "n_bytes", "None",
                "n_bytes must be specified when data is an"
                " AbstractDataReader")
        if isinstance(data, bytearray) and n_bytes is None:
            bytes_to_write = len(data)
        if isinstance(data, (int, long)) and n_bytes is None:
            bytes_to_write = 4
        if isinstance(data, (int, long)) and n_bytes > 4:
            raise exceptions.SpinnmanInvalidParameterException(
                str(n_bytes), "n_bytes", "An integer is at most 4 bytes")
        if isinstance(data, (int, long)):
            data_to_write = bytearray(bytes_to_write)
            for i in range(0, bytes_to_write):
                data_to_write[i] = (data >> (8 * i)) & 0xFF

        return bytes_to_write, data_to_write

    def power_on(self, boards=0, cabinate=0, frame=0):
        """
        powers ona  collection of boards of a machine
        :param boards: the boards that are requested to be powered on
        :param cabinate: the cabinate id for which this request is being sent
        this is otpimal if using a bmp_connection. If being used, a frame must
        also be provided
        :param frame: the frame id for which this request is being sent.
        This is optimal if used a bmp_connection. If being used, a cabinate must
        also be provided
        :return: None
        """
        self._power(True, boards, cabinate, frame)

    def power_off_machine(self):
        """
        turns off the entire machine
        :return:
        """
        for bmp_connection_port in self._bmp_connections:
            bmp_connection_data = self._bmp_connection_to_bmp_data_mapping[
                self._bmp_connections[bmp_connection_port]]
            self.power_off(
                bmp_connection_data.boards, bmp_connection_data.cabinate,
                bmp_connection_data.frame)

    def power_off(self, boards=0, cabinate=0, frame=0):
        """
        powers off a  collection of boards of a machine
        :param boards: the boards that are requested to be powered on
        :param cabinate: the cabinate id for which this request is being sent
        this is otpimal if using a bmp_connection. If being used, a frame must
        also be provided
        :param frame: the frame id for which this request is being sent.
        This is optimal if used a bmp_connection. If being used, a cabinate must
        also be provided
        :return: None

        """
        self._power(False, boards, cabinate, frame)

    def _power(self, state, boards=0, cabinate=0, frame=0):
        """
        :param state: what vlaue to send down to pwoer (on or off)
        :param boards: the boards that are requested to be powered on
        :param cabinate: the cabinate id for which this request is being sent
        this is otpimal if using a bmp_connection. If being used, a frame must
        also be provided
        :param frame: the frame id for which this request is being sent.
        This is optimal if used a bmp_connection. If being used, a cabinate must
        also be provided
        :return: None
        """
        message = SCPPowerRequest(state=state, board=boards)
        if (cabinate, frame) in self._cabinat_frame_to_connection_mapping:
            bmp_connection = self._cabinat_frame_to_connection_mapping[
                (cabinate, frame)]
        else:
            raise exceptions.SpinnmanInvalidParameterException(
                "{}:{}".format(cabinate, frame),
                "SpinnMan cant talk to frame {} in cabinate {}"
                .format(cabinate, frame), "")
        self.send_scp_message(message, timeout=constants.BMP_POWER_ON_TIMEOUT,
                              n_retries=0, connection=bmp_connection)
        # give a 10 second sleep to ensure all boards are pwoered on properly
        #time.sleep(10.0)

    def set_led(self, led, action, board, cabinate, frame):
        """

        :param led:  Number of the LED or an iterable of LEDs to set the
        state of (0-7)
        :type led: int or iterable
        :param action:State to set the LED to, either on, off or toggle
        :type action: enum of LEDS_ACTIONS
        :param board:Specifies the board to control the LEDs of. This may
         also be an iterable of multiple boards (in the same frame). The
         command will actually be sent to the first board in the iterable.
        :type board: int or iterable
        :param cabinate: the cabinate this is targetting
        :type cabinate: int
        :param frame: the frame this is targetting
        :type frame: int
        :return: None
        """
        message = SCPBMPSetLedRequest(led, action, board)
        if (cabinate, frame) in self._cabinat_frame_to_connection_mapping:
            bmp_connection = self._cabinat_frame_to_connection_mapping[
                (cabinate, frame)]
        else:
            raise exceptions.SpinnmanInvalidParameterException(
                "{}:{}".format(cabinate, frame),
                "SpinnMan cant talk to frame {} in cabinate {}"
                .format(cabinate, frame), "")
        self.send_scp_message(message, connection=bmp_connection)

    def read_fpga_register(self, fpga_num, register, cabinate, frame, board):
        """

        :param fpga_num: FPGA number (0, 1 or 2) to communicate with.
        :type fpga_num: int
        :param register: Register address to read to (will be rounded down to
                the nearest 32-bit word boundary).
        :type register: int
        :param cabinate: cabinate: the cabinate this is targetting
        :type cabinate: int
        :param frame: the frame this is targetting
        :type frame: int
        :param board: which board to request the fpga register from
        :return: the register data
        """
        message = SCPReadFPGARegisterRequest(fpga_num, register, board)
        if (cabinate, frame) in self._cabinat_frame_to_connection_mapping:
            bmp_connection = self._cabinat_frame_to_connection_mapping[
                (cabinate, frame)]
        else:
            raise exceptions.SpinnmanInvalidParameterException(
                "{}:{}".format(cabinate, frame),
                "SpinnMan cant talk to frame {} in cabinate {}"
                .format(cabinate, frame), "")
        response = self.send_scp_message(message, connection=bmp_connection)
        return response.fpga_register

    def write_fpga_register(self, fpga_num, register, value, cabinate, frame,
                            board):
        """

        :param fpga_num: FPGA number (0, 1 or 2) to communicate with.
        :type fpga_num: int
        :param register: Register address to read to (will be rounded down to
                the nearest 32-bit word boundary).
        :type register: int
        :param value: the value to write into the fpga regsiter
        :type value: int
        :param cabinate: cabinate: the cabinate this is targetting
        :type cabinate: int
        :param frame: the frame this is targetting
        :type frame: int
        :param board: which board to request the fpga register from
        :return: None
        """
        message = ScpWriteFPGARegisterRequest(fpga_num, register, value, board)
        if (cabinate, frame) in self._cabinat_frame_to_connection_mapping:
            bmp_connection = self._cabinat_frame_to_connection_mapping[
                (cabinate, frame)]
        else:
            raise exceptions.SpinnmanInvalidParameterException(
                "{}:{}".format(cabinate, frame),
                "SpinnMan cant talk to frame {} in cabinate {}"
                .format(cabinate, frame), "")
        self.send_scp_message(message, connection=bmp_connection)

    def read_fpga_adc_data(self, board, cabinate, frame):
        """
        reads the bmp's adc data
        :param cabinate: cabinate: the cabinate this is targetting
        :type cabinate: int
        :param frame: the frame this is targetting
        :type frame: int
        :param board: which board to request the fpga register from
        :return: the fpga's adc data object
        """
        message = SCPReadADCRequest(board)
        if (cabinate, frame) in self._cabinat_frame_to_connection_mapping:
            bmp_connection = self._cabinat_frame_to_connection_mapping[
                (cabinate, frame)]
        else:
            raise exceptions.SpinnmanInvalidParameterException(
                "{}:{}".format(cabinate, frame),
                "SpinnMan cant talk to frame {} in cabinate {}"
                .format(cabinate, frame), "")
        response = self.send_scp_message(message, connection=bmp_connection)
        return response.adc_info

    def read_bmp_version(self, board, cabinate, frame):
        """
        reads the bmp's sver data
        :param cabinate: cabinate: the cabinate this is targetting
        :type cabinate: int
        :param frame: the frame this is targetting
        :type frame: int
        :param board: which board to request the fpga register from
        :return: the sver from the bmp
        """
        message = SCPBMPVersionRequest(board)
        if (cabinate, frame) in self._cabinat_frame_to_connection_mapping:
            bmp_connection = self._cabinat_frame_to_connection_mapping[
                (cabinate, frame)]
        else:
            raise exceptions.SpinnmanInvalidParameterException(
                "{}:{}".format(cabinate, frame),
                "SpinnMan cant talk to frame {} in cabinate {}"
                .format(cabinate, frame), "")
        reponse = self.send_scp_message(message, connection=bmp_connection)
        return reponse.version_info

    def write_memory(self, x, y, base_address, data, n_bytes=None):
        """ Write to the SDRAM on the board

        :param x: The x-coordinate of the chip where the memory is to be\
                    written to
        :type x: int
        :param y: The y-coordinate of the chip where the memory is to be\
                    written to
        :type y: int
        :param base_address: The address in SDRAM where the region of memory\
                    is to be written
        :type base_address: int
        :param data: The data to write.  Should be one of the following:
                    * An instance of AbstractDataReader
                    * A bytearray
                    * A single integer - will be written using little-endian\
                      byte ordering
        :type data:\
                    :py:class:`spinnman.data.abstract_data_reader.AbstractDataReader`\
                    or bytearray or int
        :param n_bytes: The amount of data to be written in bytes.  If not\
                    specified:
                        * If data is an AbstractDataReader, an error is raised
                        * If data is a bytearray, the length of the bytearray\
                          will be used
                        * If data is an int, 4 will be used
        :type n_bytes: int
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException:
                    * If there is an error communicating with the board
                    * If there is an error reading the data
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If x, y does not lead to a valid chip
                    * If a packet is received that has invalid parameters
                    * If base_address is not a positive integer
                    * If data is an AbstractDataReader but n_bytes is not\
                      specified
                    * If data is an int and n_bytes is more than 4
                    * If n_bytes is less than 0
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """

        bytes_to_write, data_to_write = \
            self._get_bytes_to_write_and_data_to_write(data, n_bytes)

        # Set up all the requests and get the callbacks
        logger.debug("Writing {} bytes of memory".format(bytes_to_write))
        offset = 0
        address_to_write = base_address
        callbacks = list()
        while bytes_to_write > 0:
            max_data_size = bytes_to_write
            if max_data_size > 256:
                max_data_size = 256
            data_array = None
            if isinstance(data_to_write, AbstractDataReader):
                data_array = data_to_write.read(max_data_size)
            elif isinstance(data_to_write, bytearray):
                data_array = data_to_write[offset:(offset + max_data_size)]
            data_size = len(data_array)

            if data_size != 0:
                thread = SCPMessageInterface(self, SCPWriteMemoryRequest(
                    x, y, address_to_write, data_array))
                self._scp_message_thread_pool.apply_async(thread.run)
                callbacks.append(thread)
                bytes_to_write -= data_size
                address_to_write += data_size
                offset += data_size

        # Go through the callbacks and check that the responses are OK
        for callback in callbacks:
            callback.get_response()

    def write_neighbour_memory(self, x, y, cpu, link, base_address, data,
                               n_bytes=None):
        """ Write to the memory of a neighbouring chip using a LINK_READ SCP
        command. If sent to a BMP, this command can be used to communicate with
        the FPGAs' debug registers.

        :param x: The x-coordinate of the chip whose neighbour is to be\
                    written to
        :type x: int
        :param y: The y-coordinate of the chip whose neighbour is to be\
                    written to
        :type y: int
        :param cpu: The cpu to use, typically 0 (or if a BMP, the slot number)
        :type cpu: int
        :param link: The link index to send the request to (or if BMP, the FPGA
        number)
        :type link: int
        :param base_address: The address in SDRAM where the region of memory\
                    is to be written
        :type base_address: int
        :param data: The data to write.  Should be one of the following:
                    * An instance of AbstractDataReader
                    * A bytearray
                    * A single integer - will be written using little-endian\
                      byte ordering
        :type data:\
                    :py:class:`spinnman.data.abstract_data_reader.AbstractDataReader`\
                    or bytearray or int
        :param n_bytes: The amount of data to be written in bytes.  If not\
                    specified:
                        * If data is an AbstractDataReader, an error is raised
                        * If data is a bytearray, the length of the bytearray\
                          will be used
                        * If data is an int, 4 will be used
        :type n_bytes: int
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException:
                    * If there is an error communicating with the board
                    * If there is an error reading the data
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If x, y does not lead to a valid chip
                    * If a packet is received that has invalid parameters
                    * If base_address is not a positive integer
                    * If data is an AbstractDataReader but n_bytes is not\
                      specified
                    * If data is an int and n_bytes is more than 4
                    * If n_bytes is less than 0
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """

        bytes_to_write, data_to_write = \
            self._get_bytes_to_write_and_data_to_write(data, n_bytes)

        # Set up all the requests and get the callbacks
        logger.debug("Writing {} bytes of memory to neighbour {}.".format(
            bytes_to_write, link))
        offset = 0
        address_to_write = base_address
        callbacks = list()
        while bytes_to_write > 0:
            max_data_size = bytes_to_write
            if max_data_size > 256:
                max_data_size = 256
            data_array = None
            if isinstance(data_to_write, AbstractDataReader):
                data_array = data_to_write.read(max_data_size)
            elif isinstance(data_to_write, bytearray):
                data_array = data_to_write[offset:(offset + max_data_size)]
            data_size = len(data_array)

            if data_size != 0:
                thread = SCPMessageInterface(self, SCPWriteLinkRequest(
                    x, y, cpu, link, address_to_write, data_array))
                self._scp_message_thread_pool.apply_async(thread.run)
                callbacks.append(thread)
                bytes_to_write -= data_size
                address_to_write += data_size
                offset += data_size

        # Go through the callbacks and check that the responses are OK
        for callback in callbacks:
            callback.get_response()

    def write_memory_flood(self, base_address, data, n_bytes=None):
        """ Write to the SDRAM of all chips.

        :param base_address: The address in SDRAM where the region of memory\
                    is to be written
        :type base_address: int
        :param data: The data that is to be written.  Should be one of\
                    the following:
                    * An instance of AbstractDataReader
                    * A bytearray
                    * A single integer
        :type data:\
                    :py:class:`spinnman.data.abstract_data_reader.AbstractDataReader`\
                    or bytearray or int
        :param n_bytes: The amount of data to be written in bytes.  If not\
                    specified:
                        * If data is an AbstractDataReader, an error is raised
                        * If data is a bytearray, the length of the bytearray\
                          will be used
                        * If data is an int, 4 will be used
                        * If n_bytes is less than 0
        :type n_bytes: int
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException:
                    * If there is an error communicating with the board
                    * If there is an error reading the executable
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If one of the specified chips is not valid
                    * If app_id is an invalid application id
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """

        # Ensure only one flood fill occurs at any one time
        self._flood_write_lock.acquire()

        bytes_to_write, data_to_write = \
            self._get_bytes_to_write_and_data_to_write(data, n_bytes)

        # Start the flood fill
        nearest_neighbour_id = self._get_next_nearest_neighbour_id()
        n_blocks = int(math.ceil(math.ceil(bytes_to_write / 4.0) / 256.0))
        self.send_scp_message(SCPFloodFillStartRequest(nearest_neighbour_id,
                                                       n_blocks))

        # Send the data blocks simultaneously
        # Set up all the requests and get the callbacks
        logger.debug("Writing {} bytes of memory".format(bytes_to_write))
        offset = 0
        address_to_write = base_address
        callbacks = list()
        block_no = 0
        while bytes_to_write > 0:
            max_data_size = bytes_to_write
            if max_data_size > 256:
                max_data_size = 256
            data_array = None
            if isinstance(data_to_write, AbstractDataReader):
                data_array = data_to_write.read(max_data_size)
            elif isinstance(data_to_write, bytearray):
                data_array = data_to_write[offset:(offset + max_data_size)]
            data_size = len(data_array)

            if data_size != 0:
                thread = SCPMessageInterface(self, SCPFloodFillDataRequest(
                    nearest_neighbour_id, block_no, address_to_write,
                    data_array))
                self._scp_message_thread_pool.apply_async(thread.run)
                callbacks.append(thread)
                bytes_to_write -= data_size
                address_to_write += data_size
                offset += data_size
                block_no += 1

        # Go through the callbacks and check that the responses are OK
        for callback in callbacks:
            callback.get_response()

        # Send the end packet
        self.send_scp_message(SCPFloodFillEndRequest(nearest_neighbour_id))

        # Release the lock to allow others to proceed
        self._flood_write_lock.release()

    def read_memory(self, x, y, base_address, length):
        """ Read some areas of SDRAM from the board

        :param x: The x-coordinate of the chip where the memory is to be\
                    read from
        :type x: int
        :param y: The y-coordinate of the chip where the memory is to be\
                    read from
        :type y: int
        :param base_address: The address in SDRAM where the region of memory\
                    to be read starts
        :type base_address: int
        :param length: The length of the data to be read in bytes
        :type length: int
        :return: An iterable of chunks of data read in order
        :rtype: iterable of bytearray
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If one of x, y, p, base_address or length is invalid
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        assert(base_address <= math.pow(2, 32))
        # Set up all the requests and get the callbacks
        logger.debug("Reading {} bytes of memory".format(length))
        bytes_to_get = length
        address_to_read = base_address
        callbacks = list()
        while bytes_to_get > 0:
            data_size = bytes_to_get
            if data_size > 256:
                data_size = 256
            thread = SCPMessageInterface(self, SCPReadMemoryRequest(
                x, y, address_to_read, data_size))
            self._scp_message_thread_pool.apply_async(thread.run)
            callbacks.append(thread)
            bytes_to_get -= data_size
            address_to_read += data_size

        # Go through the callbacks and return the responses in order
        for callback in callbacks:
            yield callback.get_response().data

    def read_memory_return_byte_array(self, x, y, base_address, length):
        """ Read some areas of SDRAM from the board

        :param x: The x-coordinate of the chip where the memory is to be\
                    read from
        :type x: int
        :param y: The y-coordinate of the chip where the memory is to be\
                    read from
        :type y: int
        :param base_address: The address in SDRAM where the region of memory\
                    to be read starts
        :type base_address: int
        :param length: The length of the data to be read in bytes
        :type length: int
        :return: An full bytearray of data read in order
        :rtype: bytearray
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If one of x, y, p, base_address or length is invalid
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        assert(base_address <= math.pow(2, 32))
        # Set up all the requests and get the callbacks
        logger.debug("Reading {} bytes of memory".format(length))
        returned_byte_array = bytearray()
        bytes_to_get = length
        address_to_read = base_address
        callbacks = list()
        while bytes_to_get > 0:
            data_size = bytes_to_get
            if data_size > 256:
                data_size = 256
            thread = SCPMessageInterface(self, SCPReadMemoryRequest(
                x, y, address_to_read, data_size))
            self._scp_message_thread_pool.apply_async(thread.run)
            callbacks.append(thread)
            bytes_to_get -= data_size
            address_to_read += data_size

        # Go through the callbacks and return the responses in order
        for callback in callbacks:
            returned_byte_array.extend(callback.get_response().data)
        return returned_byte_array

    def read_neighbour_memory(self, x, y, cpu, link, base_address, length):
        """ Read some areas of memory on a neighbouring chip using a LINK_READ
        SCP command. If sent to a BMP, this command can be used to communicate
        with the FPGAs' debug registers.

        :param x: The x-coordinate of the chip whose neighbour is to be\
                    read from
        :type x: int
        :param y: The y-coordinate of the chip whose neighbour is to be\
                    read from
        :type y: int
        :param cpu: The cpu to use, typically 0 (or if a BMP, the slot number)
        :type cpu: int
        :param link: The link index to send the request to (or if BMP, the FPGA
        number)
        :type link: int
        :param base_address: The address in SDRAM where the region of memory\
                    to be read starts
        :type base_address: int
        :param length: The length of the data to be read in bytes
        :type length: int
        :return: An iterable of chunks of data read in order
        :rtype: iterable of bytearray
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If one of x, y, p, base_address or length is invalid
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """

        # Set up all the requests and get the callbacks
        logger.debug("Reading {} bytes of neighbour {}'s memory".format(length,
                                                                        link))
        bytes_to_get = length
        address_to_read = base_address
        callbacks = list()
        while bytes_to_get > 0:
            data_size = bytes_to_get
            if data_size > 256:
                data_size = 256
            thread = SCPMessageInterface(self, SCPReadLinkRequest(
                x, y, cpu, link, address_to_read, data_size))
            self._scp_message_thread_pool.apply_async(thread.run)
            callbacks.append(thread)
            bytes_to_get -= data_size
            address_to_read += data_size

        # Go through the callbacks and return the responses in order
        for callback in callbacks:
            yield callback.get_response().data

    def stop_application(self, app_id):
        """ Sends a stop request for an app_id

        :param app_id: The id of the application to send to
        :type app_id: int
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If app_id is not a valid application id
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        self.send_scp_message(SCPAppStopRequest(app_id))

    def send_signal(self, app_id, signal):
        """ Send a signal to an application

        :param app_id: The id of the application to send to
        :type app_id: int
        :param signal: The signal to send
        :type signal: :py:class:`spinnman.messages.scp.scp_signal.SCPSignal`
         :py:class:`spinnman.messages.scp.scp_signal.SCPSignal'
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If signal is not a valid signal
                    * If app_id is not a valid application id
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        self.send_scp_message(SCPSendSignalRequest(app_id, signal))

    def set_leds(self, x, y, cpu, led_states):
        """ Set LED states.
        :param x: The x-coordinate of the chip on which to set the LEDs
        :type x: int
        :param y: The x-coordinate of the chip on which to set the LEDs
        :type y: int
        :param cpu: The CPU of the chip on which to set the LEDs
        :type cpu: int
        :param led_states: A dictionary mapping LED index to state with 0 being
                           off, 1 on and 2 inverted.
        :type led_states: dict
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException: If a\
                    packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        self.send_scp_message(SCPLEDRequest(x, y, cpu, led_states))

    def locate_spinnaker_connection_for_board_address(self, board_address):
        """ Find a connection that matches the given board IP address

        :param board_address: The IP address of the ethernet connection on the\
                    baord
        :type board_address: str
        :return: A connection for the given IP address, or None if no such\
                    connection exists
        :rtype:\
                    :py:class:`spinnman.connections.udp_packet_connections.udp_spinnaker_connection.UDPSpinnakerConnection`
        """
        for connection_key in self._sending_connections.keys():
            connection = self._sending_connections[connection_key]
            if (isinstance(connection, UDPSpinnakerConnection) and
                    connection.remote_ip_address == board_address):
                return connection
        return None

    def set_ip_tag(self, ip_tag):
        """ Set up an ip tag

        :param ip_tag: The tag to set up; note board_address can be None, in\
                    which case, the tag will be assigned to all boards
        :type ip_tag: :py:class:`spinn_machine.tags.iptag.IPTag`
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If the ip tag fields are incorrect
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """

        # Get the connections - if the tag specifies a connection, use that,
        # otherwise apply the tag to all connections
        connections = list()
        if ip_tag.board_address is not None:
            connection = self.locate_spinnaker_connection_for_board_address(
                ip_tag.board_address)
            if connection is None:
                raise exceptions.SpinnmanInvalidParameterException(
                    "ip_tag", str(ip_tag),
                    "The given board address is not recognized")
            connections.append(connection)
        else:
            connections = self._sending_connections.values()

        callbacks = list()
        for connection in connections:

            # Convert the host string
            host_string = ip_tag.ip_address
            if host_string == "localhost" or host_string == ".":
                host_string = connection.local_ip_address
            ip_string = socket.gethostbyname(host_string)
            ip_address = bytearray(socket.inet_aton(ip_string))

            # Send the request
            thread = SCPMessageInterface(self, SCPIPTagSetRequest(
                connection.chip_x, connection.chip_y, ip_address, ip_tag.port,
                ip_tag.tag, strip=ip_tag.strip_sdp))
            self._scp_message_thread_pool.apply_async(thread.run)
            callbacks.append(thread)

        for thread in callbacks:
            thread.get_response()

    def set_reverse_ip_tag(self, reverse_ip_tag):
        """ Set up a reverse ip tag

        :param reverse_ip_tag: The reverse tag to set up; note board_address\
                    can be None, in which case, the tag will be assigned to\
                    all boards
        :type reverse_ip_tag:\
                    :py:class:`spinn_machine.tags.reverse_ip_tag.ReverseIPTag`
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If the reverse ip tag fields are incorrect
                    * If a packet is received that has invalid parameters
                    * If the UDP port is one that is already used by\
                      spiNNaker for system functions
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """

        if (reverse_ip_tag.port == constants.SCP_SCAMP_PORT or
                reverse_ip_tag.port ==
                constants.UDP_BOOT_CONNECTION_DEFAULT_PORT):
            raise exceptions.SpinnmanInvalidParameterException(
                "reverse_ip_tag.port", reverse_ip_tag.port,
                "The port number for the reverese ip tag conflicts with"
                " the spiNNaker system ports ({} and {})".format(
                    constants.SCP_SCAMP_PORT,
                    constants.UDP_BOOT_CONNECTION_DEFAULT_PORT))

        # Get the connections - if the tag specifies a connection, use that,
        # otherwise apply the tag to all connections
        connections = list()
        if reverse_ip_tag.board_address is not None:
            connection = self.locate_spinnaker_connection_for_board_address(
                reverse_ip_tag.board_address)
            if connection is None:
                raise exceptions.SpinnmanInvalidParameterException(
                    "reverse_ip_tag", reverse_ip_tag,
                    "The given board address is not recognized")
            connections.append(connection)
        else:
            connections = self._sending_connections.values()

        callbacks = list()
        for connection in connections:
            thread = SCPMessageInterface(self, SCPReverseIPTagSetRequest(
                connection.chip_x, connection.chip_y,
                reverse_ip_tag.destination_x, reverse_ip_tag.destination_y,
                reverse_ip_tag.destination_p,
                reverse_ip_tag.port, reverse_ip_tag.tag,
                reverse_ip_tag.sdp_port))
            self._scp_message_thread_pool.apply_async(thread.run)
            callbacks.append(thread)

        for thread in callbacks:
            thread.get_response()

    def clear_ip_tag(self, tag, connection=None, board_address=None):
        """ Clear the setting of an ip tag

        :param tag: The tag id
        :type tag: int
        :param connection: Connection where the tag should be cleard.  If not\
                    specified, all SCPSender connections will send the message\
                    to clear the tag
        :type connection:\
                    :py:class:`spinnman.connections.abstract_scp_sender.AbstractSCPSender`
        :param board_address: Board address where the tag should be cleared.\
                    If not specified, all SCPSender connections will send the\
                    message to clear the tag
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If the tag is not a valid tag
                    * If the connection cannot send SDP messages
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        if connection is not None:
            connections = [connection]
        elif board_address is not None:
            connection = self.locate_spinnaker_connection_for_board_address(
                board_address)
            connections = [connection]
        else:
            connections = self._sending_connections.values()

        callbacks = list()
        for conn in connections:
            if isinstance(conn, UDPSpinnakerConnection):
                message = SCPIPTagClearRequest(conn.chip_x, conn.chip_y, tag)
                thread = SCPMessageInterface(self, message=message)
                self._scp_message_thread_pool.apply_async(thread.run)
                callbacks.append(thread)

        for callback in callbacks:
            callback.get_response()

    def get_tags(self, connection=None):
        """ Get the current set of tags that have been set on the board

        :param connection: Connection from which the tags should be received.\
                    If not specified, all SCPSender connections will be\
                    queried and the response will be combined.
        :type connection:\
                    :py:class:`spinnman.connections.abstract_scp_sender.AbstractSCPSender`
        :return: An iterable of tags
        :rtype: iterable of\
                    :py:class:`spinn_machine.tags.abstract_tag.AbstractTag`
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If the connection cannot send SDP messages
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        if connection is not None:
            connections = connection
        else:
            connections = self._sending_connections.values()

        callbacks = list()
        for conn in connections:
            thread = GetTagsInterface(self, conn,
                                      self._scp_message_thread_pool)

            self._other_thread_pool.apply_async(thread.run)
            callbacks.append(thread)

        all_tags = list()
        for callback in callbacks:
            all_tags.extend(callback.get_tags())
        return all_tags

    def load_multicast_routes(self, x, y, routes, app_id):
        """ Load a set of multicast routes on to a chip

        :param x: The x-coordinate of the chip onto which to load the routes
        :type x: int
        :param y: The y-coordinate of the chip onto which to load the routes
        :type y: int
        :param routes: An iterable of multicast routes to load
        :type routes: iterable of\
                    :py:class:`spinnmachine.multicast_routing_entry.MulticastRoutingEntry`
        :param app_id: The id of the application with which to associate the\
                    routes.  If not specified, defaults to 0.
        :type app_id: int
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If any of the routes are invalid
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """

        # Create the routing data
        route_writer = LittleEndianByteArrayByteWriter()
        n_entries = 0
        for route in routes:
            route_writer.write_short(n_entries)
            route_writer.write_short(0)
            route_entry = 0
            for processor_id in route.processor_ids:
                if processor_id > 26 or processor_id < 0:
                    raise exceptions.SpinnmanInvalidParameterException(
                        "route.processor_ids", str(route.processor_ids),
                        "Processor ids must be between 0 and 26")
                route_entry |= (1 << (6 + processor_id))
            for link_id in route.link_ids:
                if link_id > 5 or link_id < 0:
                    raise exceptions.SpinnmanInvalidParameterException(
                        "route.link_ids", str(route.link_ids),
                        "Link ids must be between 0 and 5")
                route_entry |= (1 << link_id)
            route_writer.write_int(route_entry)
            route_writer.write_int(route.key_combo)
            route_writer.write_int(route.mask)
            n_entries += 1

        # Upload the data
        route_writer.write_int(0xFFFFFFFF)
        route_writer.write_int(0xFFFFFFFF)
        route_writer.write_int(0xFFFFFFFF)
        route_writer.write_int(0xFFFFFFFF)
        data = route_writer.data
        table_address = 0x67800000
        self.write_memory(x, y, table_address, data)

        # Allocate enough space for the entries
        alloc_response = \
            self.send_scp_message(SCPRouterAllocRequest(x, y, app_id,
                                                        n_entries))
        base_address = alloc_response.base_address
        if base_address == 0:
            raise exceptions.SpinnmanInvalidParameterException(
                "Allocation base address", str(base_address),
                "Not enough space to allocate the entries")

        # Load the entries
        self.send_scp_message(SCPRouterInitRequest(x, y, n_entries,
                                                   table_address,
                                                   base_address, app_id))

    def get_multicast_routes(self, x, y, app_id=None):
        """ Get the current multicast routes set up on a chip

        :param x: The x-coordinate of the chip from which to get the routes
        :type x: int
        :param y: The y-coordinate of the chip from which to get the routes
        :type y: int
        :param app_id: The id of the application to filter the routes for.  If\
                    not specified, will return all routes
        :type app_id: int
        :return: An iterable of multicast routes
        :rtype: iterable of\
                    :py:class:`spinnman.model.multicast_routing_entry.MulticastRoute`
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException: If a\
                    packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        if self._machine is None:
            self._update_machine()
        chip_info = self._chip_info[(x, y)]
        base_address = chip_info.router_table_copy_address()
        length = 1024 * 16
        data = self.read_memory(x, y, base_address, length)
        all_data = bytearray()
        for data_item in data:
            all_data.extend(data_item)
        reader = LittleEndianByteArrayByteReader(all_data)

        routes = list()
        for _ in range(0, 1024):
            reader.read_short()  # next
            route_app_id = reader.read_byte()  # app_id
            reader.read_byte()  # core

            route = reader.read_int()
            processor_ids = list()
            for processor_id in range(0, 26):
                if (route & (1 << (6 + processor_id))) != 0:
                    processor_ids.append(processor_id)
            link_ids = list()
            for link_id in range(0, 6):
                if (route & (1 << link_id)) != 0:
                    link_ids.append(link_id)
            key = reader.read_int()
            mask = reader.read_int()

            if route < 0xFF000000 and (app_id is None or
                                       app_id == route_app_id):
                routes.append(MulticastRoutingEntry(key, mask, processor_ids,
                                                    link_ids, False))

        return routes

    def clear_multicast_routes(self, x, y):
        """ Remove all the multicast routes on a chip

        :param x: The x-coordinate of the chip on which to clear the routes
        :type x: int
        :param y: The y-coordinate of the chip on which to clear the routes
        :type y: int
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException: If a\
                    packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        self.send_scp_message(SCPRouterClearRequest(x, y))

    def get_router_diagnostics(self, x, y):
        """ Get router diagnostic information from a chip

        :param x: The x-coordinate of the chip from which to get the\
                    information
        :type x: int
        :param y: The y-coordinate of the chip from which to get the\
                    information
        :type y: int
        :return: The router diagnostic information
        :rtype: :py:class:`spinnman.model.router_diagnostics.RouterDiagnostics`
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException: If a\
                    packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        control_register = self.send_scp_message(
            SCPReadMemoryWordsRequest(x, y, 0xe1000000, 1)).data[0]
        error_status = self.send_scp_message(
            SCPReadMemoryWordsRequest(x, y, 0xe1000014, 1)).data[0]
        register_values = [value for value in self.send_scp_message(
            SCPReadMemoryWordsRequest(x, y, 0xe1000300, 16)).data]
        return RouterDiagnostics(control_register, error_status,
                                 register_values)

    def set_router_diagnostic_filter(self, x, y, position, diagnostic_filter):
        """ Sets a router diagnostic filter in a router

        :param x: the x address of the router in which this filter is being\
                    set
        :type x: int
        :param y: the y address of the router in which this filter is being\
                    set
        :type y: int
        :param position: the position in the list of filters where this filter\
                    is to be added
        :type position: int
        :param diagnostic_filter: the diagnostic filter being set in the\
                    placed, between 0 and 15 (note that positions 0 to 11 are\
                    used by the default filters, and setting these positions\
                    will result in a warning).
        :type diagnostic_filter:\
                    :py:class:`spinnman.model.diagnostic_filter.DiagnosticFilter`
        :return: None
        :raise spinnman.exceptions.SpinnmanIOException:
                    * If there is an error communicating with the board
                    * If there is an error reading the data
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If x, y does not lead to a valid chip
                    * If position is less than 0 or more than 15
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        data_to_send = diagnostic_filter.filter_word
        if position > constants.NO_ROUTER_DIAGNOSTIC_FILTERS:
            raise exceptions.SpinnmanInvalidParameterException(
                "position", str(position), "the range of the position of a "
                                           "router filter is 0 and 16.")
        if position <= constants.ROUTER_DEFAULT_FILTERS_MAX_POSITION:
            logger.warn(
                " You are planning to change a filter which is set by default."
                " By doing this, other runs occuring on this machine will be "
                "forced to use this new configuration untill the machine is "
                "reset. Please also note that these changes will make the"
                " the reports from ybug not correct."
                "This has been executed and is trusted that the end user knows"
                " what they are doing")
        memory_position = (constants.ROUTER_REGISTER_BASE_ADDRESS +
                           constants.ROUTER_FILTER_CONTROLS_OFFSET +
                           (position *
                            constants.ROUTER_DIAGNOSTIC_FILTER_SIZE))
        self.send_scp_message(SCPWriteMemoryWordsRequest(
            x, y, memory_position, [data_to_send]))

    def get_router_diagnostic_filter(self, x, y, position):
        """ Gets a router diagnostic filter from a router

        :param x: the x address of the router from which this filter is being\
                    retrieved
        :type x: int
        :param y: the y address of the router from which this filter is being\
                    retrieved
        :type y: int
        :param position: the position in the list of filters where this filter\
                    is to be added
        :type position: int
        :return: The diagnostic filter read
        :rtype: :py:class:`spinnman.model.diagnostic_filter.DiagnosticFilter`
        :raise spinnman.exceptions.SpinnmanIOException:
                    * If there is an error communicating with the board
                    * If there is an error reading the data
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If x, y does not lead to a valid chip
                    * If a packet is received that has invalid parameters
                    * If position is less than 0 or more than 15
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        memory_position = (constants.ROUTER_REGISTER_BASE_ADDRESS +
                           constants.ROUTER_FILTER_CONTROLS_OFFSET +
                           (position *
                            constants.ROUTER_DIAGNOSTIC_FILTER_SIZE))
        result = self.send_scp_message(SCPReadMemoryWordsRequest(
            x, y, memory_position, 1))
        return DiagnosticFilter.read_from_int(result.data[0])

    def clear_router_diagnostic_counters(self, x, y, enable=True,
                                         counter_ids=range(0, 16)):
        """ Clear router diagnostic information om a chip

        :param x: The x-coordinate of the chip
        :type x: int
        :param y: The y-coordinate of the chip
        :type y: int
        :param enable: True (default) if the counters should be enabled
        :type enable: bool
        :param counter_ids: The ids of the counters to reset (all by default)\
                    and enable if enable is True; each must be between 0 and 15
        :type counter_ids: array-like of int
        :return: None
        :rtype: Nothing is returned
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException: If a\
                    packet is received that has invalid parameters or a\
                    counter id is out of range
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        clear_data = 0
        for counter_id in counter_ids:
            if counter_id < 0 or counter_id > 15:
                raise exceptions.SpinnmanInvalidParameterException(
                    "counter_id", counter_id, "Diagnostic counter ids must be"
                                              " between 0 and 15")
            clear_data |= 1 << counter_id
        if enable:
            for counter_id in counter_ids:
                clear_data |= 1 << counter_id + 16
        self.send_scp_message(SCPWriteMemoryWordsRequest(
            x, y, 0xf100002c, [clear_data]))

    def send_multicast_message(self, x, y, multicast_message, connection=None):
        """ Sends a multicast message to the board

        :param x: The x-coordinate of the chip where the message should first\
                    arrive on the board
        :type x: int
        :param y: The y-coordinate of the chip where the message should first\
                    arrive on the board
        :type y: int
        :param multicast_message: A multicast message to send
        :type multicast_message:\
                    :py:class:`spinnman.messages.multicast_message.MulticastMessage`
        :param connection: A specific connection over which to send the\
                    message.  If not specified, an appropriate connection is\
                    chosen automatically
        :type connection:\
                    :py:class:`spinnman.connections.abstract_multicast_sender.AbstractMulticastSender`
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanUnsupportedOperationException:
                    * If there is no connection that supports sending over\
                      multicast (or the given connection does not)
                    * If there is no connection that can make the packet\
                      arrive at the selected chip (ignoring routing tables)
        """
        raise exceptions.SpinnmanUnsupportedOperationException(
            "This operation is currently not supported in spinnman.")

    def receive_multicast_message(self, x, y, timeout=None, connection=None):
        """ Receives a multicast message from the board

        :param x: The x-coordinate of the chip where the message should come\
                    from on the board
        :type x: int
        :param y: The y-coordinate of the chip where the message should come\
                    from on the board
        :type y: int
        :param timeout: Amount of time to wait for the message to arrive in\
                    seconds before a timeout.  If not specified, will wait\
                    indefinitely, or until the selected connection is closed
        :type timeout: int
        :param connection: A specific connection from which to receive the\
                    message.  If not specified, an appropriate connection is\
                    chosen automatically
        :type connection:\
                    :py:class:`spinnman.connections.abstract_multicast_receiver.AbstractMulticastReceiver`
        :return: The received message
        :rtype:\
                    :py:class:`spinnman.messages.multicast_message.MulticastMessage`
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanUnsupportedOperationException:
                    * If there is no connection that supports reception over\
                      multicast (or the given connection does not)
                    * If there is no connection that can receive a packet\
                      from the selected chip (ignoring routing tables)
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If the\
                    message received is not a valid multicast message
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If the timeout value is not valid
                    * If the received packet has an invalid parameter
        """
        raise exceptions.SpinnmanUnsupportedOperationException(
            "This operation is currently not supported in spinnman.")

    @property
    def number_of_boards_located(self):
        """
        returns how many boards are currently being supported by the spinnman
        interface
        :return:
        """
        boards = 0
        for bmp_connection in self._bmp_connection_to_bmp_data_mapping:
            bmp_connection_data = \
                self._bmp_connection_to_bmp_data_mapping[bmp_connection]
            boards += len(bmp_connection_data.boards)
        return boards



    def close(self, close_original_connections=True):
        """ Close the transceiver and any threads that are running

        :param close_original_connections: If True, the original connections\
                    passed to the transceiver in the constructor are also\
                    closed.  If False, only newly discovered connections are\
                    closed.
        :return: Nothing is returned
        :rtype: None
        :raise None: No known exceptions are raised
        """
        for connection_queue in self._connection_queues.itervalues():
            connection_queue.stop()

        for connection in self._sending_connections.itervalues():
            if (close_original_connections or
                    connection not in self.connections_to_not_shut_down):
                connection.close()

        for connection in self._receiving_connections.itervalues():
            if (close_original_connections or
                    connection not in self.connections_to_not_shut_down):
                connection.close()

        self._scp_message_thread_pool.close()
        self._other_thread_pool.close()

    def register_listener(self, callback, recieve_port_no,
                          connection_type, traffic_type, hostname=None):
        """ Register a callback for a certain type of traffic

        :param callback: Function to be called when a packet is received
        :type callback: function(packet)
        :param recieve_port_no: The port number to listen on
        :type recieve_port_no: int
        :param connection_type: The type of the connection
        :param traffic_type: The type of traffic expected on the connection
        :param hostname: The optional hostname to listen on
        :type hostname: str
        """
        if recieve_port_no in self._receiving_connections:
            connection = self._receiving_connections[recieve_port_no]
            if connection_type == connection.connection_type():
                connection.register_callback(callback)
            else:
                raise exceptions.SpinnmanInvalidParameterException(
                    "There is already a connection on this port number which "
                    "does not support reception of this message type. Please "
                    "try again with antoher port number", "", "")
        else:
            if connection_type == constants.CONNECTION_TYPE.SDP_IPTAG:
                connection = IPTagConnection(hostname, recieve_port_no)
                connection.register_callback(callback, traffic_type)
                self._receiving_connections[recieve_port_no] = connection
            elif connection_type == constants.CONNECTION_TYPE.UDP_IPTAG:
                connection = StrippedIPTagConnection(hostname, recieve_port_no)
                connection.register_callback(callback, traffic_type)
                self._receiving_connections[recieve_port_no] = connection
            else:
                raise exceptions.SpinnmanInvalidParameterException(
                    "Currently spinnman does not know how to register a "
                    "callback to a connection of type {}."
                    .format(connection_type), "", "")

    def __str__(self):
        return "transciever object connected to {} with {} connections"\
            .format(self._sending_connections[0].remote_ip_address,
                    len(self._sending_connections.keys()))

    def __repr__(self):
        return self.__str__()
