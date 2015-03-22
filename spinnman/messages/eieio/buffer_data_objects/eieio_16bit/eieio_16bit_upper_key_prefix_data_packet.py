from spinnman.messages.eieio.eieio_type_param import EIEIOTypeParam
from spinnman.messages.eieio.eieio_prefix_type import EIEIOPrefixType
from spinnman.messages.eieio.buffer_data_objects\
    .eieio_without_payload_data_packet import EIEIOWithoutPayloadDataPacket


class EIEIO16BitLowerKeyPrefixDataPacket(EIEIOWithoutPayloadDataPacket):

    def __init__(self, key_prefix, data=None):
        if data is None:
            data = bytearray()

        EIEIOWithoutPayloadDataPacket.__init__(
            self, EIEIOTypeParam.KEY_16_BIT, prefix_param=key_prefix,
            prefix_type=EIEIOPrefixType.UPPER_HALF_WORD, data=data)

    @staticmethod
    def get_min_packet_length():
        return EIEIOWithoutPayloadDataPacket.get_min_length(
            EIEIOTypeParam.KEY_16_BIT, prefix_param=0,
            prefix_type=EIEIOPrefixType.UPPER_HALF_WORD)
