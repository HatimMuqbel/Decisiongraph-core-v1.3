"""
DecisionGraph Write-Ahead Log (WAL) Module

Append-only, crash-safe, hash-chained persistence for DecisionGraph cells.

WAL GUARANTEES:
1. Append-only: No rewrites, no reordering
2. Crash-safe: fsync after each record (configurable)
3. Replay-deterministic: fold([], records) = chain
4. Hash-chained: prev_hash[n] = SHA256(record[n-1])
5. Version-aware: Header locks hash_scheme for all records

FILE FORMAT:
    [WAL_HEADER: 68 bytes]
    [RECORD_0]
    [RECORD_1]
    ...
    [RECORD_N]

HEADER FORMAT (68 bytes):
    magic:        8 bytes   "DGWAL\x00\x01\x00"
    version:      2 bytes   uint16 LE
    hash_scheme: 32 bytes   UTF-8 padded
    graph_id:    20 bytes   UTF-8 padded
    flags:        2 bytes   reserved (0x0000)
    header_crc:   4 bytes   CRC32C of preceding 64 bytes

RECORD FORMAT (variable):
    record_len:      4 bytes   uint32 LE (total record size including this field)
    sequence:        8 bytes   uint64 LE (monotonic, 0-indexed)
    flags:           2 bytes   uint16 LE (reserved for future: compression, tombstone, etc.)
    prev_hash:      32 bytes   SHA-256 of previous record (raw bytes)
    cell_hash:      32 bytes   SHA-256 of canonical_bytes
    canonical_bytes: N bytes   RFC 8785 cell payload
    record_crc:      4 bytes   CRC32C of [record_len..canonical_bytes]

RECORD_HASH (for chain linking):
    SHA256(record_len || sequence || flags || prev_hash || cell_hash || canonical_bytes || record_crc)
"""

import hashlib
import os
import struct
from dataclasses import dataclass
from enum import IntFlag
from pathlib import Path
from typing import BinaryIO, Iterator, Optional, Tuple, Union

# Try to use hardware-accelerated CRC32C, fall back to zlib CRC32
try:
    import crc32c
    def compute_crc32c(data: bytes) -> int:
        return crc32c.crc32c(data)
    CRC_IMPL = "crc32c"
except ImportError:
    import zlib
    def compute_crc32c(data: bytes) -> int:
        # zlib.crc32 returns signed on some platforms, ensure unsigned
        return zlib.crc32(data) & 0xFFFFFFFF
    CRC_IMPL = "zlib"


# =============================================================================
# CONSTANTS
# =============================================================================

WAL_MAGIC = b"DGWAL\x00\x01\x00"  # 8 bytes
WAL_VERSION = 1
HEADER_SIZE = 68
MIN_RECORD_SIZE = 4 + 8 + 2 + 32 + 32 + 0 + 4  # record_len + seq + flags + prev + cell + 0 bytes + crc = 82
MAX_RECORD_SIZE = 64 * 1024 * 1024  # 64MB default max
NULL_HASH_BYTES = b'\x00' * 32


class RecordFlags(IntFlag):
    """Record flags for future extensibility."""
    NONE = 0x0000
    # Reserved for future:
    # COMPRESSED = 0x0001
    # TOMBSTONE = 0x0002
    # CHECKPOINT = 0x0004


class WALError(Exception):
    """Base WAL exception."""
    pass


class WALCorruptionError(WALError):
    """WAL file or record is corrupted."""
    pass


class WALHeaderError(WALError):
    """WAL header validation failed."""
    pass


class WALChainError(WALError):
    """Hash chain validation failed."""
    pass


