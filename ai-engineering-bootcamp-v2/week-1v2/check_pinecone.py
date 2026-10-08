#!/usr/bin/env python3
"""Read-only Pinecone connectivity check for the Session 2 index."""

import sys

from rag import (
    PineconeConfig,
    PineconeConfigurationError,
    PineconeConnectionError,
    PineconeIndexNotFoundError,
    check_pinecone_connectivity,
)

EXPECTED_DIMENSION = 1536
EXPECTED_METRIC = "cosine"


def main() -> int:
    try:
        config = PineconeConfig.from_env()
        result = check_pinecone_connectivity(config)
    except PineconeConfigurationError as exc:
        print(f"CONFIGURATION ERROR: {exc}")
        return 2
    except PineconeIndexNotFoundError as exc:
        print(f"INDEX ERROR: {exc}")
        return 3
    except PineconeConnectionError as exc:
        print(f"CONNECTION ERROR: {exc}")
        return 4

    print("PASS: Pinecone credentials are loaded (value hidden).")
    print(f"PASS: Index '{result.index_name}' is reachable.")
    print(f"Index dimension: {result.dimension}")
    print(f"Index metric: {result.metric}")
    print(f"Namespace: {result.namespace}")
    print(f"Total vectors: {result.total_vector_count}")
    print(f"Namespace vectors: {result.namespace_vector_count}")

    failed = False
    if result.dimension != EXPECTED_DIMENSION:
        print(
            f"FAIL: Expected {EXPECTED_DIMENSION} dimensions, "
            f"found {result.dimension}."
        )
        failed = True
    else:
        print(f"PASS: Index has {EXPECTED_DIMENSION} dimensions.")

    if result.metric != EXPECTED_METRIC:
        print(f"FAIL: Expected '{EXPECTED_METRIC}' metric, found '{result.metric}'.")
        failed = True
    else:
        print(f"PASS: Index uses {EXPECTED_METRIC} similarity.")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
