#!/usr/bin/env python3
"""Pure-stdlib keccak256, so on-chain identity checks need no dependencies.

Ethereum hashes with original Keccak (padding byte 0x01), not FIPS-202 SHA3
(padding byte 0x06), so hashlib.sha3_256 is the wrong function here.
"""

_ROUND_CONSTANTS = (
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
)
_ROTATION_OFFSETS = (
    (0, 36, 3, 41, 18),
    (1, 44, 10, 45, 2),
    (62, 6, 43, 15, 61),
    (28, 55, 25, 21, 56),
    (27, 20, 39, 8, 14),
)
_MASK = (1 << 64) - 1
_RATE = 136  # 1088 bits, the rate of keccak-256


def _rotl(value, shift):
    return ((value << shift) | (value >> (64 - shift))) & _MASK


def _permute(lanes):
    for round_index in range(24):
        # theta
        columns = [lanes[x][0] ^ lanes[x][1] ^ lanes[x][2] ^ lanes[x][3] ^ lanes[x][4]
                   for x in range(5)]
        for x in range(5):
            delta = columns[(x - 1) % 5] ^ _rotl(columns[(x + 1) % 5], 1)
            for y in range(5):
                lanes[x][y] ^= delta
        # rho and pi
        rotated = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                offset = _ROTATION_OFFSETS[x][y]
                value = lanes[x][y] if offset == 0 else _rotl(lanes[x][y], offset)
                rotated[y][(2 * x + 3 * y) % 5] = value
        # chi
        for y in range(5):
            row = [rotated[x][y] for x in range(5)]
            for x in range(5):
                lanes[x][y] = row[x] ^ ((~row[(x + 1) % 5] & _MASK) & row[(x + 2) % 5])
        # iota
        lanes[0][0] ^= _ROUND_CONSTANTS[round_index]
    return lanes


def keccak256(data):
    """Return the 32-byte Keccak-256 digest of bytes-like data."""
    if isinstance(data, str):
        data = data.encode('utf-8')
    data = bytes(data)
    padded = bytearray(data)
    padded.append(0x01)
    while len(padded) % _RATE != 0:
        padded.append(0x00)
    padded[-1] ^= 0x80
    lanes = [[0] * 5 for _ in range(5)]
    for start in range(0, len(padded), _RATE):
        block = padded[start:start + _RATE]
        for i in range(_RATE // 8):
            lane = int.from_bytes(block[i * 8:i * 8 + 8], 'little')
            lanes[i % 5][i // 5] ^= lane
        _permute(lanes)
    out = bytearray()
    for i in range(4):  # 32 bytes come from the first four lanes of the rate
        out += lanes[i % 5][i // 5].to_bytes(8, 'little')
    return bytes(out)


def keccak_hex(data):
    return '0x' + keccak256(data).hex()


def selector(signature):
    """Return the 4-byte function selector of a canonical signature, as 0x-hex."""
    canonical = ''.join(signature.split())
    if '(' not in canonical or not canonical.endswith(')'):
        raise ValueError('signature must look like name(type,type)')
    return '0x' + keccak256(canonical)[:4].hex()
