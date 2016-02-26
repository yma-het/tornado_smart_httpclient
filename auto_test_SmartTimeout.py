from tornado.testing import AsyncHTTPTestCase, AsyncHTTPSTestCase, gen_test
from tornado.httpclient import AsyncHTTPClient, HTTPError
from tornado import gen
import testSmartTimeout
import os
import random
# from functools import partial


def generate_random_text(length):
    buf = ""
    written = 0
    while written < length:
        line_len = random.randint(1, 1024)
        buf += os.urandom(line_len-1) + "\n"
        written += line_len
    return buf


def produce_bad_server(request):
    fify_megabytes = 1024**2*50
    request.write("HTTP/1.1 200 OK\r\nContent-Length: %d\r\n\r\n" % (
            fify_megabytes))

    response_body = generate_random_text(fify_megabytes/2)
    request.write(response_body)


class GoodServer(object):
    def __init__(self):
        self.length = 1024**2*5
        self.response_body = generate_random_text(self.length)

    def produce_good_server(self, request):
        request.write("HTTP/1.1 200 OK\r\nContent-Length: {}\r\n\r\n{}".format(
            self.length,
            self.response_body)
        )


err_code = [None]
has_boby = [None]


def produce_err_server(request):
    if has_boby[0] == True:
        boby = "<h1>{}</h1>".format(err_code[0])
        http_response = "HTTP/1.1 %s\r\nContent-Length: %d\r\n\r\n%s" % (
            err_code[0], len(boby), boby)
        request.write(http_response)
    elif has_boby[0] == False:
        request.write("HTTP/1.1 %s\r\n\r\n" % (err_code[0]))
    else:
        print "Cannot use uninitialized pair err_code, has_boby"


class TestHTTPSmartTimeout(AsyncHTTPTestCase):
    def get_app(self):
        return produce_bad_server

    @gen_test(timeout=3000)
    def test_http_timeout(self):
        smart_timeout = .5
        url = self.get_url('/')
        print "Running test through HTTP. It must produce smart timout"
        print "Requesting: {}".format(url)
        http_client = AsyncHTTPClient(max_body_size=10485760000,
                                      io_loop=self.io_loop)
        http_fetcher = testSmartTimeout.GuarantedHTTPFetcher(
            url,
            http_client,
            inactive_timeout=smart_timeout)
        http_fetcher._io_loop = self.io_loop
        try:
            fetch_future = http_fetcher.fetch()
            response = yield fetch_future
        except HTTPError as e:
            self.assertEqual(type(e), HTTPError)
            print "Chunks has not been recieved for {} second(s), so got " \
                  "error: {}".format(smart_timeout, type(e))


class TestHTTPSSmartTimeout(AsyncHTTPSTestCase):
    def get_app(self):
        return produce_bad_server

    @gen_test(timeout=3000)
    def test_https_timeout(self):
        smart_timeout = .5
        url = self.get_url('/')
        print "Running test through HTTPS. It must produce smart timout"
        print "Requesting: {}".format(url)
        http_client = AsyncHTTPClient(max_body_size=10485760000,
                                      io_loop=self.io_loop)
        http_fetcher = testSmartTimeout.GuarantedHTTPFetcher(
            url,
            http_client,
            inactive_timeout=smart_timeout,
            req_opts={"validate_cert": False})
        http_fetcher._io_loop = self.io_loop
        try:
            fetch_future = http_fetcher.fetch()
            response = yield fetch_future
        except HTTPError as e:
            self.assertEqual(type(e), HTTPError)
            print "Chunks has not been recieved for {} second(s), so got " \
                  "error: {}".format(smart_timeout, type(e))


class TestRetryableCodesGuarantedHTTPFetcher(AsyncHTTPTestCase):
    def get_app(self):
        return produce_err_server

    @gen_test(timeout=10)
    def test_all_codes(self):
        retryable_codes = [
            {"errcode": "599 Connection Closed", "body": True},
            {"errcode": "503 Service Temporarily Unavailable", "body": True},
            {"errcode": "504 Gateway Time-out", "body": True}

            # As far as i do'n found the method to produce 104 error in
            # Tornado, it is not tested

            # {"errcode": "104 Connection Reset By Peer", "body": False}
        ]

        for code_dict in retryable_codes:
            err_code[0] = code_dict["errcode"]
            has_boby[0] = code_dict["body"]
            yield self._test_retryable_code(code_dict["errcode"])

    @gen.coroutine
    def _test_retryable_code(self, code):
        smart_timeout = .5
        url = self.get_url('/')
        print "Requesting: {}".format(url)
        http_client = AsyncHTTPClient(max_body_size=10485760000,
                                      io_loop=self.io_loop)
        http_fetcher = testSmartTimeout.GuarantedHTTPFetcher(
            url,
            http_client,
            inactive_timeout=smart_timeout)
        http_fetcher._io_loop = self.io_loop
        try:
            fetch_future = http_fetcher.fetch()
            response = yield fetch_future
        except HTTPError as e:
            http_fetcher.httprequest.done()
            self.assertEqual(type(e), HTTPError)
            tornado_http_err = "HTTP {}: {}".format(code[:3], code[4:])
            self.assertEqual(tornado_http_err, str(e))
            print "Got HTTPError {} expected to get: {}".format(
                e, code)


class TestSuccessGuarantedHTTPFetcher(AsyncHTTPTestCase):
    def get_app(self):
        self._server = GoodServer()
        return self._server.produce_good_server

    @gen_test(timeout=3000)
    def test_good_scenario(self):
        smart_timeout = .5
        url = self.get_url('/')
        print "Running success test case, must produce 200 OK"
        print "Requesting: {}".format(url)
        http_client = AsyncHTTPClient(max_body_size=10485760000,
                                      io_loop=self.io_loop)
        http_fetcher = testSmartTimeout.GuarantedHTTPFetcher(
            url,
            http_client,
            inactive_timeout=smart_timeout)
        http_fetcher._io_loop = self.io_loop
        response = yield http_fetcher.fetch()
        self.assertEqual(self._server.response_body, response.body)
        print "All seems to be ok, response body is the same as server input"

        # try:

        # except HTTPError as e:
        #     self.assertEqual(type(e), HTTPError)
        #     print "Chunks has not been recieved for {} second(s), so got " \
        #           "error: {}".format(smart_timeout, type(e))
