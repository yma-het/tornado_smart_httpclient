# Smart http client for tornado
This class is aimed to throw HTTPError, when request to server has been sent and response chunks has not been recieved for time, determined by user.
Usage:
```shell
fetcher = GuarantedHTTPFetcher(url, inactive_timeout=smart_timeout)
try:
    response = yield response fetcher.fetch()
except HTTPError as e:
    print e
```
To run tests execute:
```
python -m tornado.test.runtests auto_test_SmartAsyncHttpClient
```
