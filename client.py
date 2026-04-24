import grpc
import greeter_pb2
import greeter_pb2_grpc

import time
import asyncio
import json

from Message import *

async def message_generator():
    for i in range(1):
        msg = greeter_pb2.CommandMessage(
            teamName = "ObudaInnovationLab",
            counter = i + 1,
            unitId = 43,
            operation = "Left",
            extraJson = "{}",
        )

        print("Sending: ", msg)

        yield msg
        await asyncio.sleep(1)

def handle_server_message(message: CommandMessage):
    print(message.teamName)
    print(message.counter)
    print(message.operation)
    print(json.dumps(message.extraJson, indent=2))
        
async def run_stream():
    async with grpc.aio.insecure_channel("10.4.4.59:5001") as channel:
        stub = greeter_pb2_grpc.FireRaServiceStub(channel)

        # hello
        request = greeter_pb2.HelloRequest(teamName="ObudaInnovationLab")
        response = await stub.SayHello(request)

        print("Response:", response.message)

        responses = stub.CommunicateWithStreams(message_generator())

        async for resp in responses:
            handle_server_message(CommandMessage(resp))

if __name__ == "__main__":
    asyncio.run(run_stream())