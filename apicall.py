import requests
import json
from collections.abc import Sequence, KeysView
import numpy as np
import atexit
import argparse
import sys

def string2array(s):
    s = s.replace('\\', '').replace('\n', '')
    if s.startswith('[') and s.endswith(']'):
        return eval(s)

# endpoint = "http://172.24.132.8:8800/"
endpoint = "http://10.100.100.12:8800/"
script_version = "1.0.0"


class RequestBase:
    """
    Base class for sending HTTP POST requests to a specified endpoint.
    """

    def __init__(self, endpoint):
        self.endpoint = endpoint

    def send_request(self, data, file_path=None):
        headers = {"Content-Type": "application/json"}

        if file_path is None:
            response = requests.post(self.endpoint, headers=headers, data=json.dumps(data))
        else:  
            files = {
                "file": open(file_path, "rb")
            }
            response = requests.post(self.endpoint, data=data, files=files)

        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Request failed with status code {response.status_code}: {response.text}"}
    
    @staticmethod
    def make_call_arguments(lease, service, method, args):
        return {
            "pdu": "query", 
            "args": {
                "lease": lease, 
                "service": service, 
                "query": {
                    "pdu": method, 
                    "args": args
                }
            }
        }
        

class LoginRequest(RequestBase):
    def request(self, service):
        data = {"pdu": "login", "args": {"service": service}}
        return self.send_request(data)
    

class LogoutRequest(RequestBase):
    def request(self, lease):
        data = {"pdu": "logout", "args": {"lease": lease}}
        return self.send_request(data)


class LlmRequest(RequestBase):
    def request(self, lease, prompt, model="llama31:latest", **kwargs):
        data = RequestBase.make_call_arguments(lease, "Llm_Manager", "generate", {
            "model": model,
            "prompt": prompt
        })
        return self.send_request(data)
    

class OCRRequest(RequestBase):
    def request(self, lease, file_path, **kwargs):
        data = {
            "pdu": "query",
            "lease": lease,
            "service": "OCR",
            "query.pdu": "generate",
        }
        for key, value in kwargs.items():
            data[f"query.args.{key}"] = value

        return self.send_request(data, file_path)


class ApiCall:
    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.lease = None
        self.requests = {
            "login": LoginRequest(endpoint),
            "logout": LogoutRequest(endpoint),
        }
        atexit.register(self._clean_up)

    def _clean_up(self):
        print("Cleaning up")
        print(self.lease)
        if self.lease is not None:
            print("Logging out")
            try:
                res = self.requests["logout"].request(self.lease)
                print("Logged out: ", res)
            except Exception as e:
                print(f"Failed to logout: {e}")

    def _check_lease(self, service):
        if self.lease is None:
            try:
                _lease = self.requests["login"].request(service)['args']['lease']
                self.lease = _lease
            except:
                print("Could not get lease")
                raise Exception("Could not get lease")

    def get_services(self):
        return self.requests.keys()
    
    def reqister_service(self, service):
        serv = ApiCall.as_list(service)

        for s in serv: 
            if ApiCall.as_list(s.keys(), string2array) != ['name', 'request']:
                raise ValueError("Service must have 'name' and 'request' keys")
            self.requests[s['name']] = s['request']

    def send_request(self, service, data, cont_mode=True, **kwargs):
        self._check_lease(service=service)
        
        if service not in self.requests.keys():
            raise Exception(f"Service {service} not available")
        
        res = self.requests[service].request(self.lease, data, **kwargs)
        if not cont_mode:
            self.requests["logout"].request(self.lease)
        return res
    
    def send_raw_request(self, data, cont_mode=True):
        self._check_lease(service=data['args']['service'])
        data['args']['lease'] = self.lease
        res = RequestBase(self.endpoint).send_request(data)
        if not cont_mode:
            self.requests["logout"].request(self.lease)
        return res

    @staticmethod
    def as_list(x, string_conversion_strategy=None):
        def is_sequence(obj):
            return (isinstance(obj, Sequence) or isinstance(x, KeysView)) and not isinstance(obj, (str, bytes, bytearray))

        if x is None:
            return []
        if is_sequence(x):
            return list(x)
        if isinstance(x, str):
            if string_conversion_strategy is not None:
                return string_conversion_strategy(x)
        return [x]


def check_parameters(args):
    """
    Checks that required parameters are present and valid.
    
    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        
    Raises:
        ValueError: If a required parameter is missing or invalid.
    """
    if not args.service:
        raise ValueError("Missing required parameter: 'service'")
    if args.service == "llm" and not args.prompt:
        raise ValueError("Missing required parameter: 'prompt' for LLM service")


