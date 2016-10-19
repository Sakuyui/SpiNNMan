from spinnman.messages.scp.abstract_messages.abstract_scp_request\
    import AbstractSCPRequest
from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.scp.scp_request_header import SCPRequestHeader
from spinnman.messages.scp.scp_command import SCPCommand
from spinnman.messages.scp.impl.scp_check_ok_response import SCPCheckOKResponse


class SCPFillRequest(AbstractSCPRequest):
    """ An SCP request to fill a region of memory on a chip with repeated data
    """

    def __init__(self, x, y, base_address, data, size):
        """

        :param x: The x-coordinate of the chip to read from, between 0 and 255
        :type x: int
        :param y: The y-coordinate of the chip to read from, between 0 and 255
        :type y: int
        :param base_address: The positive base address to start the fill from
        :type base_address: int
        :param data: The data to fill in the space with
        :type data: int
        :param size: The number of bytes to fill in
        :type size: int
        """
        AbstractSCPRequest.__init__(
            self,
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED, destination_port=0,
                destination_cpu=0, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(command=SCPCommand.CMD_FILL),
            argument_1=base_address, argument_2=data,
            argument_3=size)

    def get_scp_response(self):
        """ See\
            :py:meth:`spinnman.messages.scp.abstract_scp_request.AbstractSCPRequest.get_scp_response`
        """
        return SCPCheckOKResponse("Fill", SCPCommand.CMD_FILL)
