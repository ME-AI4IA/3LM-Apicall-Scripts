import requests
import json
from collections.abc import Sequence
import numpy as np

# endpoint = "http://172.24.132.8:8800/"
endpoint = "http://10.100.100.12:8800/"

# url = "http://172.24.132.8:8800/"
url = "http://10.100.100.12:8800/"


def is_sequence(obj):
 """
 Check if the object is a sequence but not a string, bytes, or bytearray.

 Args:
 obj (object): The object to be checked.

 Returns:
 bool: True if the object is a sequence but not a string, bytes, or bytearray. False otherwise.
 """
 return isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray))


def as_list(x):
    """
    Return the parameter as a list. If it was one before, return a clone.
    :param x: None, a list or a value
    :return: a new list - None results in an empty list.
    """
    if x is None:
        return []
    if is_sequence(x):
        return list(x)
    if isinstance(x, str):
        x = x.replace('\\', '').replace('\n', '')
        if x.startswith('[') and x.endswith(']'):
            return eval(x)
    return [x]

# curl -X POST -H "Content-Type: application/json" -d "{\"pdu\":\"login\", \"args\":{\"service\":\"Whisper\"}}" -s http://172.24.132.8:8800/
def send_login_request():
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "pdu": "login",
        "args": {
            "service": "Whisper"
        }
    }

    # Send the POST request
    response = requests.post(endpoint, headers=headers, data=json.dumps(data))

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the response JSON into a dictionary
        response_dict = response.json()
    else:
        response_dict = {
            "error": f"Request failed with status code {response.status_code}"
        }

    return response_dict


# curl -X POST -H "Content-Type: application/json" -d "{\"pdu\":\"logout\", \"args\":{\"lease\":\"NsHxNKrCICSVjtOSZMXzpnGvjNcloJTJBpwrfIGjXpmWYWQvivSiOCkbjAfeZUxr\"}}" -s http://172.24.132.8:8800/
def send_logout_request(lease):
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "pdu": "logout",
        "args": {
            "lease": lease
        }
    }

    # Send the POST request
    response = requests.post(endpoint, headers=headers, data=json.dumps(data))

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the response JSON into a dictionary
        response_dict = response.json()
    else:
        response_dict = {
            "error": f"Request failed with status code {response.status_code}"
        }

    return response_dict


# curl -X POST -F "pdu=query" -F "lease=MZvQYtVAgbOdlQpFxHMvodDwGUWGJMzNJeNfDbvUVseyZoAuyJfmnXBUyVKfwmld" -F "service=Whisper" -F "query.pdu=generate" -F "query.args.X=1" -F "file=@speech.mp3" http://172.24.132.8:8800/
def send_ocr_request(lease, file_path, **kwargs):
    data = {
        "pdu": "query",
        "lease": lease,
        "service": "OCR",
        "query.pdu": "generate",
    }

    for key, value in kwargs.items():
        data[f"query.args.{key}"] = value

    files = {
        "file": open(file_path, "rb")
    }

    # Send the POST request
    response = requests.post(endpoint, data=data, files=files)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the response JSON into a dictionary
        response_dict = response.json()
    else:
        response_dict = {
            "error": f"Request failed with status code {response.status_code}"
        }

    return response_dict

if __name__ == "__main__":
    lease = send_login_request()['args']['lease']
    print(lease)
    res = send_ocr_request(lease, "./exampletext.jpg", details=1)['args']['output']
    res = as_list(res)
    for i in res:
        print(i)
    
    send_logout_request(lease)