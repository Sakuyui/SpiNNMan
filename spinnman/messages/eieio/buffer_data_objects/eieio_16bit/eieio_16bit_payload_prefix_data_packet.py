from spinnman.messages.eieio.eieio_type_param import EIEIOTypeParam
from spinnman.messages.eieio.buffer_data_objects.eieio_without_payload_data_packet import EIEIOWithoutPayloadDataPacket


class EIEIO16BitPayloadPrefixDataPacket(EIEIOWithoutPayloadDataPacket):

    def __init__(self, payload_prefix, data=None):
        if data is None:
            data = bytearray()

        EIEIOWithoutPayloadDataPacket.__init__(
            self, EIEIOTypeParam.KEY_16_BIT, payload_base=payload_prefix,
            data=data)

    @staticmethod
    def get_min_packet_length():
        return EIEIOWithoutPayloadDataPacket.get_min_length(
            EIEIOTypeParam.KEY_16_BIT, payload_base=0)
