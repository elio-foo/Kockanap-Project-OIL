import grpc
import greeter_pb2
import greeter_pb2_grpc

import time
import asyncio
import json

class Response:
    def __init__(self, raw_data):
        self.teamName = raw_data.teamName
        self.counter = raw_data.counter
        self.operation = raw_data.operation
        self.extraJson = raw_data.extraJson

async def message_generator():
    for i in range(5):
        msg = greeter_pb2.CommandMessage(
            teamName = "ObudaInnovationLab",
            counter = i + 1,
            unitId = 123,
            operation = "NOP",
            extraJson = "{}",
        )

        print("Sending: ", msg)

        yield msg
        await asyncio.sleep(1)
        
async def run_stream():
    async with grpc.aio.insecure_channel("10.4.4.59:5001") as channel:
        stub = greeter_pb2_grpc.FireRaServiceStub(channel)

        # hello
        request = greeter_pb2.HelloRequest(teamName="ObudaInnovationLab")
        response = await stub.SayHello(request)

        print("Response:", response.message)

        responses = stub.CommunicateWithStreams()

        async for resp in responses:
            r = Response(resp)

            print(r.teamName)


if __name__ == "__main__":
    asyncio.run(run_stream())