class WALSequenceError(WALError):
    """Sequence number validation failed."""
    pass


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass(frozen=True)
class WALHeader:
    """WAL file header."""
    version: int
    hash_scheme: str
    graph_id: str
    flags: int
    header_crc: int

    @staticmethod
    def create(hash_scheme: str, graph_id: str) -> 'WALHeader':
        """Create a new WAL header."""
        # Truncate to fit in fixed fields
        scheme_truncated = hash_scheme[:32] if len(hash_scheme) > 32 else hash_scheme
        graph_truncated = graph_id[:20] if len(graph_id) > 20 else graph_id

        # Compute CRC of the first 64 bytes
        header_bytes = WALHeader._pack_without_crc(scheme_truncated, graph_truncated)
        crc = compute_crc32c(header_bytes)
        return WALHeader(
            version=WAL_VERSION,
            hash_scheme=scheme_truncated,
            graph_id=graph_truncated,
            flags=0,
            header_crc=crc,
        )

    @staticmethod
    def _pack_without_crc(hash_scheme: str, graph_id: str) -> bytes:
        """Pack header bytes without CRC (first 64 bytes)."""
        scheme_bytes = hash_scheme.encode('utf-8')[:32].ljust(32, b'\x00')
        graph_bytes = graph_id.encode('utf-8')[:20].ljust(20, b'\x00')
        return (
            WAL_MAGIC +                          # 8 bytes
            struct.pack('<H', WAL_VERSION) +     # 2 bytes
            scheme_bytes +                       # 32 bytes
            graph_bytes +                        # 20 bytes
            struct.pack('<H', 0)                 # 2 bytes flags
        )  # Total: 64 bytes

    def to_bytes(self) -> bytes:
        """Serialize header to bytes."""
        header_bytes = self._pack_without_crc(self.hash_scheme, self.graph_id)
        return header_bytes + struct.pack('<I', self.header_crc)  # 64 + 4 = 68 bytes

    @staticmethod
    def from_bytes(data: bytes) -> 'WALHeader':
        """Deserialize header from bytes."""
        if len(data) != HEADER_SIZE:
            raise WALHeaderError(f"Header size mismatch: expected {HEADER_SIZE}, got {len(data)}")

        magic = data[0:8]
        if magic != WAL_MAGIC:
            raise WALHeaderError(f"Invalid magic: {magic!r}")

        version = struct.unpack('<H', data[8:10])[0]
        if version != WAL_VERSION:
            raise WALHeaderError(f"Unsupported WAL version: {version}")

        # Verify CRC first (before attempting UTF-8 decode)
        header_crc = struct.unpack('<I', data[64:68])[0]
        computed_crc = compute_crc32c(data[0:64])
        if computed_crc != header_crc:
            raise WALHeaderError(
                f"Header CRC mismatch: stored={header_crc:08x}, computed={computed_crc:08x}"
            )

        # Now safe to decode strings (CRC validated)
        try:
            hash_scheme = data[10:42].rstrip(b'\x00').decode('utf-8')
            graph_id = data[42:62].rstrip(b'\x00').decode('utf-8')
        except UnicodeDecodeError as e:
            raise WALHeaderError(f"Header contains invalid UTF-8: {e}")

        flags = struct.unpack('<H', data[62:64])[0]

        return WALHeader(
            version=version,
            hash_scheme=hash_scheme,
            graph_id=graph_id,
            flags=flags,
            header_crc=header_crc,
        )


