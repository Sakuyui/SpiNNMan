from spinnman.messages.scp.abstract_scp_request import AbstractSCPRequest
from spinnman.exceptions import SpinnmanInvalidParameterException
from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.scp.scp_request_header import SCPRequestHeader
from spinnman.messages.scp.scp_command import SCPCommand
from spinnman.messages.scp.impl.scp_read_link_response import SCPReadLinkResponse
   

class SCPReadLinkRequest(AbstractSCPRequest):
    """ An SCP request to read a region of memory via a link on a chip
    """
    
    def __init__(self, x, y, link, base_address, size):
        """
        
        :param x: The x-coordinate of the chip to read from, between 0 and 255
        :type x: int
        :param y: The y-coordinate of the chip to read from, between 0 and 255
        :type y: int
        :param link: The id of the link down which to send the query
        :type link: int
        :param base_address: The positive base address to start the read from
        :type base_address: int
        :param size: The number of bytes to read, between 1 and 256
        :type size: int
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If the chip coordinates are out of range
                    * If the base address is not a positive number
                    * If the size is out of range
                    * If the tag is out of range
                    * If the sequence number if not a positive number
        """
        if base_address < 0:
            raise SpinnmanInvalidParameterException(
                    "base_address", str(base_address),
                    "Must be a positive number")
        
        if size < 1 or size > 256:
            raise SpinnmanInvalidParameterException(
                    "size", size, "Must be between 1 and 256")
        
        super(SCPReadLinkRequest, self).__init__(
                SDPHeader(
                        flags=SDPFlag.REPLY_EXPECTED, destination_port=1,
                        destination_cpu=0, destination_chip_x=x,
                        destination_chip_y=y),
                SCPRequestHeader(command=SCPCommand.CMD_LINK_READ))
        self._link = link
        self._base_address = base_address
        self._size = size
        
    def write_scp_request(self, byte_writer):
        """ See :py:meth:`spinnman.messages.scp.abstract_scp_request.AbstractSCPRequest.write_scp_request`
        """
        super(SCPReadLinkRequest, self).write_scp_request(byte_writer)
        
        # Write the arguments
        byte_writer.write_int(self._base_address)
        byte_writer.write_int(self._size)
        byte_writer.write_int(self._link)
        
    def _get_scp_response(self):
        """ See :py:meth:`spinnman.messages.scp.abstract_scp_request.AbstractSCPRequest._get_scp_response`
        """
        return SCPReadLinkResponse()