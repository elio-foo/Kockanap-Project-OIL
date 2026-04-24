from Entity import Unit

def parse_to_unit(unit_data) -> Unit:
    return Unit().from_json(unit_data)


def parse_units(payload) -> list[Unit]:
    if payload is None:
        return []

    if isinstance(payload, list):
        return [parse_to_unit(unit_data) for unit_data in payload]

    if isinstance(payload, dict):
        if "Id" in payload:
            return [parse_to_unit(payload)]

        list_values = [value for value in payload.values() if isinstance(value, list)]
        if len(list_values) == 1:
            return [parse_to_unit(unit_data) for unit_data in list_values[0]]

    raise ValueError(f"Unsupported unit payload: {payload}")
