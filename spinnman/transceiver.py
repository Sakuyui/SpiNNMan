from spinnman.connections.udp_connection import UDPConnection
from spinnman.connections.udp_connection import UDP_CONNECTION_DEFAULT_PORT
from spinnman.connections._connection_queue import _ConnectionQueue
from spinnman.exceptions import SpinnmanUnsupportedOperationException
from spinnman.exceptions import SpinnmanTimeoutException
from spinnman.exceptions import SpinnmanUnexpectedResponseCodeException
from spinnman.model.system_variables import SystemVariables
from spinnman.model.system_variables import _SYSTEM_VARIABLE_BASE_ADDRESS
from spinnman.model.system_variables import _SYSTEM_VARIABLE_BYTES
from spinnman.model.machine_dimensions import MachineDimensions
from spinnman.messages.scp.impl.scp_read_link_request import SCPReadLinkRequest
from spinnman.messages.scp.impl.scp_read_memory_request import SCPReadMemoryRequest
from spinnman.messages.scp.scp_result import SCPResult

from spinn_machine.machine import Machine
from spinn_machine.chip import Chip
from spinn_machine.chip import CHIP_DEFAULT_SDRAM_AVAIABLE
from spinn_machine.sdram import SDRAM
from spinn_machine.processor import Processor
from spinn_machine.router import Router
from spinn_machine.router import ROUTER_DEFAULT_AVAILABLE_ENTRIES
from spinn_machine.router import ROUTER_DEFAULT_CLOCK_SPEED
from spinn_machine.link import Link

from time import sleep
from collections import deque

import logging
from spinnman.messages.scp.impl.scp_version_request import SCPVersionRequest

logger = logging.getLogger(__name__)


