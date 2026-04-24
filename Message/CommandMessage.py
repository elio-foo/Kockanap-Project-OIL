from Message import OperationId

import json

class CommandMessage:
    def __init__(self, server_response):
        self.teamName = server_response.teamName
        self.counter = server_response.counter
        self.unitId = server_response.unitId
        self.operation = OperationId(server_response.operation)
        raw_extra_json = server_response.extraJson.strip()
        self.extraJson = json.loads(raw_extra_json) if raw_extra_json else {}
