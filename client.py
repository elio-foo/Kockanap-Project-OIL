import grpc
import greeter_pb2
import greeter_pb2_grpc

import time
import asyncio
import json

from typing import List

from Entity import *
from Message import *

async def request_generator(send_queue):
    while True:
        msg = await send_queue.get()

        if msg is None:
            break

        yield msg


def handle_incoming(msg: CommandMessage):
    if msg.operation == OperationId.ACK:
        print("ACKNOWLEGED COMMAND")
    elif msg.operation == OperationId.SERVER_UNITS:
        for unit in msg.extraJson:
            u = Unit()
            u.from_json(msg.extraJson)


async def run():
    async with grpc.aio.insecure_channel("10.4.4.59:5001") as channel:
        stub = greeter_pb2_grpc.FireRaServiceStub(channel)

        # hello
        request = greeter_pb2.HelloRequest(teamName="ObudaInnovationLab")
        response = await stub.SayHello(request)

        print("Response:", response.message)
        #    

        send_queue = asyncio.Queue(maxsize=10)

        call = stub.CommunicateWithStreams(
            request_generator(send_queue)
        )

        async def receiver():
            try:
                async for response in call:
                    handle_incoming(CommandMessage(response))
            except grpc.aio.AioRpcError as e:
                print("ERROR: ", e)
        
        async def sender():
            counter = 0
            while True:
                msg = greeter_pb2.CommandMessage(
                    teamName="ObudaInnovationLab",
                    counter=counter,
                    unitId=43,
                    operation=OperationId.NOP.value,
                    extraJson="{}"
                )

                await send_queue.put(msg)
                counter += 1

                await asyncio.sleep(1)
        
        await asyncio.gather(receiver(), sender())

if __name__ == "__main__":
    asyncio.run(run())