def create_transceiver_from_hostname(hostname):
    """ Create a Transceiver by creating a UDPConnection to the given\
        hostname on port 17893 (the default SCAMP port), discovering any\
        additional links using this connection, and then returning the\
        transceiver created with the conjunction of the created\
        UDPConnection and the discovered connections

    :param hostname: The hostname or IP address of the board
    :type hostname: str
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
    connection = UDPConnection(remote_host=hostname)
    return Transceiver(connections=[connection])


class Transceiver(object):
    """ An encapsulation of various communications with the spinnaker board.\
        Note that the methods of this class are designed to be thread-safe;\
        thus you can make multiple calls to the same (or different) methods\
        from multiple threads and expect each call to work as if it had been\
        called sequentially, although the order of returns is not guaranteed.\
        Note also that with multiple connections to the board, using multiple\
        threads in this way may result in an increase in the overall speed of\
        operation, since the multiple calls may be made separately over the\
        set of given connections.
    """

    def __init__(self, connections=None, discover=True):
        """

        :param connections: An iterable of connections to the board.  If not\
                    specified, no communication will be possible until\
                    connections are specified.
        :type connections: iterable of\
                    :py:class:`spinnman.connections.abstract_connection.AbstractConnection`
        :param discover: Determines if discovery should take place.  If not\
                    specified, an attempt will be made to discover connections\
                    to the board.
        :type discover: bool
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException: If a\
                    packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        # Create a connection list
        self._connections = list(connections)
        self._udp_connections = dict()
        for connection in self._connections:
            if isinstance(connection, UDPConnection):
                self._udp_connections[(connection._remote_ip_address,
                        connection._remote_port)] = connection

        # Update the queues for the given connections
        self._connection_queues = dict()
        self._update_connection_queues()

        # Discover any new connections, and update the queues if requested
        if discover:
            self.discover_connections()

        # Place to keep the current machine
        self._machine = None

    def _update_connection_queues(self):
        """ Creates and deletes queues of connections depending upon what\
            connections are now available

        :return: Nothing is returned
        :rtype: None
        :raise None: No known exceptions are raised
        """
        for connection in self._connections:

            # Only add a new queue if there isn't one currently
            if connection not in self._connection_queues:
                self._connection_queues[connection] =\
                        _ConnectionQueue(connection)
                self._connection_queues[connection].start()

    def _send_message(self, message, response_required, connection=None,
            timeout=1):
        """ Sends a message using one of the connections, and gets a response\
            if requested

        :param message: The message to send
        :type message: One of:
                    * :py:class:`spinnman.messages.sdp.sdp_message.SDPMessage`
                    * :py:class:`spinnman.messages.scp.abstract_scp_request.AbstractSCPRequest`
                    * :py:class:`spinnman.messages.multicast_message.MulticastMessage`
                    * :py:class:`spinnman.messages.spinnaker_boot_message.SpinnakerBootMessage`
        :param response_required: True if a response is required, False\
                    otherwise
        :type response_required: bool
        :param connection: An optional connection to use
        :type connection:\
                    :py:class:`spinnman.connections.abstract_connection.AbstractConnection`
        :param timeout: Timeout to use when waiting for a response
        :type timeout: int
        :return: The response if requested, or None otherwise
        :rtype: The same type as message, or\
                    :py:class:`spinnman.messages.scp.abstract_scp_response.AbstractSCPResponse`\
                    if message is an AbstractSCPRequest
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

        best_connection_queue = None

        # If a connection is given, use it
        if connection != None:
            best_connection_queue = self._connection_queues[connection]

            # If the connection doesn't support the message,
            # reject the connection, and allow the error to be raised later
            if not best_connection_queue.message_type_supported(message):
                best_connection_queue = None
        else:

            # Find the least congested way that supports the message type
            best_connection_queue_size = None
            for connection_queue in self._connection_queues.values():
                if connection_queue.message_type_supported(
                        message, response_required):
                    connection_queue_size = connection_queue.queue_length
                    if (best_connection_queue is None
                            or connection_queue_size
                                    < best_connection_queue_size):
                        best_connection_queue = connection_queue
                        best_connection_queue_size = connection_queue_size

        # If no supported queue was found, raise an exception
        if best_connection_queue is None:
            raise SpinnmanUnsupportedOperationException(
                    "Sending and receiving {}".format(message.__class__))

        # Send the message with the best queue
        logger.debug("Sending message with {}".format(best_connection_queue))
        return best_connection_queue.send_message(
                message, response_required, timeout)

    def _send_scp_message(
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
        :type n_retries: int
        :return: The received response
        :rtype: :py:class:`spinnman.messages.scp.abstract_scp_response.AbstractSCPResponse`
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
        retries_to_go = n_retries
        response = None
        while retries_to_go >= 0:
            retry = False
            try:
                response = self._send_message(
                        message=message, response_required=True,
                        connection=connection)

                if response.scp_response_header.result == SCPResult.RC_OK:
                    return response

                if response.scp_response_header.result in retry_codes:
                    retry = True
            except SpinnmanTimeoutException:
                retry = True

            if retry:
                retries_to_go -= 1
                sleep(0.1)

        raise SpinnmanUnexpectedResponseCodeException(
                "SCP", message.scp_request_header.command.name,
                response.scp_response_header.result.name)

    def _make_chip(self, chip_details):
        """ Creates a chip from a SystemVariables structure

        :param chip_details: The SystemVariables structure to create the chip\
                    from
        :type chip_details: \
                    :py:class:`spinnman.model.system_variables.SystemVariables`
        :return: The created chip
        :rtype: :py:class:`spinn_machine.chip.Chip`
        """

        # Create the processor list
        processors = list()
        for virtual_core_id in chip_details.virtual_core_ids:
            processors.append(Processor(
                    virtual_core_id, chip_details.cpu_clock_mhz * 1000000,
                    virtual_core_id == 0))

        # Create the router - add the links later during search
        router = Router(
                links=list(), emergency_routing_enabled=False,
                clock_speed=ROUTER_DEFAULT_CLOCK_SPEED,
                n_available_multicast_entries=ROUTER_DEFAULT_AVAILABLE_ENTRIES
                    - chip_details.first_free_router_entry)

        # Create the chip
        chip = Chip(
                x=chip_details.x, y=chip_details.y, processors=processors,
                router=router, sdram=SDRAM(CHIP_DEFAULT_SDRAM_AVAIABLE),
                ip_address=chip_details.ip_address)
        return chip

    def _update_machine(self):
        """ Get the current machine status and store it
        """

        # Ask the chip at 0, 0 for details
        logger.debug("Getting details of chip 0, 0")
        response = self._send_scp_message(SCPReadMemoryRequest(
                x=0, y=0, base_address=_SYSTEM_VARIABLE_BASE_ADDRESS,
                size=_SYSTEM_VARIABLE_BYTES))
        chip_0_0_details = SystemVariables(response.data)
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
                    response = self._send_scp_message(SCPReadLinkRequest(
                        x=chip.x, y=chip.y, link=link,
                        base_address=_SYSTEM_VARIABLE_BASE_ADDRESS,
                        size=_SYSTEM_VARIABLE_BYTES))
                    new_chip_details = SystemVariables(response.data)

                    # Standard links use the opposite link id (with ids between
                    # 0 and 5) as default
                    opposite_link_id = (link + 3) % 6

                    # Update the defaults of any existing link
                    if chip.router.is_link(opposite_link_id):
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
                        search.append(
                                (new_chip, new_chip_details.links_available))

                except SpinnmanUnexpectedResponseCodeException:

                    # If there is an error, assume the link is down
                    pass

    def discover_connections(self):
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
        # that supports SCP - this is done via the machine
        self._update_machine()

        # Find all the new connections via the machine ethernet-connected chips
        new_connections = list()
        for ethernet_connected_chip in self._machine.ethernet_connected_chips:
            if (ethernet_connected_chip.ip_address,
                    UDP_CONNECTION_DEFAULT_PORT) not in self._udp_connections:
                new_connection = UDPConnection(
                        remote_host=ethernet_connected_chip.ip_address)
                new_connections.append(new_connection)
                self._connections.append(new_connection)
                self._udp_connections[(ethernet_connected_chip.ip_address,
                    UDP_CONNECTION_DEFAULT_PORT)] = new_connection

        # Update the connection queues after finding new connections
        self._update_connection_queues()

        return new_connections

    def get_connections(self):
        """ Get the currently known connections to the board, made up of those\
            passed in to the transceiver and those that are discovered during\
            calls to discover_connections.  No further discovery is done here.

        :return: An iterable of connections known to the transciever
        :rtype: iterable of\
                    :py:class:`spinnman.connections.abstract_connection.AbstractConnection`
        :raise None: No known exceptions are raised
        """
        return self._connections

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
        for connection in self._connections:
            if connection.is_connected():
                return True
        return False

    def get_scamp_version(self, n_retries=3, timeout=1):
        """ Get the version of scamp which is running on the board

        :param n_retries: The number of times to retry getting the version
        :type n_retries: int
        :param timeout: The timeout for each retry in seconds
        :type timeout: int
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
        response = self._send_scp_message(
                message=SCPVersionRequest(x=0, y=0, p=0),
                n_retries=n_retries, timeout=timeout)
        return response.version_info

    def boot_board(self, board_version):
        """ Attempt to boot the board.  No check is performed to see if the\
            board is already booted.

        :param board_version: The version of the board e.g. 3 for a SpiNN-3\
                    board or 5 for a SpiNN-5 board.
        :type board_version: int
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        """
        pass

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
        pass

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
        pass

    def get_core_status_count(self, status, app_id=None):
        """ Get a count of the number of cores which have a given status

        :param status: The status count to get
        :type status: :py:class:`spinnman.model.cpu_info.State`
        :param app_id: The id of the application from which to get the count.\
                    If not specified, gets the count from all applications.
        :type app_id: int
        :return: A count of the cores with the given status
        :rtype: int
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If status is not a valid status
                    * If app_id is not a valid application id
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        pass

    def execute(self, x, y, p, executable, app_id):
        """ Start an executable running on a single core

        :param x: The x-coordinate of the chip on which to run the executable
        :type x: int
        :param y: The y-coordinate of the chip on which to run the executable
        :type y: int
        :param p: The core on the chip on which to run the application
        :type p: int
        :param executable: The data that is to be executed.  Should be one of\
                    the following:
                    * An instance of AbstractDataReader
                    * A bytearray
        :type executable: :py:class:`spinnman.data.abstract_data_reader.AbstractDataReader`\
                    or bytearray
        :param app_id: The id of the application with which to associate the\
                    executable
        :type app_id: int
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
        pass

    def execute_flood(self, core_subsets, executable, app_id):
        """ Start an executable running on multiple places on the board.  This\
            will be optimized based on the selected cores, but it may still\
            require a number of communications with the board to execute.

        :param core_subsets: Which cores on which chips to start the executable
        :type core_subsets: :py:class:`spinnman.model.core_subsets.CoreSubsets`
        :param executable: The data that is to be executed.  Should be one of\
                    the following:
                    * An instance of AbstractDataReader
                    * A bytearray
        :type executable: :py:class:`spinnman.data.abstract_data_reader.AbstractDataReader`\
                    or bytearray
        :param app_id: The id of the application with which to associate the\
                    executable
        :type app_id: int
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
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        pass

    def write_memory(self, x, y, base_address, data):
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
                    * A single integer
        :type data: :py:class:`spinnman.data.abstract_data_reader.AbstractDataReader`\
                    or bytearray or int
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
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        pass

    def write_memory_flood(self, core_subsets, base_address, data):
        """ Write to the SDRAM of a number of chips.  This will be optimized\
            based on the selected cores, but it may still require a number\
            of communications with the board.

        :param core_subsets: Which chips to write the data to (the cores are\
                    ignored)
        :type core_subsets: :py:class:`spinnman.model.core_subsets.CoreSubsets`
        :param base_address: The address in SDRAM where the region of memory\
                    is to be written
        :type base_address: int
        :param data: The data that is to be written.  Should be one of\
                    the following:
                    * An instance of AbstractDataReader
                    * A bytearray
                    * A single integer
        :type data: :py:class:`spinnman.data.abstract_data_reader.AbstractDataReader`\
                    or bytearray or int
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
        pass

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
        pass

    def send_signal(self, signal, app_id=None):
        """ Send a signal to an application

        :param signal: The signal to send
        :type signal: :py:class:`spinnman.messages.scp_message.Signal`
        :param app_id: The id of the application to send to.  If not\
                    specified, the signal is sent to all applications
        :type app_id: int
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
        pass

    def set_ip_tag(self, ip_tag, connection=None):
        """ Set up an ip tag

        :param iptag: The iptag to set up
        :type iptag: :py:class:`spinnman.model.iptag.IPTag`
        :param connection: Connection where the tag should be set up.  If not\
                    specified, all SCPSender connections will send the message\
                    to set up the tag
        :type connection:\
                    :py:class:`spinnman.connections.abstract_scp_sender.AbstractSCPSender`
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If the ip tag fields are incorrect
                    * If the connection cannot send SDP messages
                    * If a packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        pass

    def clear_ip_tag(self, tag, connection=None):
        """ Clear the setting of an ip tag

        :param tag: The tag id
        :type tag: int
        :param connection: Connection where the tag should be cleard.  If not\
                    specified, all SCPSender connections will send the message\
                    to clear the tag
        :type connection:\
                    :py:class:`spinnman.connections.abstract_scp_sender.AbstractSCPSender`
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
        pass

    def get_ip_tags(self, connection=None):
        """ Get the current set of ip tags that have been set on the board

        :param connection: Connection from which the tags should be received.\
                    If not specified, all SCPSender connections will be queried\
                    and the response will be combined.
        :type connection:\
                    :py:class:`spinnman.connections.abstract_scp_sender.AbstractSCPSender`
        :return: An iterable of ip tags
        :rtype: iterable of :py:class:`spinnman.model.iptag.IPTag`
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
        pass

    def load_multicast_routes(self, app_id, x, y, routes):
        """ Load a set of multicast routes on to a chip

        :param app_id: The id of the application to associate routes with
        :type app_id: int
        :param x: The x-coordinate of the chip onto which to load the routes
        :type x: int
        :param y: The y-coordinate of the chip onto which to load the routes
        :type y: int
        :param route_data_item: An iterable of multicast routes to load
        :type route_data_item: iterable of\
                    :py:class:`spinnman.model.multicast_routing_entry.MulticastRoute`
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
        pass

    def get_multicast_routes(self, x, y, app_id=None):
        """ Get the current multicast routes set up on a chip

        :param x: The x-coordinate of the chip from which to get the routes
        :type x: int
        :param y: The y-coordinate of the chip from which to get the routes
        :type y: int
        :param app_id: Optional application id of the routes.  If not\
                    specified all the routes will be returned.  If specified,\
                    the routes will be filtered so that only those for the\
                    given application are returned.
        :type app_id: int
        :return: An iterable of multicast routes
        :rtype: iterable of :py:class:`spinnman.model.multicast_routing_entry.MulticastRoute`
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If a packet\
                    is received that is not in the valid format
        :raise spinnman.exceptions.SpinnmanInvalidParameterException: If a\
                    packet is received that has invalid parameters
        :raise spinnman.exceptions.SpinnmanUnexpectedResponseCodeException: If\
                    a response indicates an error during the exchange
        """
        pass

    def clear_multicast_routes(self, x, y, app_id=None):
        """ Remove all the multicast routes on a chip
        :param x: The x-coordinate of the chip on which to clear the routes
        :type x: int
        :param y: The y-coordinate of the chip on which to clear the routes
        :type y: int
        :param app_id: Optional application id of the routes.  If not\
                    specified all the routes will be cleared.  If specified,\
                    only the routes with the given application id will be\
                    removed.
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
        pass

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
        pass

    def send_multicast(self, x, y, multicast_message, connection=None):
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
        pass

    def receive_multicast(self, x, y, timeout=None, connection=None):
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
        :rtype: :py:class:`spinnman.messages.multicast_message.MulticastMessage`
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
        pass

    def send_sdp_message(self, sdp_message, connection=None):
        """ Sends an SDP message to the board

        :param sdp_message: The SDP message to send
        :type sdp_message: :py:class:`spinnman.messages.sdp.sdp_message.SDPMessage`
        :param connection: A specific connection over which to send the\
                    message.  If not specified, an appropriate connection is\
                    chosen automatically
        :type connection:\
                    :py:class:`spinnman.connections.abstract_sdp_sender.AbstractSDPSender`
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanUnsupportedOperationException: If\
                    there is no connection that supports sending SDP\
                    messages (or the given connection does not)
        """
        pass

    def receive_sdp_message(self, timeout=None, connection=None):
        """ Receives an SDP message from the board

        :param timeout: Amount of time to wait for the message to arrive in\
                    seconds before a timeout.  If not specified, will wait\
                    indefinitely, or until the selected connection is closed
        :type timeout: int
        :param connection: A specific connection from which to receive the\
                    message.  If not specified, an appropriate connection is\
                    chosen automatically
        :type connection:\
                    :py:class:`spinnman.connections.abstract_sdp_receiver.AbstractSDPReceiver`
        :return: The received message
        :rtype: :py:class:`spinnman.messages.sdp.sdp_message.SDPMessage`
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanUnsupportedOperationException: If\
                    there is no connection that supports reception of\
                    SDP (or the given connection does not)
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If the\
                    message received is not a valid SDP message
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If the timeout value is not valid
                    * If the received packet has an invalid parameter
        """
        pass

    def send_scp_message(self, scp_message, connection=None):
        """ Sends an SCP message to the board

        :param scp_message: The SDP message to send
        :type scp_message: :py:class:`spinnman.messages.scp_message.SCPMessage`
        :param connection: A specific connection over which to send the\
                    message.  If not specified, an appropriate connection is\
                    chosen automatically
        :type connection:\
                    :py:class:`spinnman.connections.abstract_scp_sender.AbstractSCPSender`
        :return: Nothing is returned
        :rtype: None
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanUnsupportedOperationException: If\
                    there is no connection that supports sending SCP\
                    messages (or the given connection does not)
        """
        pass

    def receive_scp_message(self, timeout=None, connection=None):
        """ Receives an SCP message from the board

        :param timeout: Amount of time to wait for the message to arrive in\
                    seconds before a timeout.  If not specified, will wait\
                    indefinitely, or until the selected connection is closed
        :type timeout: int
        :param connection: A specific connection from which to receive the\
                    message.  If not specified, an appropriate connection is\
                    chosen automatically
        :type connection:\
                    :py:class:`spinnman.connections.abstract_scp_receiver.AbstractSCPReceiver`
        :return: The received message
        :rtype: :py:class:`spinnman.messages.scp_message.SCPMessage`
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    communicating with the board
        :raise spinnman.exceptions.SpinnmanUnsupportedOperationException: If\
                    there is no connection that supports reception of\
                    SCP (or the given connection does not)
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If the\
                    message received is not a valid SCP message
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If the timeout value is not valid
                    * If the received packet has an invalid parameter
        """
        pass

    def close(self):
        """ Close the transceiver and any threads that are running

        :return: Nothing is returned
        :rtype: None
        :raise None: No known exceptions are raised
        """
        for connection_queue in self._connection_queues.itervalues():
            connection_queue.stop()
