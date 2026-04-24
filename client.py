import grpc
import greeter_pb2
import greeter_pb2_grpc

import asyncio
import json
from itertools import count
from typing import Dict

from Entity import *
from Message import *
from Parser import parse_units

TEAM_NAME = "ObudaInnovationLab"
COMMAND_HELP = (
    "Commands:\n"
    "  move <unit_id> <up|down|left|right>\n"
    "  list\n"
    "  nop\n"
    "  quit"
)


async def request_generator(send_queue):
    while True:
        msg = await send_queue.get()

        if msg is None:
            break

        yield msg


def build_command(counter: int, unit_id: int, operation: OperationId, extra_json=None):
    return greeter_pb2.CommandMessage(
        teamName=TEAM_NAME,
        counter=counter,
        unitId=unit_id,
        operation=operation.value,
        extraJson=json.dumps(extra_json or {}),
    )


async def queue_command(send_queue, command_counter, unit_id: int, operation: OperationId, extra_json=None):
    command = build_command(next(command_counter), unit_id, operation, extra_json)
    await send_queue.put(command)
    print(f"Queued {operation.value} for unit {unit_id} (counter={command.counter})")


async def queue_move_command(send_queue, command_counter, unit_id: int, direction: str):
    operation = OperationId.from_direction(direction)
    await queue_command(send_queue, command_counter, unit_id, operation)


def print_units(units_by_id: Dict[int, Unit]):
    if not units_by_id:
        print("No units tracked yet.")
        return

    for unit_id in sorted(units_by_id):
        print(units_by_id[unit_id])


def handle_incoming(msg: CommandMessage, units_by_id: Dict[int, Unit]):
    if msg.operation == OperationId.ACK:
        print(f"ACKNOWLEDGED command #{msg.counter} for unit {msg.unitId}")
    elif msg.operation == OperationId.SERVER_UNITS:
        try:
            parsed_units = parse_units(msg.extraJson)
        except ValueError as exc:
            print(f"Could not parse server units: {exc}")
            return

        previous_count = len(units_by_id)

        for unit in parsed_units:
            if unit.id is None:
                continue
            units_by_id[unit.id] = unit

        current_count = len(units_by_id)
        if previous_count == 0 and current_count > 0:
            print(f"Initial unit sync complete. Tracking {current_count} units.")
        elif current_count != previous_count:
            print(f"Unit roster changed. Tracking {current_count} units.")
    else:
        print(
            f"Server message: operation={msg.operation.value}, "
            f"unitId={msg.unitId}, extraJson={msg.extraJson}"
        )


async def command_loop(send_queue, units_by_id: Dict[int, Unit], command_counter):
    print(COMMAND_HELP)

    while True:
        try:
            raw_command = await asyncio.to_thread(input, "Command> ")
        except EOFError:
            await send_queue.put(None)
            return

        command_text = raw_command.strip()
        if not command_text:
            continue

        parts = command_text.split()
        command_name = parts[0].lower()

        if command_name in {"quit", "exit"}:
            await send_queue.put(None)
            return

        if command_name == "help":
            print(COMMAND_HELP)
            continue

        if command_name == "list":
            print_units(units_by_id)
            continue

        if command_name == "nop":
            await queue_command(send_queue, command_counter, 0, OperationId.NOP)
            continue

        if command_name == "move":
            if len(parts) != 3:
                print("Usage: move <unit_id> <up|down|left|right>")
                continue

            try:
                unit_id = int(parts[1])
                direction = parts[2]
                if unit_id not in units_by_id:
                    print(f"Unit {unit_id} is not tracked yet, sending the move anyway.")
                await queue_move_command(send_queue, command_counter, unit_id, direction)
            except ValueError as exc:
                print(exc)
            continue

        print("Unknown command.")
        print(COMMAND_HELP)


async def run():
    async with grpc.aio.insecure_channel("10.4.4.59:5001") as channel:
        stub = greeter_pb2_grpc.FireRaServiceStub(channel)

        # hello
        request = greeter_pb2.HelloRequest(teamName=TEAM_NAME)
        response = await stub.SayHello(request)

        print("Response:", response.message)
        #    

        send_queue = asyncio.Queue(maxsize=10)
        units_by_id: Dict[int, Unit] = {}
        command_counter = count()

        call = stub.CommunicateWithStreams(
            request_generator(send_queue)
        )

        async def receiver():
            try:
                async for response in call:
                    handle_incoming(CommandMessage(response), units_by_id)
            except grpc.aio.AioRpcError as e:
                print("ERROR: ", e)

        await asyncio.gather(receiver(), command_loop(send_queue, units_by_id, command_counter))

if __name__ == "__main__":
    asyncio.run(run())
