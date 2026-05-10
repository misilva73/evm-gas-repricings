def get_fusaka_dict():
    out_dict = {
        # opcodes
        "DIV": 5,
        "SDIV": 5,
        "MOD": 5,
        "SMOD": 5,
        "ADDMOD": 8,
        "MULMOD": 8,
        "KECCAK256": 30,
        "KECCAK256_WORD": 6,
        "SSTORE": 100,
        "SSTORE_NEW": 20_000 - 100,
        "SSTORE_UPDATE": 5_000 - 2_100 - 100,
        "SSTORE_COLD": 2_100,
        "SLOAD": 100,
        "SLOAD_COLD": 2_100 - 100,
        # Precompiles
        "ECRECOVER": 3_000,
        "ECADD": 150,
        "ECPAIRING": 45_000,
        "ECPAIRING_PAIRS": 34_000,
        "BLAKE2F": 0,
        "BLAKE2F_ROUNDS": 1,
        "POINT_EVALUATION": 50_000,
        "BLS12_G1ADD": 375,
        "BLS12_G2ADD": 600,
        "P256VERIFY":6_900,

    }
    # ToDo: add cost for SELFDESTRUCT
    for op in [
        "BALANCE",
        "DELEGATECALL",
        "STATICCALL",
        "CALL",
        "CALLCODE",
        "EXTCODESIZE",
        "EXTCODEHASH",
        "EXTCODECOPY",
    ]:
        out_dict[op] = 100
        out_dict[op + "_COLD"] = 2_500
    out_dict["EXTCODECOPY_SIZE"] = 3
    return out_dict
