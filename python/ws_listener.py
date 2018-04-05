import socket
import asyncio
import websockets
import time
import logging
import threading
from os import environ

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
streamHandler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)


class WSClient():

    def __init__(self, url, **kwargs):
        self.url = url
        self.observer = []
        self.reply_timeout = kwargs.get('reply_timeout', 10)
        self.ping_timeout = kwargs.get('ping_timeout', 5)
        self.sleep_time = kwargs.get('sleep_time', 5)

    def register(self, obs):
        if not hasattr(obs, 'notify'):
            logger.warning('Observers must have a *notify* callback')
            return False
        self.observer.append(obs)
        logger.debug('New observer has registered')
        return True

    def unregister(self, obs):
        try:
            self.observer.remove(obs)
            return True
        except:
            # not in the list
            return False

    async def listen_forever(self):
        while True:
        # outer loop restarted every time the connection fails
            logger.debug('Creating new connection...')
            try:
                async with websockets.connect(self.url) as ws:
                    while True:
                    # listener loop
                        try:
                            reply = await asyncio.wait_for(ws.recv(), timeout=self.reply_timeout)
                        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                            try:
                                pong = await ws.ping()
                                await asyncio.wait_for(pong, timeout=self.ping_timeout)
                                logger.debug('Ping OK, keeping connection alive...')
                                continue
                            except:
                                logger.debug(
                                    'Ping error - retrying connection in {} sec (Ctrl-C to quit)'.format(self.sleep_time))
                                await asyncio.sleep(self.sleep_time)
                                break
                        logger.debug('Server said > {}'.format(reply))
                        for obs in self.observer:
                            obs.notify(self, reply)
                        logger.debug('Observers notified')
            except socket.gaierror:
                logger.debug(
                    'Socket error - retrying connection in {} sec (Ctrl-C to quit)'.format(self.sleep_time))
                await asyncio.sleep(self.sleep_time)
                continue
            except ConnectionRefusedError:
                logger.debug('Nobody seems to listen to this endpoint. Please check the URL.')
                logger.debug('Retrying connection in {} sec (Ctrl-C to quit)'.format(self.sleep_time))
                await asyncio.sleep(self.sleep_time)
                continue


def start_ws_client(client):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(client.listen_forever())


class A():
    # a short example of observer object
    def __init__(self, idx=None):
        self.idx = idx

    def notify(self, notifier, message):
        print('A {}, got message {}'.format(self.idx, message))


# Run it as standalone
if __name__ == '__main__':
    url = "ws://127.0.0.1:8000/macro/sample/"
    params = {'ping_timeout': 5,
              'reply_timeout': 10,
              'sleep_time': 5}
    client = WSClient(url, **params)
    a = A(idx=int(time.time()))
    client.register(a)
    wst = threading.Thread(
        target=start_ws_client, args=(client,))
    wst.daemon = True
    wst.start()
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            logger.info('Exiting...')
            sys.exit(0)
