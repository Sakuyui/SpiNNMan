from spinnman.messages.eieio.eieio_type import EIEIOType
from spinnman.messages.eieio.data_messages.eieio_without_payload_data_message\
    import EIEIOWithoutPayloadDataMessage
from spinnman.messages.eieio.data_messages.eieio_data_header\
    import EIEIODataHeader
from spinnman.messages.eieio.data_messages.eieio_data_message\
    import EIEIODataMessage


class EIEIO16BitTimedPayloadPrefixDataMessage(EIEIOWithoutPayloadDataMessage):

    def __init__(self, timestamp, count=0, data_reader=None):

        EIEIOWithoutPayloadDataMessage.__init__(
            self, EIEIODataHeader(EIEIOType.KEY_16_BIT, payload_base=timestamp,
                                  is_time=True, count=count),
            data_reader)

    @staticmethod
    def get_min_packet_length():
        return EIEIODataMessage.min_packet_length(
            EIEIOType.KEY_16_BIT, is_payload_base=True)