def process_arguments(argv):
    class CustomFormatter(argparse.HelpFormatter):
        def _format_usage(self, usage, actions, groups, prefix):
            # This method formats the usage message
            if prefix is None:
                prefix = 'Usage: '

            format_description = super()._format_usage(usage, actions, groups, prefix)
            extended_format_description = f'{format_description[:-2]} [endpoint] method [argument=value]*\n\n'
            return extended_format_description

        def _format_text(self, text):
            return text
        
    def read_stdin():
        """
        Reads all input from standard input (stdin) until EOF is reached.
        Returns the collected input as a single string, with the last newline removed.
        """
        input_lines = []
        for line in sys.stdin:
            input_lines.append(line)

        if len(input_lines[-1]) == 0:
            del input_lines[-1]

        result = ' '.join(input_lines)
        return result[:-1]
    

    # Step 1: Set up argparse
    parser = argparse.ArgumentParser(
        description=f"""Version: {script_version}
Call a service method.

'endpoint' is an optional url to be used for the session. Default is http://127.0.0.1:8800.
'method' is of the form [service.]method_name. Uses the session's service if missing. Default is 'llm'.
'endpoint' and 'service' are stored for the session once provided.

You may provide arguments to the call using argument=value, where 'argument' is a json path.
If 'value' is a single minus sign, the value is read from the console instead.
        """,
        formatter_class=CustomFormatter
    )
    either_continue_or_end = parser.add_mutually_exclusive_group()
    either_continue_or_end.add_argument(
        '-c',
        action='store_true',
        help='Continuous Mode: start or continue a session, keep the login active.'
    )
    either_continue_or_end.add_argument(
        '-e',
        action='store_true',
        help='End Query Mode: logout after the call completed.'
    )
    either_list_or_delete = parser.add_mutually_exclusive_group()
    either_list_or_delete.add_argument(
        '-d',
        action='store_true',
        help="Delete the session. The default session can not be deleted."
    )
    either_list_or_delete.add_argument('-l', action='store_true', help='List defined sessions.')
    parser.add_argument(
        '-s',
        nargs=1,
        default='default',
        help="""Use a named session.
        Start a session with -cs and end it with -es, where "S" is the name of the session.
        Default is 'default'."""
    )
    parser.add_argument('-u', nargs=1, default='', help='provide a user id to login')
    parser.add_argument('-v', action='store_true', help='Enable verbose output.')

    # Step 2: Parse known arguments (options)
    options, remaining_args = parser.parse_known_args(argv)

    # Initialize structures for storing different types of arguments
    basic_arguments = []
    arguments = {}

    # Step 3: Process remaining arguments
    for arg in remaining_args:
        # Check for key-value format
        if '=' in arg:
            key, value = arg.split('=')
            if value == '-':
                print(key, ':', end=' ', flush=True)
                value = read_stdin()
            elif value[0] == '@':
                value_from_file = open(value[1:], 'r').read()
                value = json.loads(value_from_file)
            arguments[key] = value
        else:
            # Add to basic arguments, ensuring no more than two are added
            if len(basic_arguments) < 2:
                basic_arguments.append(arg)

    # Step 4: interpret basic arguments
    if len(basic_arguments) > 2:
        print('Too many non-argument parameters. Only "endpoint" and "method" are accepted.')
        sys.exit(1)

    if len(basic_arguments) == 2:
        endpoint, method = basic_arguments
    elif len(basic_arguments) == 1:
        endpoint, method = None, basic_arguments[0]
    else:
        endpoint, method = None, None

    if method is None:
        service, function = None, None
    elif '.' in method:
        service, function = method.rsplit('.', maxsplit=1)
    else:
        service, function = None, method

    return {
        'endpoint': endpoint,
        'service': service,
        'function': function,
        'arguments': arguments,
        'options': options
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        args = process_arguments(sys.argv[1:])

        # Initialize ApiCall with endpoint and add services
        api = ApiCall(args['endpoint'] if args['endpoint'] else endpoint)
        call_data = RequestBase.make_call_arguments(0, args['service'], args['function'], args['arguments'])
        call_options = {key: value for key, value in vars(args['options']).items()}

        res = api.send_raw_request(call_data, call_options['c'])
        print(res)
    else:
        api = ApiCall(endpoint)

        api.reqister_service({'name': 'llm', 'request': LlmRequest(endpoint)})
        response = api.send_request('llm', "Hello, world!")
        print(response)

        # api.reqister_service({'name': 'ocr', 'request': OCRRequest(endpoint)})
        # response = api.send_request('ocr', 'exampletext.jpg', details=0)
        # print(response['args']['output'])
