from spinnman.messages.eieio.eieio_type_param import EIEIOTypeParam
from spinnman.messages.eieio.eieio_prefix_type import EIEIOPrefixType
from spinnman.messages.eieio.buffer_data_objects\
    .eieio_with_payload_data_packet import EIEIOWithPayloadDataPacket


class EIEIO16BitWithPayloadTimedLowerKeyPrefixDataPacket(
        EIEIOWithPayloadDataPacket):

    def __init__(self, key_prefix, data=None):
        if data is None:
            data = bytearray()

        EIEIOWithPayloadDataPacket.__init__(
            self, EIEIOTypeParam.KEY_PAYLOAD_16_BIT, prefix_param=key_prefix,
            prefix_type=EIEIOPrefixType.LOWER_HALF_WORD, is_time=True,
            data=data)

    @staticmethod
    def get_min_packet_length():
        return EIEIOWithPayloadDataPacket.get_min_length(
            EIEIOTypeParam.KEY_PAYLOAD_16_BIT, prefix_param=0,
            prefix_type=EIEIOPrefixType.LOWER_HALF_WORD, is_time=True)
