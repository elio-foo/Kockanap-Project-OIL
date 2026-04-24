from Message import OperationId

import json

class CommandMessage:
    def __init__(self, server_response):
        self.teamName = server_response.teamName
        self.counter = server_response.counter
        self.operation = OperationId(server_response.operation)
        self.extraJson = json.loads(server_response.extraJson)