import grpc
import greeter_pb2
import greeter_pb2_grpc

import time
import asyncio
import json

class Response():
    pass

class ServerData():
    pass

def message_generator():
    for i in range(1):
        msg = greeter_pb2.CommandMessage(
            teamName = "ObudaInnovationLab",
            counter = i + 1,
            unitId = 123,
            operation = "NOP",
            extraJson = "{}",
        )

        print("Sending: ", msg)

        yield msg
        time.sleep(1)
        
def run_stream():
    with grpc.insecure_channel("10.4.4.59:5001") as channel:
        stub = greeter_pb2_grpc.FireRaServiceStub(channel)

        # hello
        request = greeter_pb2.HelloRequest(teamName="ObudaInnovationLab")
        response = stub.SayHello(request)

        print("Response:", response.message)
        #

        responses = stub.CommunicateWithStreams(message_generator())

        for resp in responses:
            # print("Recieved: ", resp)
            data = json.loads(resp.extraJson)
            print(json.dumps(data, indent=2))


if __name__ == "__main__":
    run_stream()