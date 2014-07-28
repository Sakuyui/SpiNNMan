from spinnman.messages.scp.abstract_scp_response import AbstractSCPResponse
from spinnman.messages.scp.scp_result import SCPResult
from spinnman.exceptions import SpinnmanUnexpectedResponseCodeException


class SCPIPTagGetResponse(AbstractSCPResponse):
    """ An SCP response to a request for an IP tags
    """

    def __init__(self):
        """
        """
        super(SCPIPTagGetResponse, self).__init__()
        self._ip_address = None
        self._mac_address = None
        self._port = None
        self._timeout = None
        self._flags = None
        self._count = None
        self._rx_port = None
        self._spin_chip_y = None
        self._spin_chip_x = None
        self._spin_port = None

    def read_scp_response(self, byte_reader):
        """ See :py:meth:`spinnman.messages.scp.abstract_scp_response.AbstractSCPResponse.read_scp_response`
        """
        super(SCPIPTagGetResponse, self).read_scp_response(byte_reader)
        result = self.scp_response_header.result
        if result != SCPResult.RC_OK:
            raise SpinnmanUnexpectedResponseCodeException(
                "Get IP Tag Info", "CMD_IPTAG", result.name)

        self._ip_address = bytearray([byte_reader.read_byte()
                for _ in range(0, 4)])
        self._mac_address = bytearray([byte_reader.read_byte()
                for _ in range(0, 6)])
        self._port = byte_reader.read_short()
        self._timeout = byte_reader.read_short()
        self._flags = byte_reader.read_short()
        self._count = byte_reader.read_int()
        self._rx_port = byte_reader.read_short()
        self._spin_chip_y = byte_reader.read_byte()
        self._spin_chip_x = byte_reader.read_byte()
        self._spin_port = byte_reader.read_byte()

    @property
    def ip_address(self):
        """ The IP address of the tag, as a bytearray of 4 bytes

        :rtype: bytearray
        """
        return self._ip_address

    @property
    def mac_address(self):
        """ The MAC address of the tag, as a bytearray of 6 bytes

        :rtype: bytearray
        """
        return self._mac_address

    @property
    def port(self):
        """ The port of the tag

        :rtype: int
        """
        return self._port

    @property
    def timeout(self):
        """ The timeout of the tag

        :rtype: int
        """
        return self._timeout

    @property
    def flags(self):
        """ The flags of the tag

        :rtype: int
        """
        return self._flags

    @property
    def in_use(self):
        """ True if the tag is marked as being in use

        :rtype: bool
        """
        return (self._flags & 0x8000) > 0

    @property
    def count(self):
        """ The count of the number of packets that have been sent with the tag

        :rtype: int
        """
        return self._count

    @property
    def rx_port(self):
        """ The receive port of the tag

        :rtype: int
        """
        return self._rx_port

    @property
    def spin_chip_x(self):
        """ The x-coordinate of the chip on which the tag is defined

        :rtype: int
        """
        return self._spin_chip_x

    @property
    def spin_chip_y(self):
        """ The y-coordinate of the chip on which the tag is defined

        :rtype: int
        """
        return self._spin_chip_y

    @property
    def spin_port(self):
        """ The spin-port of the ip tag

        :rtype: int
        """
        return self._spin_port