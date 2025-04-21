
from pymongo import ASCENDING, DESCENDING

def parse_filter_string(filter_string: str):
    OPERATORS = {
        ">=": "$gte",
        "<=": "$lte",
        "!=": "$ne",
        ">": "$gt",
        "<": "$lt",
        "=": "$eq",
        ":": "$eq"
    }

    filters = {}
    if not filter_string:
        return filters

    for part in filter_string.split(","):
        matched = False
        for symbol in sorted(OPERATORS.keys(), key=len, reverse=True):
            if symbol in part:
                field, value = part.split(symbol, 1)
                field = field.strip()
                value = value.strip()

                # Typ-Konvertierung
                lower_val = value.lower()
                if lower_val == "true":
                    value = True
                elif lower_val == "false":
                    value = False
                elif lower_val == "asc":
                    value = ASCENDING
                elif lower_val == "desc":
                    value = DESCENDING
                else:
                    try:
                        if "." in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        pass

                mongo_op = OPERATORS[symbol]

                if field in filters:
                    if isinstance(filters[field], dict):
                        filters[field][mongo_op] = value
                    else:
                        filters[field] = {
                            "$eq": filters[field],
                            mongo_op: value
                        }
                else:
                    if mongo_op == "$eq":
                        filters[field] = value
                    else:
                        filters[field] = {mongo_op: value}

                matched = True
                break

        if not matched:
            print(f"⚠️ Ungültiger Filterteil: {part}")

    return filters
