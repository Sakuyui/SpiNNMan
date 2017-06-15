from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.scp.enums import SCPCommand
from spinnman.messages.sdp import SDPFlag, SDPHeader
from .scp_version_response import SCPVersionResponse


class SCPVersionRequest(AbstractSCPRequest):
    """ An SCP request to read the version of software running on a core
    """

    def __init__(self, x, y, p):
        """

        :param x: The x-coordinate of the chip to read from, between 0 and 255
        :type x: int
        :param y: The y-coordinate of the chip to read from, between 0 and 255
        :type y: int
        :param p: The id of the processor to read the version from,\
                    between 0 and 31
        :type p: int
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:
                    * If the chip coordinates are out of range
                    * If the processor is out of range
        """
        super(SCPVersionRequest, self).__init__(
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED, port=0,
                destination_cpu=p, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(command=SCPCommand.CMD_VER))

    def get_scp_response(self):
        """ See\
            :py:meth:`spinnman.messages.scp.abstract_scp_request.AbstractSCPRequest.get_scp_response`
        """
        return SCPVersionResponse()
