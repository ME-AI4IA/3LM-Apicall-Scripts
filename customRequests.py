import requests
import json
from api.lib.singleton import SingletonMeta
from api.lib.serialize_json import read_serializable
from tools.logger import logger


class CustomRequests(metaclass=SingletonMeta):
    endpoint_data = read_serializable("./tools/endpoint.json")
    ip = endpoint_data.get("ip", None)
    port = endpoint_data.get("port", None)
    endpoint = "http://" + ip + ":" + port
    lease = None

    @classmethod
    def obtain_lease(cls):
        logger.debug("Obtaining (new) lease")
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "pdu": "login",
            "args": {
                "service": "Whisper"
            }
        }
        try:
            response = requests.post(cls.endpoint, headers=headers, data=json.dumps(data), timeout=3)
            response_data = response.json()
            cls.lease = response_data.get('args', {}).get('lease', None)
            if not cls.lease:
                raise Exception("Failed to obtain lease")
        except Exception as e:
            raise Exception(f"Error obtaining lease: {str(e)}")

    @classmethod
    def send_request(cls, data, file_path=None):
        if not cls.lease:
            cls.obtain_lease()

        headers = {
            "Content-Type": "application/json"
        }
        data["lease"] = cls.lease

        files = None
        if file_path:
            files = {
                "file": open(file_path, "rb")
            }

        try:
            if files:
                response = requests.post(cls.endpoint, data=data, files=files, timeout=30)
            else:
                response = requests.post(cls.endpoint, headers=headers, json=data, timeout=30)
        except Exception as e:
            response = requests.Response()
            if isinstance(e, requests.exceptions.ConnectTimeout):
                response.status_code = 408
            else:
                response.status_code = 500
            response._content = str(e).encode()

        if files:
            files["file"].close()

        if response.status_code == 200:
            response_dict = response.json()
        else:
            response_dict = {
                "error": f"Request failed with status code {response.status_code}",
                "details": response.content.decode('utf-8', errors='replace')
            }

        # Check for specific error message and obtain a new lease if needed
        if response_dict.get('args', {}).get('error') == 'No such lease.':
            logger.debug("No such lease error received. Obtaining a new lease.")
            cls.obtain_lease()
            return cls.send_request(data, file_path)

        return response_dict

    @classmethod
    def send_logout_request(cls):
        if cls.lease:
            data = {
                "pdu": "logout",
                "args": {
                    "lease": cls.lease
                }
            }
            response = cls.send_request(data)
            cls.lease = None
            return response
        else:
            return {"error": "No active lease"}

    @classmethod
    def send_whisper_request(cls, file_path):
        data = {
            "pdu": "query",
            "service": "Whisper",
            "query.pdu": "generate",
            "query.args.X": 1
        }
        return cls.send_request(data, file_path=file_path)

    @classmethod
    def send_llm_request(cls, file_path):
        data = {
            "pdu": "query",
            "service": "Whisper",
            "query.pdu": "talk_to_llm",
            "query.args.X": 1
        }
        return cls.send_request(data, file_path=file_path)


if __name__ == '__main__':
    transcript = CustomRequests.send_whisper_request("./speech.mp3")
    print(transcript)