@dataclass(frozen=True)
class WALRecord:
    """A single WAL record."""
    sequence: int
    flags: RecordFlags
    prev_hash: bytes  # 32 bytes
    cell_hash: bytes  # 32 bytes
    canonical_bytes: bytes
    record_crc: int

    @property
    def record_len(self) -> int:
        """Total record size in bytes."""
        return 4 + 8 + 2 + 32 + 32 + len(self.canonical_bytes) + 4

    def to_bytes(self) -> bytes:
        """Serialize record to bytes."""
        record_len = self.record_len

        # Pack everything except CRC
        payload = (
            struct.pack('<I', record_len) +
            struct.pack('<Q', self.sequence) +
            struct.pack('<H', self.flags) +
            self.prev_hash +
            self.cell_hash +
            self.canonical_bytes
        )

        # Compute CRC of payload
        crc = compute_crc32c(payload)

        return payload + struct.pack('<I', crc)

    def compute_record_hash(self) -> bytes:
        """
        Compute the hash of this record for chain linking.

        record_hash = SHA256(record_len || sequence || flags || prev_hash ||
                            cell_hash || canonical_bytes || record_crc)
        """
        data = (
            struct.pack('<I', self.record_len) +
            struct.pack('<Q', self.sequence) +
            struct.pack('<H', self.flags) +
            self.prev_hash +
            self.cell_hash +
            self.canonical_bytes +
            struct.pack('<I', self.record_crc)
        )
        return hashlib.sha256(data).digest()

    @staticmethod
    def from_bytes(data: bytes, expected_sequence: Optional[int] = None) -> 'WALRecord':
        """
        Deserialize record from bytes.

        Validates:
        - Length consistency
        - CRC integrity
        - Sequence (if expected_sequence provided)
        """
        if len(data) < MIN_RECORD_SIZE:
            raise WALCorruptionError(f"Record too small: {len(data)} < {MIN_RECORD_SIZE}")

        record_len = struct.unpack('<I', data[0:4])[0]

        if record_len != len(data):
            raise WALCorruptionError(
                f"Record length mismatch: header says {record_len}, got {len(data)}"
            )

        if record_len > MAX_RECORD_SIZE:
            raise WALCorruptionError(
                f"Record too large: {record_len} > {MAX_RECORD_SIZE}"
            )

        sequence = struct.unpack('<Q', data[4:12])[0]
        flags = RecordFlags(struct.unpack('<H', data[12:14])[0])
        prev_hash = data[14:46]
        cell_hash = data[46:78]
        canonical_bytes = data[78:-4]
        stored_crc = struct.unpack('<I', data[-4:])[0]

        # Verify CRC
        computed_crc = compute_crc32c(data[:-4])
        if computed_crc != stored_crc:
            raise WALCorruptionError(
                f"Record CRC mismatch at seq {sequence}: "
                f"stored={stored_crc:08x}, computed={computed_crc:08x}"
            )

        # Verify sequence if expected
        if expected_sequence is not None and sequence != expected_sequence:
            raise WALSequenceError(
                f"Sequence mismatch: expected {expected_sequence}, got {sequence}"
            )

        # Verify cell_hash matches canonical_bytes
        computed_cell_hash = hashlib.sha256(canonical_bytes).digest()
        if computed_cell_hash != cell_hash:
            raise WALCorruptionError(
                f"Cell hash mismatch at seq {sequence}: "
                f"stored={cell_hash.hex()}, computed={computed_cell_hash.hex()}"
            )

        return WALRecord(
            sequence=sequence,
            flags=flags,
            prev_hash=prev_hash,
            cell_hash=cell_hash,
            canonical_bytes=canonical_bytes,
            record_crc=stored_crc,
        )

    @staticmethod
    def create(
        sequence: int,
        canonical_bytes: bytes,
        prev_hash: bytes,
        flags: RecordFlags = RecordFlags.NONE,
    ) -> 'WALRecord':
        """
        Create a new WAL record.

        Args:
            sequence: Monotonic sequence number (0-indexed)
            canonical_bytes: RFC 8785 canonical cell bytes
            prev_hash: Hash of previous record (NULL_HASH_BYTES for genesis)
            flags: Record flags

        Returns:
            WALRecord ready for serialization
        """
        cell_hash = hashlib.sha256(canonical_bytes).digest()

        # Build record to compute CRC
        record_len = 4 + 8 + 2 + 32 + 32 + len(canonical_bytes) + 4
        payload = (
            struct.pack('<I', record_len) +
            struct.pack('<Q', sequence) +
            struct.pack('<H', flags) +
            prev_hash +
            cell_hash +
            canonical_bytes
        )
        record_crc = compute_crc32c(payload)

        return WALRecord(
            sequence=sequence,
            flags=flags,
            prev_hash=prev_hash,
            cell_hash=cell_hash,
            canonical_bytes=canonical_bytes,
            record_crc=record_crc,
        )


# =============================================================================
# WAL WRITER
# =============================================================================

