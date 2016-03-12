from spinnman.messages.scp.impl.scp_sdram_alloc_request import \
    SCPSDRAMAllocRequest
from spinnman.processes\
    .multi_connection_process_most_direct_connection_selector \
    import MultiConnectionProcessMostDirectConnectionSelector
from spinnman.processes.abstract_multi_connection_process \
    import AbstractMultiConnectionProcess


class MallocSDRAMProcess(AbstractMultiConnectionProcess):

    def __init__(self, machine, connections):
        AbstractMultiConnectionProcess.__init__(
            self, connections,
            MultiConnectionProcessMostDirectConnectionSelector(
                machine, connections))
        self._connections = connections
        self._base_address = None

    def handle_sdram_alloc_response(self, response):
        self._base_address = response.base_address

    def malloc_sdram(self, x, y, size, app_id, tag):
        # Allocate space in the sdram space
        self._send_request(SCPSDRAMAllocRequest(x, y, app_id, size, tag),
                           self.handle_sdram_alloc_response)
        self._finish()
        self.check_for_error()

    @property
    def base_address(self):
        return self._base_address