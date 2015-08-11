"""
SCPPowerRequest
"""

# spinnman imports
from spinnman.messages.scp.abstract_messages.abstract_scp_bmp_request import \
    AbstractSCPBMPRequest
from spinnman.messages.scp.impl.scp_check_ok_response import SCPCheckOKResponse
from spinnman.messages.scp.scp_command import SCPCommand
from spinnman.messages.scp.scp_request_header import SCPRequestHeader


class SCPPowerRequest(AbstractSCPBMPRequest):
    """ An SCP request for the BMP to power on or power off a rack of boards
    """

    def __init__(self, power_command, boards, delay=0.0):
        """
        :param power_command: The power command being sent
        :type power_command:\
                :py:class:`spinnman.messages.scp.scp_power_command.SCPPowerCommand`
        :param boards: The boards on the same backplane to power on or off
        :type board: int or iterable of int
        :param delay: Number of seconds delay between power state changes of\
                the different boards.
        :type delay: int
        :return:
        """

        arg1 = (int(delay * 1000) << 16) | power_command.value
        arg2 = self.get_board_mask(boards)

        AbstractSCPBMPRequest.__init__(
            self, boards,
            SCPRequestHeader(command=SCPCommand.CMD_BMP_POWER),
            argument_1=arg1, argument_2=arg2)

    def get_scp_response(self):
        """ Get the response from the powering message
        """
        return SCPCheckOKResponse("powering request", "CMD_BMP_POWER")