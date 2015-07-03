from spinnman.messages.eieio.command_messages.eieio_command_message\
    import EIEIOCommandMessage
from spinnman.messages.eieio.command_messages.eieio_command_header\
    import EIEIOCommandHeader
from spinnman import constants


class DatabaseConfirmation(EIEIOCommandMessage):

    def __init__(self, database_path=None):
        EIEIOCommandMessage.__init__(
            self, EIEIOCommandHeader(
                constants.EIEIO_COMMAND_IDS.DATABASE_CONFIRMATION.value))
        self._database_path = database_path

    @property
    def database_path(self):
        return self._database_path

    @property
    def bytestring(self, writer):
        data = super(DatabaseConfirmation, self).bytestring
        if self._database_path is not None:
            data += self._database_path

    @staticmethod
    def from_bytestring(command_header, data, offset):
        database_path = None
        if len(data) - offset > 0:
            database_path = data[offset:]
        return DatabaseConfirmation(database_path)
