import socket
import threading
import logging
import traceback
from multiprocessing.pool import ThreadPool
from spinnman.connections.listeners.queuers.callback_worker import \
    CallbackWorker

logger = logging.getLogger(__name__)


class PortListener(threading.Thread):

    def __init__(self, callback, queuer, no_threads=5):
        threading.Thread.__init__(self)
        self._done = False
        self._queuer = queuer
        self._callbacks = list()
        self._callbacks.append(callback)
        self._thread_pool = ThreadPool(processes=no_threads,
                                       initializer=CallbackWorker)
        self.setDaemon(True)

    def register_callback(self, callback):
        self._callbacks.append(callback)

    def deregister_callback(self, callback):
        self._callbacks.remove(callback)

    def stop(self):
        logger.debug("[port_listener] Stopping")
        self._queuer.stop()
        self._done = True

    def set_port(self, port):
        self._queuer.set_port(port)

    def run(self):
        logger.debug("[port_listener] starting")
        self._queuer.start()
        while not self._done:
            try:
                packet = self._queuer.get_packet()
                for callback in self._callbacks:
                    self._thread_pool.apply_async(CallbackWorker.call_callback,
                                                  callback, packet)
            except socket.timeout:
                pass
            except Exception as e:
                if not self._done:
                    traceback.print_exc()
                    logger.debug("[port listener] Error receiving data: %s" % e)