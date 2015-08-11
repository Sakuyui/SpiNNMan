import functools
import struct
from collections import defaultdict
from collections import OrderedDict

from spinnman.processes.get_cpu_info_process import GetCPUInfoProcess
from spinnman.model.io_buffer import IOBuffer
from spinnman.messages.scp.impl.scp_read_memory_request \
    import SCPReadMemoryRequest
from spinnman.processes.abstract_multi_connection_process \
    import AbstractMultiConnectionProcess
from spinnman import constants


class ReadIOBufProcess(AbstractMultiConnectionProcess):
    """ A process for reading memory
    """

    def __init__(self, machine, connections, next_connection_selector=None):
        AbstractMultiConnectionProcess.__init__(
            self, connections, next_connection_selector)
        self._connections = connections
        self._machine = machine

        # A dictionary of (x, y, p) -> OrderedDict(n) -> bytearray
        self._iobuf = defaultdict(OrderedDict)

        # A dictionary of (x, y, p) -> OrderedDict(n) -> memoryview
        self._iobuf_view = defaultdict(OrderedDict)

        # A list of extra reads that need to be done as a result of the first
        # read = list of (x, y, p, n, base_address, size, offset)
        self._extra_reads = list()

        # A list of next reads that need to be done as a result of the first
        # read = list of (x, y, p, n, next_address, first_read_size)
        self._next_reads = list()

    def handle_first_iobuf_response(self, x, y, p, n, base_address,
                                    first_read_size, response):

        # Unpack the iobuf header
        (next_address, bytes_to_read) = struct.unpack_from(
            "<I8xI", response.data, response.offset)

        # Create a buffer for the data
        data = bytearray(bytes_to_read)
        view = memoryview(data)
        self._iobuf[(x, y, p)][n] = data
        self._iobuf_view[(x, y, p)][n] = view

        # Put the data from this packet into the buffer
        packet_bytes = response.length - 16
        if packet_bytes > bytes_to_read:
            packet_bytes = bytes_to_read
        offset = response.offset + 16
        if packet_bytes > 0:
            view[0:packet_bytes] = response.data[
                offset:(offset + packet_bytes)]

        bytes_to_read -= packet_bytes
        base_address += packet_bytes + 16
        read_offset = packet_bytes

        # While more reads need to be done to read the data
        while bytes_to_read > 0:

            # Read the next bit of memory making up the buffer
            next_bytes_to_read = min((bytes_to_read,
                                      constants.UDP_MESSAGE_MAX_SIZE))
            self._extra_reads.append((x, y, p, n, base_address,
                                      next_bytes_to_read, read_offset))
            base_address += next_bytes_to_read
            read_offset += next_bytes_to_read
            bytes_to_read -= next_bytes_to_read

        # If there is another IOBuf buffer, read this next
        if next_address != 0:
            self._next_reads.append((x, y, p, n + 1, next_address,
                                     first_read_size))

    def handle_extra_iobuf_response(self, x, y, p, n, offset, response):
        view = self._iobuf_view[(x, y, p)][n]
        view[offset:offset + response.length] = response.data[
            response.offset:response.offset + response.length]

    def read_iobuf(self, chip_info, core_subsets):
        cpu_info_process = GetCPUInfoProcess(self._machine, self._connections)
        cpu_information = cpu_info_process.get_cpu_info(chip_info,
                                                        core_subsets)

        # Kick-start the reading of the IOBufs
        for cpu_info in cpu_information:
            this_chip_info = chip_info[(cpu_info.x, cpu_info.y)]
            iobuf_size = this_chip_info.iobuf_size + 16
            first_read_size = min((iobuf_size, constants.UDP_MESSAGE_MAX_SIZE))

            self._next_reads.append((cpu_info.x, cpu_info.y, cpu_info.p, 0,
                                     cpu_info.iobuf_address, first_read_size))

        # Run rounds of the process until reading is complete
        while len(self._extra_reads) > 0 or len(self._next_reads) > 0:

            # Process the extra iobuf reads needed
            while len(self._extra_reads) > 0:
                (x, y, p, n, base_address, size, offset) = \
                    self._extra_reads.pop()

                self._send_request(
                    SCPReadMemoryRequest(x, y, base_address, size),
                    functools.partial(self.handle_extra_iobuf_response,
                                      x, y, p, n, offset))

            # Process the next iobuf reads needed
            while len(self._next_reads) > 0:
                (x, y, p, n, next_address, first_read_size) = \
                    self._next_reads.pop()
                self._send_request(
                    SCPReadMemoryRequest(x, y, next_address, first_read_size),
                    functools.partial(self.handle_first_iobuf_response,
                                      x, y, p, n, next_address,
                                      first_read_size))

            # Finish this round
            self._finish()

        self.check_for_error()
        for core_subset in core_subsets:
            x = core_subset.x
            y = core_subset.y
            for p in core_subset.processor_ids:
                iobufs = self._iobuf[(x, y, p)]
                iobuf = ""
                for item in iobufs.itervalues():
                    iobuf += item.decode("ascii")

                yield IOBuffer(x, y, p, iobuf)