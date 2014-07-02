from abc import ABCMeta
from abc import abstractmethod
from six import add_metaclass

from spinnman.connections.abstract_connection import AbstractConnection

@add_metaclass(ABCMeta)
class AbstractSCPReceiver(AbstractConnection):
    """ A receiver of SCP messages
    """
    
    @abstractmethod
    def receive_scp_message(self, timeout=None):
        """ Receives an SCP message from this connection.  Blocks\
            until a message has been received, or a timeout occurs.
        
        :param timeout: The time in seconds to wait for the message to arrive;\
                    if not specified, will wait forever, or until the\
                    connection is closed
        :type timeout: int
        :return: an SCP message
        :rtype: :py:class:`spinnman.messages.scp_message.SCPMessage`
        :raise spinnman.exceptions.SpinnmanIOException: If there is an error\
                    receiving the message
        :raise spinnman.exceptions.SpinnmanTimeoutException: If there is a\
                    timeout before a message is received
        :raise spinnman.exceptions.SpinnmanInvalidPacketException: If the\
                    received packet is not a valid SCP message
        :raise spinnman.exceptions.SpinnmanInvalidParameterException: If one of\
                    the fields of the SCP message is invalid
        """
        pass