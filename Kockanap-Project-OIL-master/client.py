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
from UnitLogic import MapTracker, UnitLogicContext, UnitLogicDispatcher

TEAM_NAME = "ObudaInnovationLab"
AUTO_LOGIC_INTERVAL_SECONDS = 0.5
COMMAND_HELP = (
    f"Auto logic: enabled for all controlled units every {AUTO_LOGIC_INTERVAL_SECONDS:.1f}s\n"
    "Commands:\n"
    "  move <unit_id> <up|down|left|right>\n"
    "  logic [unit_id|all]\n"
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


def get_controlled_unit(units_by_id: Dict[int, Unit], unit_id: int) -> Unit | None:
    unit = units_by_id.get(unit_id)
    if unit is None:
        return None

    if unit.owner != TEAM_NAME:
        return None

    return unit


def get_controlled_units(units_by_id: Dict[int, Unit]) -> list[Unit]:
    return [unit for unit in units_by_id.values() if unit.owner == TEAM_NAME]


async def run_unit_logic(
    dispatcher: UnitLogicDispatcher,
    units_by_id: Dict[int, Unit],
    map_tracker: MapTracker,
    queue_command_for_unit,
    queue_move_for_unit,
    target_unit_id: int | None = None,
    announce_result: bool = True,
):
    if not units_by_id:
        if announce_result:
            print("No units tracked yet.")
        return

    context = UnitLogicContext(
        units_by_id=units_by_id,
        queue_command=queue_command_for_unit,
        queue_move=queue_move_for_unit,
        map_tracker=map_tracker,
    )

    if target_unit_id is not None:
        unit = get_controlled_unit(units_by_id, target_unit_id)
        if unit is None:
            tracked_unit = units_by_id.get(target_unit_id)
            if tracked_unit is None and announce_result:
                print(f"Unit {target_unit_id} is not tracked yet.")
            elif tracked_unit is not None and announce_result:
                print(
                    f"Unit {target_unit_id} is tracked but owned by {tracked_unit.owner}, "
                    "so logic will not run for it."
                )
            return

        handled = await dispatcher.run_for_unit(unit, context)
        if not handled:
            if announce_result:
                print(f"No unit logic registered for unit {target_unit_id}.")
            return

        if announce_result:
            print(f"Ran logic for unit {target_unit_id} ({unit.type}).")
        return

    controlled_units = get_controlled_units(units_by_id)
    if not controlled_units:
        if announce_result:
            print(f"No controlled units for team {TEAM_NAME} are tracked yet.")
        return

    handled_count = await dispatcher.run_for_units(controlled_units, context)
    if announce_result:
        print(f"Ran logic for {handled_count} controlled unit(s).")


def handle_incoming(msg: CommandMessage, units_by_id: Dict[int, Unit], map_tracker: MapTracker):
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

        map_tracker.update_from_units(units_by_id)

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


async def auto_logic_loop(
    dispatcher: UnitLogicDispatcher,
    logic_lock: asyncio.Lock,
    units_by_id: Dict[int, Unit],
    map_tracker: MapTracker,
    queue_command_for_unit,
    queue_move_for_unit,
):
    while True:
        await asyncio.sleep(AUTO_LOGIC_INTERVAL_SECONDS)

        if not units_by_id:
            continue

        async with logic_lock:
            await run_unit_logic(
                dispatcher,
                units_by_id,
                map_tracker,
                queue_command_for_unit,
                queue_move_for_unit,
                announce_result=False,
            )


async def command_loop(
    send_queue,
    units_by_id: Dict[int, Unit],
    map_tracker: MapTracker,
    command_counter,
    logic_dispatcher: UnitLogicDispatcher,
    logic_lock: asyncio.Lock,
    queue_command_for_unit,
    queue_move_for_unit,
):
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

        if command_name == "logic":
            if len(parts) > 2:
                print("Usage: logic [unit_id|all]")
                continue

            target_unit_id = None
            if len(parts) == 2 and parts[1].lower() != "all":
                try:
                    target_unit_id = int(parts[1])
                except ValueError:
                    print("Usage: logic [unit_id|all]")
                    continue

            async with logic_lock:
                await run_unit_logic(
                    logic_dispatcher,
                    units_by_id,
                    map_tracker,
                    queue_command_for_unit,
                    queue_move_for_unit,
                    target_unit_id,
                )
            continue

        if command_name == "move":
            if len(parts) != 3:
                print("Usage: move <unit_id> <up|down|left|right>")
                continue

            try:
                unit_id = int(parts[1])
                direction = parts[2]
                unit = get_controlled_unit(units_by_id, unit_id)
                if unit is None:
                    tracked_unit = units_by_id.get(unit_id)
                    if tracked_unit is None:
                        print(f"Unit {unit_id} is not tracked yet. Use `list` after the next sync.")
                    else:
                        print(
                            f"Unit {unit_id} belongs to {tracked_unit.owner}, not {TEAM_NAME}. "
                            "Skipping the move to avoid steering the wrong unit."
                        )
                    continue

                print(
                    f"Sending move {direction} to unit {unit_id} "
                    f"({unit.type}, owner={unit.owner}, position={unit.position})."
                )
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
        map_tracker = MapTracker("map.txt")
        command_counter = count()
        logic_dispatcher = UnitLogicDispatcher()
        logic_lock = asyncio.Lock()

        call = stub.CommunicateWithStreams(
            request_generator(send_queue)
        )

        async def queue_command_for_unit(unit_id: int, operation: OperationId, extra_json=None):
            await queue_command(send_queue, command_counter, unit_id, operation, extra_json)

        async def queue_move_for_unit(unit_id: int, direction: str):
            await queue_move_command(send_queue, command_counter, unit_id, direction)

        async def receiver():
            try:
                async for response in call:
                    handle_incoming(CommandMessage(response), units_by_id, map_tracker)
            except asyncio.CancelledError:
                raise
            except grpc.aio.AioRpcError as e:
                if e.code() != grpc.StatusCode.CANCELLED:
                    print("ERROR: ", e)

        receiver_task = asyncio.create_task(receiver())
        auto_logic_task = asyncio.create_task(
            auto_logic_loop(
                logic_dispatcher,
                logic_lock,
                units_by_id,
                map_tracker,
                queue_command_for_unit,
                queue_move_for_unit,
            )
        )

        try:
            await command_loop(
                send_queue,
                units_by_id,
                map_tracker,
                command_counter,
                logic_dispatcher,
                logic_lock,
                queue_command_for_unit,
                queue_move_for_unit,
            )
        finally:
            call.cancel()
            receiver_task.cancel()
            auto_logic_task.cancel()

            try:
                await receiver_task
            except asyncio.CancelledError:
                pass

            try:
                await auto_logic_task
            except asyncio.CancelledError:
                pass

if __name__ == "__main__":
    asyncio.run(run())