class WALWriter:
    """
    Append-only WAL writer with crash-safe guarantees.

    Usage:
        writer = WALWriter.create(path, hash_scheme, graph_id)
        record_hash = writer.append(canonical_bytes)
        writer.close()

    Or with context manager:
        with WALWriter.create(path, hash_scheme, graph_id) as writer:
            writer.append(canonical_bytes)
    """

    def __init__(
        self,
        file: BinaryIO,
        header: WALHeader,
        next_sequence: int,
        prev_hash: bytes,
        fsync_policy: str = "per_record",
    ):
        self._file = file
        self._header = header
        self._next_sequence = next_sequence
        self._prev_hash = prev_hash
        self._fsync_policy = fsync_policy
        self._closed = False

    @property
    def header(self) -> WALHeader:
        return self._header

    @property
    def next_sequence(self) -> int:
        return self._next_sequence

    @property
    def prev_hash(self) -> bytes:
        return self._prev_hash

    @staticmethod
    def create(
        path: Union[str, Path],
        hash_scheme: str,
        graph_id: str,
        fsync_policy: str = "per_record",
    ) -> 'WALWriter':
        """
        Create a new WAL file.

        Args:
            path: File path for WAL
            hash_scheme: Hash scheme (must match all cells)
            graph_id: Graph identifier
            fsync_policy: "per_record" (safe) or "manual" (fast, less safe)

        Returns:
            WALWriter instance

        Raises:
            FileExistsError: If file already exists
        """
        path = Path(path)
        if path.exists():
            raise FileExistsError(f"WAL file already exists: {path}")

        # Create parent directories
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create header
        header = WALHeader.create(hash_scheme, graph_id)

        # Open file and write header
        file = open(path, 'wb')
        try:
            file.write(header.to_bytes())
            file.flush()
            os.fsync(file.fileno())
        except:
            file.close()
            raise

        return WALWriter(
            file=file,
            header=header,
            next_sequence=0,
            prev_hash=NULL_HASH_BYTES,
            fsync_policy=fsync_policy,
        )

    @staticmethod
    def open(
        path: Union[str, Path],
        fsync_policy: str = "per_record",
    ) -> 'WALWriter':
        """
        Open an existing WAL file for appending.

        Scans to find last valid record, positions for append.

        Args:
            path: Path to existing WAL file
            fsync_policy: Sync policy

        Returns:
            WALWriter positioned at end
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"WAL file not found: {path}")

        # Read and validate header
        with open(path, 'rb') as f:
            header_bytes = f.read(HEADER_SIZE)
            if len(header_bytes) < HEADER_SIZE:
                raise WALHeaderError("WAL file too small for header")
            header = WALHeader.from_bytes(header_bytes)

        # Scan for last valid record
        last_sequence = -1
        last_hash = NULL_HASH_BYTES
        last_valid_offset = HEADER_SIZE

        for record, offset in WALReader._iter_records_raw(path, header):
            last_sequence = record.sequence
            last_hash = record.compute_record_hash()
            last_valid_offset = offset + record.record_len

        # Open for append at last valid position
        file = open(path, 'r+b')
        file.seek(last_valid_offset)
        file.truncate()  # Remove any partial record

        return WALWriter(
            file=file,
            header=header,
            next_sequence=last_sequence + 1,
            prev_hash=last_hash,
            fsync_policy=fsync_policy,
        )

    def append(self, canonical_bytes: bytes) -> Tuple[int, bytes, int]:
        """
        Append a cell to the WAL.

        Args:
            canonical_bytes: RFC 8785 canonical cell bytes

        Returns:
            Tuple of (sequence, record_hash, file_offset_end)

        Raises:
            WALError: If WAL is closed
            ValueError: If canonical_bytes is empty
        """
        if self._closed:
            raise WALError("WAL is closed")

        if not canonical_bytes:
            raise ValueError("canonical_bytes cannot be empty")

        # Create record
        record = WALRecord.create(
            sequence=self._next_sequence,
            canonical_bytes=canonical_bytes,
            prev_hash=self._prev_hash,
        )

        # Validate size
        if record.record_len > MAX_RECORD_SIZE:
            raise ValueError(f"Record too large: {record.record_len} > {MAX_RECORD_SIZE}")

        # Write atomically
        record_bytes = record.to_bytes()
        self._file.write(record_bytes)

        # Sync based on policy
        if self._fsync_policy == "per_record":
            self._file.flush()
            os.fsync(self._file.fileno())

        # Update state
        record_hash = record.compute_record_hash()
        offset_end = self._file.tell()
        self._prev_hash = record_hash
        self._next_sequence += 1

        return (record.sequence, record_hash, offset_end)

    def sync(self) -> None:
        """Force sync to disk."""
        if not self._closed:
            self._file.flush()
            os.fsync(self._file.fileno())

    def close(self) -> None:
        """Close the WAL file."""
        if not self._closed:
            self.sync()
            self._file.close()
            self._closed = True

    def __enter__(self) -> 'WALWriter':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# =============================================================================
# WAL READER
# =============================================================================

class WALReader:
    """
    WAL reader with chain validation.

    Usage:
        reader = WALReader(path)
        for record in reader:
            process(record.canonical_bytes)
    """

    def __init__(self, path: Union[str, Path]):
        self._path = Path(path)
        self._header: Optional[WALHeader] = None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def header(self) -> WALHeader:
        """Get WAL header (reads from file if not cached)."""
        if self._header is None:
            with open(self._path, 'rb') as f:
                header_bytes = f.read(HEADER_SIZE)
                if len(header_bytes) < HEADER_SIZE:
                    raise WALHeaderError("WAL file too small for header")
                self._header = WALHeader.from_bytes(header_bytes)
        return self._header

    @staticmethod
    def _iter_records_raw(
        path: Path,
        header: WALHeader,
        start_sequence: Optional[int] = 0,
    ) -> Iterator[Tuple[WALRecord, int]]:
        """
        Iterate records without chain validation.

        Yields (record, file_offset) tuples.
        Stops at first corrupted or incomplete record.

        Args:
            path: Path to WAL file
            header: WAL header (for validation)
            start_sequence: Expected starting sequence number.
                           If None, sequence validation is skipped.
                           If 0 (default), expects sequences starting from 0.
        """
        with open(path, 'rb') as f:
            f.seek(HEADER_SIZE)
            offset = HEADER_SIZE
            expected_sequence = start_sequence

            while True:
                # Try to read record length
                len_bytes = f.read(4)
                if len(len_bytes) == 0:
                    # Clean EOF
                    break
                if len(len_bytes) < 4:
                    # Incomplete length - truncation point
                    break

                record_len = struct.unpack('<I', len_bytes)[0]

                # Sanity checks
                if record_len < MIN_RECORD_SIZE or record_len > MAX_RECORD_SIZE:
                    # Corrupt length - truncation point
                    break

                # Read rest of record
                rest_bytes = f.read(record_len - 4)
                if len(rest_bytes) < record_len - 4:
                    # Incomplete record - truncation point
                    break

                record_bytes = len_bytes + rest_bytes

                try:
                    record = WALRecord.from_bytes(record_bytes, expected_sequence)
                    yield record, offset
                    offset += record_len
                    if expected_sequence is not None:
                        expected_sequence += 1
                except (WALCorruptionError, WALSequenceError):
                    # Corruption detected - truncation point
                    break

    def __iter__(self) -> Iterator[WALRecord]:
        """
        Iterate records with full chain validation.

        Validates:
        - CRC integrity
        - Sequence monotonicity
        - Hash chain continuity
        - Cell hash correctness
        """
        header = self.header
        prev_hash = NULL_HASH_BYTES

        for record, offset in self._iter_records_raw(self._path, header):
            # Validate hash chain
            if record.prev_hash != prev_hash:
                raise WALChainError(
                    f"Hash chain break at seq {record.sequence}: "
                    f"expected prev_hash={prev_hash.hex()}, got={record.prev_hash.hex()}"
                )

            yield record
            prev_hash = record.compute_record_hash()

    def validate(self) -> Tuple[int, bytes]:
        """
        Validate entire WAL and return final state.

        Returns:
            Tuple of (last_sequence, last_record_hash)
            Returns (-1, NULL_HASH_BYTES) if WAL is empty
        """
        last_sequence = -1
        last_hash = NULL_HASH_BYTES

        for record in self:
            last_sequence = record.sequence
            last_hash = record.compute_record_hash()

        return last_sequence, last_hash

    def count(self) -> int:
        """Count valid records."""
        return sum(1 for _ in self)


# =============================================================================
# WAL RECOVERY
# =============================================================================

def recover_wal(path: Union[str, Path]) -> Tuple[int, bytes, int]:
    """
    Recover a WAL file by truncating at last valid record.

    Scans the WAL, finds the last valid record, and truncates
    any partial/corrupt data after it.

    Args:
        path: Path to WAL file

    Returns:
        Tuple of (last_sequence, last_record_hash, truncated_bytes)
        last_sequence is -1 if no valid records

    Raises:
        WALHeaderError: If header is invalid
    """
    path = Path(path)

    # Read header first
    with open(path, 'rb') as f:
        header_bytes = f.read(HEADER_SIZE)
        if len(header_bytes) < HEADER_SIZE:
            raise WALHeaderError("WAL file too small for header")
        header = WALHeader.from_bytes(header_bytes)
        file_size = f.seek(0, 2)

    # Find last valid record
    last_sequence = -1
    last_hash = NULL_HASH_BYTES
    last_valid_offset = HEADER_SIZE

    # Use start_sequence=None to skip sequence validation
    # (segments may start at any sequence number)
    for record, offset in WALReader._iter_records_raw(path, header, start_sequence=None):
        last_sequence = record.sequence
        last_hash = record.compute_record_hash()
        last_valid_offset = offset + record.record_len

    # Truncate if needed
    truncated_bytes = file_size - last_valid_offset
    if truncated_bytes > 0:
        with open(path, 'r+b') as f:
            f.seek(last_valid_offset)
            f.truncate()
            f.flush()
            os.fsync(f.fileno())

    return last_sequence, last_hash, truncated_bytes


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Constants
    'WAL_MAGIC',
    'WAL_VERSION',
    'HEADER_SIZE',
    'MIN_RECORD_SIZE',
    'MAX_RECORD_SIZE',
    'NULL_HASH_BYTES',
    'CRC_IMPL',

    # Flags
    'RecordFlags',

    # Exceptions
    'WALError',
    'WALCorruptionError',
    'WALHeaderError',
    'WALChainError',
    'WALSequenceError',

    # Data structures
    'WALHeader',
    'WALRecord',

    # Core classes
    'WALWriter',
    'WALReader',

    # Recovery
    'recover_wal',
]
