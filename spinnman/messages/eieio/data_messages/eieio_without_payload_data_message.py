from spinnman.exceptions import SpinnmanInvalidParameterException
from spinnman.messages.eieio.data_messages \
    import EIEIODataMessage, EIEIOKeyDataElement


class EIEIOWithoutPayloadDataMessage(EIEIODataMessage):
    """ An EIEIO message without a payload
    """

    def __init__(self, eieio_header, data=None, offset=0):
        EIEIODataMessage.__init__(self, eieio_header, data, offset)

        if eieio_header.eieio_type.payload_bytes != 0:
            raise SpinnmanInvalidParameterException(
                "eieio_header", eieio_header,
                "This message should have no payload, but the header indicates"
                " that it does")

    def add_key(self, key):
        """ Add a key to the packet

        :param key: The key to add
        :type key: int
        :raise SpinnmanInvalidParameterException: If the key is too\
                    big for the format
        """
        if key > self._header.eieio_type.max_value:
            raise SpinnmanInvalidParameterException(
                "key", key,
                "Larger than the maximum allowed of {}".format(
                    self._header.eieio_type.max_value))
        EIEIODataMessage.add_element(self, EIEIOKeyDataElement(key))
