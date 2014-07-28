from spinnman.messages.scp.abstract_scp_request import AbstractSCPRequest
from spinnman.exceptions import SpinnmanInvalidParameterException
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.scp.scp_request_header import SCPRequestHeader
from spinnman.messages.scp.scp_command import SCPCommand
from spinnman.messages.scp.impl.scp_check_ok_response import SCPCheckOKResponse


class SCPRouterInitRequest(AbstractSCPRequest):
    """ A request to initialize the router on a chip
    """

    def __init__(self, x, y, n_entries, table_address, base_address):
        """

        :param x: The x-coordinate of the chip, between 0 and 255
        :type x: int
        :param y: The y-coordinate of the chip, between 0 and 255
        :type y: int
        :param n_entries: The number of entries in the table, more than 0
        :type n_entries: int
        :param table_address: The allocated table address
        :type table_address: int
        :param base_address: The base_address containing the entries
        :type base_address: int
        :raise spinnman.exceptions.SpinnmanInvalidParameterException:\
                    * If x is out of range
                    * If y is out of range
                    * If n_entries is 0 or less
                    * If table_address is not positive
                    * If base_address is not positive
        """
        if n_entries < 1:
            raise SpinnmanInvalidParameterException(
                "n_entries", str(n_entries),
                "Must be more than 0")
        if base_address < 0:
            raise SpinnmanInvalidParameterException(
                "base_address", str(base_address),
                "Must be a positive integer")
        if table_address < 0:
            raise SpinnmanInvalidParameterException(
                "table_address", str(table_address),
                "Must be a positive integer")

        super(SCPRouterInitRequest, self).__init__(
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED, destination_port=0,
                destination_cpu=0, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(command=SCPCommand.CMD_RTR),
            argument_1=((n_entries << 16) | 2),
            argument_2=table_address, argument_3=base_address)

    def get_scp_response(self):
        return SCPCheckOKResponse("RouterInit", "CMD_RTR")