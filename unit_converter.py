from decimal import Decimal
from typing import Union

# Conversion factors relative to Wei
ETH_UNITS = {
    'wei': Decimal('1'),
    'kwei': Decimal('1e3'),
    'mwei': Decimal('1e6'),
    'gwei': Decimal('1e9'),
    'szabo': Decimal('1e12'),
    'finney': Decimal('1e15'),
    'ether': Decimal('1e18'),
}

def convert_eth_unit(
    value: Union[int, float, str, Decimal],
    from_unit: str,
    to_unit: str
) -> Decimal:
    """
    Converts a value between different Ethereum units.

    Args:
        value: The numeric value to convert. Can be an int, float, str, or Decimal.
        from_unit: The starting unit (e.g., 'ether', 'gwei', 'wei').
        to_unit: The target unit (e.g., 'ether', 'gwei', 'wei').

    Returns:
        The converted value as a Decimal, preserving precision.

    Raises:
        ValueError: If an invalid unit name is provided.
    """
    from_unit_lower = from_unit.lower()
    to_unit_lower = to_unit.lower()

    if from_unit_lower not in ETH_UNITS:
        raise ValueError(f"Invalid 'from_unit': {from_unit}. Must be one of {list(ETH_UNITS.keys())}")
    if to_unit_lower not in ETH_UNITS:
        raise ValueError(f"Invalid 'to_unit': {to_unit}. Must be one of {list(ETH_UNITS.keys())}")

    # Use Decimal for precision, essential for financial calculations
    value_decimal = Decimal(str(value))

    # Convert the value to the base unit (Wei)
    value_in_wei = value_decimal * ETH_UNITS[from_unit_lower]

    # Convert from Wei to the target unit
    converted_value = value_in_wei / ETH_UNITS[to_unit_lower]

    return converted_value
