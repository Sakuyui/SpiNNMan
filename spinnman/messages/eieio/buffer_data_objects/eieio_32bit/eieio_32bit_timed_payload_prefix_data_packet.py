from spinnman.messages.eieio.eieio_type_param import EIEIOTypeParam
from spinnman.messages.eieio.buffer_data_objects.eieio_without_payload_data_packet import EIEIOWithoutPayloadDataPacket


class EIEIO32BitTimedPayloadPrefixDataPacket(EIEIOWithoutPayloadDataPacket):

    def __init__(self, timestamp, data=None):
        if data is None:
            data = bytearray()

        EIEIOWithoutPayloadDataPacket.__init__(
            self, EIEIOTypeParam.KEY_32_BIT, payload_base=timestamp,
            is_time=True, data=data)

    @staticmethod
    def get_min_packet_length():
        return EIEIOWithoutPayloadDataPacket.get_min_length(
            EIEIOTypeParam.KEY_32_BIT, payload_base=0, is_time=True)