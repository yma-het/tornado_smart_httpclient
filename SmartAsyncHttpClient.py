from tornado import gen, ioloop
from tornado.concurrent import Future
from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPError
from tornado.concurrent import TracebackFuture


def lazy_chain_future(a, b):
    """Chain two futures together so that when one completes, so does the other.

    The result (success or failure) of ``a`` will be copied to ``b``, unless
    ``b`` has already been completed or cancelled by the time ``a`` finishes.
    """
    def copy(future):
        assert future is a
        if b.done():
            try:
                a.result()
            except Exception:
                pass
            return
        a_is_tb_future = isinstance(a, TracebackFuture)
        b_is_tb_future = isinstance(b, TracebackFuture)
        if (a_is_tb_future and b_is_tb_future and a.exc_info() is not None):
            b.set_exc_info(a.exc_info())
        elif a.exception() is not None:
            b.set_exception(a.exception())
        else:
            b.set_result(a.result())
    a.add_done_callback(copy)


# url = "http://speedtest.reliableservers.com/1GBtest.bin"
# url = "http://speedtest.reliableservers.com/100MBtest.bin"
# url = "http://speedtest.reliableservers.com/10MBtest.bin"
# url = "http://localhost:1488/"
url = "https://registry.npmjs.org/007/-/007-0.0.0.tgz"


class GuarantedHTTPRequest(HTTPRequest):
    def __init__(self, *args, **kwargs):
        self._first_chunk_recieved = False
        self.timeout_handle = None
        self._io_loop = ioloop.IOLoop.current()

        if "streaming_callback" in kwargs:
            self.orig_streaming_callback = kwargs["streaming_callback"]
        else:
            self.orig_streaming_callback = None

        if "inactive_timeout" in kwargs:
            self.inactive_timeout = kwargs["inactive_timeout"]
        else:
            self.inactive_timeout = 1
        del kwargs["inactive_timeout"]

        self.timeout_future = Future()
        kwargs["streaming_callback"] = self.stream_cb

        super(GuarantedHTTPRequest, self).__init__(*args, **kwargs)

    def stream_cb(self, data):
        self._first_chunk_recieved = True
        if self.orig_streaming_callback:
            self.orig_streaming_callback(data)
        io_loop = self._io_loop
        if self.timeout_handle:
            io_loop.remove_timeout(self.timeout_handle)
        self.timeout_handle = io_loop.call_at(io_loop.time()+1,
                                              self.throwStreamingTimeout)

    def throwStreamingTimeout(self):
        err = HTTPError(
            504,
            message="No activity from server for {} second(s)".format(
                self.inactive_timeout))
        self.timeout_future.set_exception(err)

    def done(self):
        if self._first_chunk_recieved:
            io_loop = self._io_loop
            io_loop.remove_timeout(self.timeout_handle)


class GuarantedHTTPFetcher(object):
    def __init__(self, url, http_client=None, ioloop_inst=ioloop.IOLoop.current(), inactive_timeout=1, req_opts={}):
        self._chunks = []

        def get_chunk(data):
            self._chunks.append(data)

        if not http_client:
            http_client = AsyncHTTPClient(io_loop=ioloop_inst)
        self.http_client = http_client


        if not ("request_timeout" in req_opts):
            req_opts["request_timeout"] = 365*24*60*60

        self.httprequest = GuarantedHTTPRequest(
            url,
            streaming_callback=get_chunk,
            inactive_timeout=inactive_timeout,
            **req_opts
        )

    @gen.coroutine
    def fetch(self):
        # !!!!THE FUTURE BELOW WAS HANGING!!!!
        self.fetch_future = self.http_client.fetch(self.httprequest)
        lazy_chain_future(self.fetch_future, self.httprequest.timeout_future)
        combined_fetch_future = self.httprequest.timeout_future
        res = yield combined_fetch_future
        self.httprequest.done()
        try:
            res.body = "".join(self._chunks)
        except AttributeError:
            res._body = "".join(self._chunks)
        raise gen.Return(res)


@gen.coroutine
def start_test():
    http_client = AsyncHTTPClient(max_body_size=10485760000, force_instance=True)
    http_fetcher = GuarantedHTTPFetcher(url, http_client)
    try:
        response = yield http_fetcher.fetch()
        # print response.body
        print "Done!"
        import sys
        sys.exit()
    except HTTPError:
        print "Got timeout!"

if __name__ == '__main__':
    io_loop = ioloop.IOLoop.current()
    io_loop.add_callback(start_test)
    io_loop.start()
