from decimal import (
    Decimal,
)

import pytest

from eth_abi.codec import (
    ABIEncoder,
)
from eth_abi.encoding import (
    UnsignedIntegerEncoder,
)
from eth_abi.exceptions import (
    ValueOutOfBounds,
)
from eth_abi.grammar import (
    parse,
)
from eth_abi.packed import (
    encode_packed,
)
from eth_abi.registry import (
    registry_packed,
)
from tests.core.common.unit import (
    CORRECT_ENCODINGS,
    CORRECT_TUPLE_ENCODINGS,
)


@pytest.mark.parametrize(
    "single_abi_type,python_value,_,packed_encoding",
    CORRECT_TUPLE_ENCODINGS,
)
def test_encode_packed(single_abi_type, python_value, _, packed_encoding):
    abi_type = parse(single_abi_type)
    if abi_type.arrlist is not None:
        pytest.skip("ABI coding functions do not support array types")

    types = [t.to_type_str() for t in abi_type.components]

    actual = encode_packed(types, python_value)
    assert actual == packed_encoding


@pytest.mark.parametrize(
    "single_abi_type,python_value,_,packed_encoding",
    CORRECT_ENCODINGS,
)
def test_encode_packed_single_types(single_abi_type, python_value, _, packed_encoding):
    actual = encode_packed([single_abi_type], [python_value])
    assert actual == packed_encoding


@pytest.mark.parametrize("suffix", ["[]", "[2]"])
@pytest.mark.parametrize(
    "abi_type,values,expected",
    [
        ("uint8", [1, 255], (1).to_bytes(32, "big") + (255).to_bytes(32, "big")),
        ("int8", [-1, -128], b"\xff" * 32 + b"\xff" * 31 + b"\x80"),
        ("bool", [True, False], b"\x00" * 31 + b"\x01" + b"\x00" * 32),
        (
            "address",
            ["0x" + "12" * 20, "0x" + "34" * 20],
            b"\x00" * 12 + b"\x12" * 20 + b"\x00" * 12 + b"\x34" * 20,
        ),
        ("bytes2", [b"ab", b"c"], b"ab" + b"\x00" * 30 + b"c" + b"\x00" * 31),
        (
            "fixed16x1",
            [Decimal("-1.2"), Decimal("1.2")],
            (-12).to_bytes(32, "big", signed=True) + (12).to_bytes(32, "big"),
        ),
        (
            "ufixed16x1",
            [Decimal("0"), Decimal("1.2")],
            b"\x00" * 32 + (12).to_bytes(32, "big"),
        ),
    ],
)
def test_encode_packed_array_elements(abi_type, values, expected, suffix):
    assert encode_packed([abi_type + suffix], [values]) == expected


@pytest.mark.parametrize("array_type", ["int8[]", "int8[2]"])
def test_encode_packed_scalar_after_array(array_type):
    codec = ABIEncoder(registry_packed.copy())
    assert codec.encode([array_type], [[-1, -1]]) == b"\xff" * 64
    assert codec.encode(["int8"], [-1]) == b"\xff"


@pytest.mark.parametrize(
    "abi_type,value", [("uint8", 256), ("int8", 128), ("bytes2", b"abc")]
)
def test_encode_packed_array_element_validation(abi_type, value):
    with pytest.raises(ValueOutOfBounds):
        encode_packed([abi_type + "[]"], [[value]])


@pytest.mark.parametrize(
    "abi_type,value,expected",
    [
        ("uint8[][]", [[1], [2]], (1).to_bytes(32, "big") + (2).to_bytes(32, "big")),
        ("(int8[],uint8)", ([-1], 3), b"\xff" * 32 + b"\x03"),
        ("bytes[]", [b"ab", b"c"], b"abc"),
        ("string[]", ["a", "bc"], b"abc"),
    ],
)
def test_encode_packed_nested_and_dynamic_arrays(abi_type, value, expected):
    assert encode_packed([abi_type], [value]) == expected


def test_encode_packed_array_custom_encoder():
    registry = registry_packed.copy()
    registry.unregister_encoder("uint")

    def encode(value):
        return bytes([value + 1])

    encode.validate_value = lambda value: None
    registry.register_encoder("uint8", encode)
    assert ABIEncoder(registry).encode(["uint8[]"], [[1, 2]]) == b"\x02\x03"


def test_encode_packed_array_wide_custom_encoder():
    registry = registry_packed.copy()
    registry.register_encoder(
        "wide", UnsignedIntegerEncoder(value_bit_size=512, data_byte_size=64)
    )
    codec = ABIEncoder(registry)
    expected = (1).to_bytes(64, "big")
    assert codec.encode(["wide"], [1]) == expected
    assert codec.encode(["wide[]"], [[1]]) == expected
