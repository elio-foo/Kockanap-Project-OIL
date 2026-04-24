import grpc
import greeter_pb2
import greeter_pb2_grpc

import asyncio
from typing import Dict

from Entity import *
from Message import *
from Parser import parse_units

async def request_generator(send_queue):
    while True:
        msg = await send_queue.get()

        if msg is None:
            break

        yield msg


def handle_incoming(msg: CommandMessage, units_by_id: Dict[int, Unit]):
    if msg.operation == OperationId.ACK:
        print("ACKNOWLEGED COMMAND")
    elif msg.operation == OperationId.SERVER_UNITS:
        try:
            parsed_units = parse_units(msg.extraJson)
        except ValueError as exc:
            print(f"Could not parse server units: {exc}")
            return

        for unit in parsed_units:
            if unit.id is None:
                continue
            units_by_id[unit.id] = unit

        print(f"Tracked {len(units_by_id)} units")
        for unit in parsed_units:
            print(unit)


async def run():
    async with grpc.aio.insecure_channel("10.4.4.59:5001") as channel:
        stub = greeter_pb2_grpc.FireRaServiceStub(channel)

        # hello
        request = greeter_pb2.HelloRequest(teamName="ObudaInnovationLab")
        response = await stub.SayHello(request)

        print("Response:", response.message)
        #    

        send_queue = asyncio.Queue(maxsize=10)
        units_by_id: Dict[int, Unit] = {}

        call = stub.CommunicateWithStreams(
            request_generator(send_queue)
        )

        async def receiver():
            try:
                async for response in call:
                    handle_incoming(CommandMessage(response), units_by_id)
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
