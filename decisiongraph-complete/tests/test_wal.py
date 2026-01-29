"""
Tests for DecisionGraph WAL (Write-Ahead Log) Module

Tests cover:
1. Header validation
2. Record serialization/deserialization
3. Hash chain integrity
4. CRC validation
5. Crash recovery (partial writes, corruption)
6. Sequence monotonicity
7. Reader/Writer lifecycle
"""

import hashlib
import os
import struct
import tempfile
from pathlib import Path

import pytest

from decisiongraph.wal import (
    WAL_MAGIC,
    WAL_VERSION,
    HEADER_SIZE,
    MIN_RECORD_SIZE,
    MAX_RECORD_SIZE,
    NULL_HASH_BYTES,
    RecordFlags,
    WALError,
    WALCorruptionError,
    WALHeaderError,
    WALChainError,
    WALSequenceError,
    WALHeader,
    WALRecord,
    WALWriter,
    WALReader,
    recover_wal,
    compute_crc32c,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_wal_path(tmp_path):
    """Provide a temporary WAL file path."""
    return tmp_path / "test.wal"


@pytest.fixture
def sample_canonical_bytes():
    """Sample canonical cell bytes."""
    return b'{"header":{"version":"1.3"},"fact":{"namespace":"test"}}'


@pytest.fixture
def sample_canonical_bytes_list():
    """Multiple sample canonical cell bytes."""
    return [
        b'{"seq":0,"data":"genesis"}',
        b'{"seq":1,"data":"first"}',
        b'{"seq":2,"data":"second"}',
        b'{"seq":3,"data":"third"}',
    ]


# =============================================================================
# TEST: CONSTANTS
# =============================================================================

class TestConstants:
    """Test WAL constants are correct."""

    def test_magic_length(self):
        assert len(WAL_MAGIC) == 8

    def test_magic_format(self):
        assert WAL_MAGIC.startswith(b"DGWAL")

    def test_header_size(self):
        assert HEADER_SIZE == 68

    def test_min_record_size(self):
        # 4 + 8 + 2 + 32 + 32 + 0 + 4 = 82
        assert MIN_RECORD_SIZE == 82

    def test_null_hash_bytes(self):
        assert len(NULL_HASH_BYTES) == 32
        assert NULL_HASH_BYTES == b'\x00' * 32


# =============================================================================
# TEST: WAL HEADER
# =============================================================================

class TestWALHeader:
    """Test WAL header creation and validation."""

    def test_create_header(self):
        header = WALHeader.create("canon:rfc8785:v1", "graph:test-123")
        assert header.version == WAL_VERSION
        assert header.hash_scheme == "canon:rfc8785:v1"
        assert header.graph_id == "graph:test-123"
        assert header.flags == 0

    def test_header_to_bytes_size(self):
        header = WALHeader.create("canon:rfc8785:v1", "graph:test")
        data = header.to_bytes()
        assert len(data) == HEADER_SIZE

    def test_header_roundtrip(self):
        original = WALHeader.create("canon:rfc8785:v1", "graph:test-456")
        data = original.to_bytes()
        restored = WALHeader.from_bytes(data)

        assert restored.version == original.version
        assert restored.hash_scheme == original.hash_scheme
        assert restored.graph_id == original.graph_id
        assert restored.header_crc == original.header_crc

    def test_header_magic_validation(self):
        header = WALHeader.create("test", "graph")
        data = bytearray(header.to_bytes())
        data[0:8] = b"INVALID\x00"

        with pytest.raises(WALHeaderError) as exc_info:
            WALHeader.from_bytes(bytes(data))
        assert "magic" in str(exc_info.value).lower()

    def test_header_version_validation(self):
        header = WALHeader.create("test", "graph")
        data = bytearray(header.to_bytes())
        # Set version to 99
        struct.pack_into('<H', data, 8, 99)
        # Must also fix CRC
        data[64:68] = struct.pack('<I', compute_crc32c(bytes(data[0:64])))

        with pytest.raises(WALHeaderError) as exc_info:
            WALHeader.from_bytes(bytes(data))
        assert "version" in str(exc_info.value).lower()

    def test_header_crc_validation(self):
        header = WALHeader.create("test", "graph")
        data = bytearray(header.to_bytes())
        # Corrupt a byte in the middle
        data[20] ^= 0xFF

        with pytest.raises(WALHeaderError) as exc_info:
            WALHeader.from_bytes(bytes(data))
        assert "crc" in str(exc_info.value).lower()

    def test_header_truncated_hash_scheme(self):
        """Long hash_scheme is truncated to 32 bytes."""
        long_scheme = "a" * 100
        header = WALHeader.create(long_scheme, "graph")
        assert len(header.hash_scheme) <= 32

    def test_header_truncated_graph_id(self):
        """Long graph_id is truncated to 20 bytes."""
        long_id = "graph:" + "x" * 100
        header = WALHeader.create("test", long_id)
        assert len(header.graph_id) <= 20


# =============================================================================
# TEST: WAL RECORD
# =============================================================================

class TestWALRecord:
    """Test WAL record creation and validation."""

    def test_create_genesis_record(self):
        canonical = b'{"type":"genesis"}'
        record = WALRecord.create(
            sequence=0,
            canonical_bytes=canonical,
            prev_hash=NULL_HASH_BYTES,
        )

        assert record.sequence == 0
        assert record.prev_hash == NULL_HASH_BYTES
        assert record.canonical_bytes == canonical
        assert record.cell_hash == hashlib.sha256(canonical).digest()

    def test_record_size_calculation(self):
        canonical = b'{"test":"data"}'
        record = WALRecord.create(0, canonical, NULL_HASH_BYTES)

        expected_size = 4 + 8 + 2 + 32 + 32 + len(canonical) + 4
        assert record.record_len == expected_size

    def test_record_roundtrip(self):
        canonical = b'{"important":"data","value":42}'
        original = WALRecord.create(5, canonical, b'x' * 32)
        data = original.to_bytes()
        restored = WALRecord.from_bytes(data, expected_sequence=5)

        assert restored.sequence == original.sequence
        assert restored.prev_hash == original.prev_hash
        assert restored.cell_hash == original.cell_hash
        assert restored.canonical_bytes == original.canonical_bytes
        assert restored.record_crc == original.record_crc

    def test_record_crc_validation(self):
        canonical = b'{"test":"crc"}'
        record = WALRecord.create(0, canonical, NULL_HASH_BYTES)
        data = bytearray(record.to_bytes())
        # Corrupt a byte in canonical_bytes
        data[80] ^= 0xFF

        with pytest.raises(WALCorruptionError) as exc_info:
            WALRecord.from_bytes(bytes(data))
        assert "crc" in str(exc_info.value).lower()

    def test_record_sequence_validation(self):
        canonical = b'{"test":"seq"}'
        record = WALRecord.create(5, canonical, NULL_HASH_BYTES)
        data = record.to_bytes()

        with pytest.raises(WALSequenceError):
            WALRecord.from_bytes(data, expected_sequence=6)

    def test_record_cell_hash_validation(self):
        canonical = b'{"test":"hash"}'
        record = WALRecord.create(0, canonical, NULL_HASH_BYTES)
        data = bytearray(record.to_bytes())

        # Corrupt the cell_hash
        data[46:78] = b'x' * 32
        # Fix CRC so CRC check passes
        data[-4:] = struct.pack('<I', compute_crc32c(bytes(data[:-4])))

        with pytest.raises(WALCorruptionError) as exc_info:
            WALRecord.from_bytes(bytes(data))
        assert "cell hash" in str(exc_info.value).lower()

    def test_record_hash_determinism(self):
        canonical = b'{"determinism":"test"}'
        record1 = WALRecord.create(0, canonical, NULL_HASH_BYTES)
        record2 = WALRecord.create(0, canonical, NULL_HASH_BYTES)

        assert record1.compute_record_hash() == record2.compute_record_hash()

    def test_record_hash_changes_with_content(self):
        record1 = WALRecord.create(0, b'{"v":1}', NULL_HASH_BYTES)
        record2 = WALRecord.create(0, b'{"v":2}', NULL_HASH_BYTES)

        assert record1.compute_record_hash() != record2.compute_record_hash()

    def test_record_hash_changes_with_sequence(self):
        canonical = b'{"same":"content"}'
        record1 = WALRecord.create(0, canonical, NULL_HASH_BYTES)
        record2 = WALRecord.create(1, canonical, NULL_HASH_BYTES)

        assert record1.compute_record_hash() != record2.compute_record_hash()

    def test_record_hash_changes_with_prev_hash(self):
        canonical = b'{"same":"content"}'
        record1 = WALRecord.create(0, canonical, NULL_HASH_BYTES)
        record2 = WALRecord.create(0, canonical, b'x' * 32)

        assert record1.compute_record_hash() != record2.compute_record_hash()


# =============================================================================
# TEST: WAL WRITER
# =============================================================================

class TestWALWriter:
    """Test WAL writer functionality."""

    def test_create_new_wal(self, temp_wal_path):
        writer = WALWriter.create(temp_wal_path, "canon:rfc8785:v1", "graph:test")
        writer.close()

        assert temp_wal_path.exists()
        assert temp_wal_path.stat().st_size == HEADER_SIZE

    def test_create_writes_header(self, temp_wal_path):
        writer = WALWriter.create(temp_wal_path, "test-scheme", "my-graph")
        writer.close()

        with open(temp_wal_path, 'rb') as f:
            header = WALHeader.from_bytes(f.read(HEADER_SIZE))

        assert header.hash_scheme == "test-scheme"
        assert header.graph_id == "my-graph"

    def test_create_fails_if_exists(self, temp_wal_path):
        temp_wal_path.touch()

        with pytest.raises(FileExistsError):
            WALWriter.create(temp_wal_path, "test", "graph")

    def test_append_single_record(self, temp_wal_path, sample_canonical_bytes):
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            seq, record_hash, offset = writer.append(sample_canonical_bytes)

        assert seq == 0
        assert len(record_hash) == 32
        assert offset > HEADER_SIZE

    def test_append_multiple_records(self, temp_wal_path, sample_canonical_bytes_list):
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            results = []
            for data in sample_canonical_bytes_list:
                results.append(writer.append(data))

        # Verify sequence numbers
        sequences = [r[0] for r in results]
        assert sequences == [0, 1, 2, 3]

        # Verify offsets are increasing
        offsets = [r[2] for r in results]
        assert offsets == sorted(offsets)

    def test_append_updates_state(self, temp_wal_path, sample_canonical_bytes):
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            assert writer.next_sequence == 0
            assert writer.prev_hash == NULL_HASH_BYTES

            seq, record_hash, _ = writer.append(sample_canonical_bytes)

            assert writer.next_sequence == 1
            assert writer.prev_hash == record_hash

    def test_append_empty_bytes_fails(self, temp_wal_path):
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            with pytest.raises(ValueError):
                writer.append(b'')

    def test_context_manager(self, temp_wal_path, sample_canonical_bytes):
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            writer.append(sample_canonical_bytes)

        # File should be closed and synced
        assert temp_wal_path.stat().st_size > HEADER_SIZE

    def test_open_existing_wal(self, temp_wal_path, sample_canonical_bytes_list):
        # Write some records
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            for data in sample_canonical_bytes_list[:2]:
                writer.append(data)

        # Reopen and continue
        with WALWriter.open(temp_wal_path) as writer:
            assert writer.next_sequence == 2
            writer.append(sample_canonical_bytes_list[2])
            assert writer.next_sequence == 3

    def test_open_verifies_header(self, temp_wal_path):
        # Create valid WAL
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            pass

        # Corrupt header
        with open(temp_wal_path, 'r+b') as f:
            f.write(b"CORRUPT!")

        with pytest.raises(WALHeaderError):
            WALWriter.open(temp_wal_path)


# =============================================================================
# TEST: WAL READER
# =============================================================================

class TestWALReader:
    """Test WAL reader functionality."""

    def test_read_empty_wal(self, temp_wal_path):
        with WALWriter.create(temp_wal_path, "test", "graph"):
            pass

        reader = WALReader(temp_wal_path)
        records = list(reader)
        assert records == []

    def test_read_header(self, temp_wal_path):
        with WALWriter.create(temp_wal_path, "my-scheme", "my-graph"):
            pass

        reader = WALReader(temp_wal_path)
        assert reader.header.hash_scheme == "my-scheme"
        assert reader.header.graph_id == "my-graph"

    def test_read_single_record(self, temp_wal_path, sample_canonical_bytes):
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            writer.append(sample_canonical_bytes)

        reader = WALReader(temp_wal_path)
        records = list(reader)

        assert len(records) == 1
        assert records[0].sequence == 0
        assert records[0].canonical_bytes == sample_canonical_bytes

    def test_read_multiple_records(self, temp_wal_path, sample_canonical_bytes_list):
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            for data in sample_canonical_bytes_list:
                writer.append(data)

        reader = WALReader(temp_wal_path)
        records = list(reader)

        assert len(records) == 4
        for i, record in enumerate(records):
            assert record.sequence == i
            assert record.canonical_bytes == sample_canonical_bytes_list[i]

    def test_validate_returns_final_state(self, temp_wal_path, sample_canonical_bytes_list):
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            for data in sample_canonical_bytes_list:
                writer.append(data)

        reader = WALReader(temp_wal_path)
        last_seq, last_hash = reader.validate()

        assert last_seq == 3
        assert len(last_hash) == 32

    def test_count_records(self, temp_wal_path, sample_canonical_bytes_list):
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            for data in sample_canonical_bytes_list:
                writer.append(data)

        reader = WALReader(temp_wal_path)
        assert reader.count() == 4


# =============================================================================
# TEST: HASH CHAIN VALIDATION
# =============================================================================

class TestHashChain:
    """Test hash chain integrity validation."""

    def test_valid_chain(self, temp_wal_path, sample_canonical_bytes_list):
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            for data in sample_canonical_bytes_list:
                writer.append(data)

        reader = WALReader(temp_wal_path)
        # Should not raise
        list(reader)

    def test_chain_break_detected(self, temp_wal_path, sample_canonical_bytes_list):
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            for data in sample_canonical_bytes_list:
                writer.append(data)

        # Corrupt prev_hash of second record
        with open(temp_wal_path, 'r+b') as f:
            # Find second record (after header + first record)
            f.seek(HEADER_SIZE)
            len_bytes = f.read(4)
            first_record_len = struct.unpack('<I', len_bytes)[0]
            f.seek(HEADER_SIZE + first_record_len)

            # Read second record length
            len_bytes = f.read(4)
            # Skip sequence and flags
            f.seek(f.tell() + 8 + 2)
            # Write corrupted prev_hash
            f.write(b'x' * 32)

            # Need to also fix CRC
            f.seek(HEADER_SIZE + first_record_len)
            record_len = struct.unpack('<I', f.read(4))[0]
            f.seek(HEADER_SIZE + first_record_len)
            record_data = bytearray(f.read(record_len))
            new_crc = compute_crc32c(bytes(record_data[:-4]))
            record_data[-4:] = struct.pack('<I', new_crc)
            f.seek(HEADER_SIZE + first_record_len)
            f.write(record_data)

        reader = WALReader(temp_wal_path)
        with pytest.raises(WALChainError):
            list(reader)

    def test_genesis_must_have_null_prev_hash(self, temp_wal_path):
        """First record must have NULL_HASH_BYTES as prev_hash."""
        # Create a record with non-null prev_hash manually
        canonical = b'{"type":"genesis"}'
        bad_record = WALRecord.create(0, canonical, b'x' * 32)  # Wrong!

        # Write header + bad record
        header = WALHeader.create("test", "graph")
        with open(temp_wal_path, 'wb') as f:
            f.write(header.to_bytes())
            f.write(bad_record.to_bytes())

        reader = WALReader(temp_wal_path)
        with pytest.raises(WALChainError):
            list(reader)


# =============================================================================
# TEST: CRASH RECOVERY
# =============================================================================

class TestCrashRecovery:
    """Test crash recovery scenarios."""

    def test_recover_clean_wal(self, temp_wal_path, sample_canonical_bytes_list):
        """Recovery of clean WAL should be no-op."""
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            for data in sample_canonical_bytes_list:
                writer.append(data)

        original_size = temp_wal_path.stat().st_size
        last_seq, last_hash, truncated = recover_wal(temp_wal_path)

        assert last_seq == 3
        assert truncated == 0
        assert temp_wal_path.stat().st_size == original_size

    def test_recover_partial_length_write(self, temp_wal_path, sample_canonical_bytes_list):
        """Simulate crash during length write (partial 4 bytes)."""
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            for data in sample_canonical_bytes_list[:2]:
                writer.append(data)

        # Append partial length (2 bytes instead of 4)
        with open(temp_wal_path, 'ab') as f:
            f.write(b'\x50\x00')  # Partial record_len

        last_seq, last_hash, truncated = recover_wal(temp_wal_path)

        assert last_seq == 1
        assert truncated == 2

        # Verify WAL is readable again
        reader = WALReader(temp_wal_path)
        assert reader.count() == 2

    def test_recover_partial_record_write(self, temp_wal_path, sample_canonical_bytes_list):
        """Simulate crash during record body write."""
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            for data in sample_canonical_bytes_list[:2]:
                writer.append(data)

        # Append partial record (length + some bytes)
        with open(temp_wal_path, 'ab') as f:
            f.write(struct.pack('<I', 100))  # Claim 100 bytes
            f.write(b'x' * 50)  # But only write 50

        original_size = temp_wal_path.stat().st_size
        last_seq, last_hash, truncated = recover_wal(temp_wal_path)

        assert last_seq == 1
        assert truncated == 54  # 4 + 50

        # Verify WAL is readable
        reader = WALReader(temp_wal_path)
        assert reader.count() == 2

    def test_recover_corrupt_crc(self, temp_wal_path, sample_canonical_bytes_list):
        """Record with corrupt CRC should be truncated."""
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            for data in sample_canonical_bytes_list[:3]:
                writer.append(data)

        # Find and corrupt CRC of last record
        reader = WALReader(temp_wal_path)
        records = list(reader)
        last_record_start = HEADER_SIZE
        for r in records[:-1]:
            last_record_start += r.record_len

        with open(temp_wal_path, 'r+b') as f:
            f.seek(last_record_start)
            record_len = struct.unpack('<I', f.read(4))[0]
            # Corrupt last 4 bytes (CRC)
            f.seek(last_record_start + record_len - 4)
            f.write(b'\xff\xff\xff\xff')

        last_seq, last_hash, truncated = recover_wal(temp_wal_path)

        assert last_seq == 1  # Only first 2 records valid
        assert truncated > 0

    def test_recover_corrupt_sequence(self, temp_wal_path, sample_canonical_bytes_list):
        """Record with wrong sequence but valid CRC is accepted.

        Note: Since v2.0, sequence validation is skipped during recovery
        to support segmented WAL where segments start at different sequences.
        A record with wrong sequence but valid CRC/hash is not considered
        corrupt - it's a consistency issue that should be caught at a
        higher level (e.g., chain validation during read).
        """
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            for data in sample_canonical_bytes_list[:2]:
                writer.append(data)

        # Manually write a record with wrong sequence
        canonical = sample_canonical_bytes_list[2]
        # Get prev_hash from last valid record
        reader = WALReader(temp_wal_path)
        records = list(reader)
        prev_hash = records[-1].compute_record_hash()

        # Create record with sequence 5 instead of 2
        bad_record = WALRecord.create(5, canonical, prev_hash)

        with open(temp_wal_path, 'ab') as f:
            f.write(bad_record.to_bytes())

        last_seq, last_hash, truncated = recover_wal(temp_wal_path)

        # Record with wrong sequence but valid CRC is accepted
        assert last_seq == 5  # Record accepted (CRC valid)
        assert truncated == 0  # Nothing truncated

    def test_recover_empty_wal(self, temp_wal_path):
        """Recovery of empty WAL (header only)."""
        with WALWriter.create(temp_wal_path, "test", "graph"):
            pass

        last_seq, last_hash, truncated = recover_wal(temp_wal_path)

        assert last_seq == -1
        assert last_hash == NULL_HASH_BYTES
        assert truncated == 0

    def test_recover_and_continue(self, temp_wal_path, sample_canonical_bytes_list):
        """After recovery, should be able to continue appending."""
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            for data in sample_canonical_bytes_list[:2]:
                writer.append(data)

        # Add corruption
        with open(temp_wal_path, 'ab') as f:
            f.write(b'garbage data here')

        # Recover
        recover_wal(temp_wal_path)

        # Continue writing
        with WALWriter.open(temp_wal_path) as writer:
            assert writer.next_sequence == 2
            writer.append(sample_canonical_bytes_list[2])
            writer.append(sample_canonical_bytes_list[3])

        # Verify final state
        reader = WALReader(temp_wal_path)
        assert reader.count() == 4


# =============================================================================
# TEST: DETERMINISTIC REPLAY
# =============================================================================

class TestDeterministicReplay:
    """Test that WAL replay is deterministic."""

    def test_same_input_same_output(self, temp_wal_path, sample_canonical_bytes_list):
        """Writing same data produces same bytes."""
        def write_and_hash():
            path = temp_wal_path.parent / f"wal_{os.urandom(4).hex()}.wal"
            with WALWriter.create(path, "test", "graph") as writer:
                for data in sample_canonical_bytes_list:
                    writer.append(data)
            with open(path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()

        hash1 = write_and_hash()
        hash2 = write_and_hash()
        hash3 = write_and_hash()

        assert hash1 == hash2 == hash3

    def test_replay_produces_same_chain(self, temp_wal_path, sample_canonical_bytes_list):
        """Reading WAL produces consistent results."""
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            for data in sample_canonical_bytes_list:
                writer.append(data)

        # Read multiple times
        def get_hashes():
            reader = WALReader(temp_wal_path)
            return [r.compute_record_hash().hex() for r in reader]

        hashes1 = get_hashes()
        hashes2 = get_hashes()
        hashes3 = get_hashes()

        assert hashes1 == hashes2 == hashes3


# =============================================================================
# TEST: EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_minimum_size_record(self, temp_wal_path):
        """Record with 1-byte payload."""
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            writer.append(b'x')

        reader = WALReader(temp_wal_path)
        records = list(reader)
        assert len(records) == 1
        assert records[0].canonical_bytes == b'x'

    def test_large_record(self, temp_wal_path):
        """Record with 1MB payload."""
        large_data = b'x' * (1024 * 1024)

        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            writer.append(large_data)

        reader = WALReader(temp_wal_path)
        records = list(reader)
        assert len(records) == 1
        assert records[0].canonical_bytes == large_data

    def test_unicode_in_canonical_bytes(self, temp_wal_path):
        """Canonical bytes with UTF-8 content."""
        data = '{"emoji":"🎉","accents":"éàü"}'.encode('utf-8')

        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            writer.append(data)

        reader = WALReader(temp_wal_path)
        records = list(reader)
        assert records[0].canonical_bytes.decode('utf-8') == '{"emoji":"🎉","accents":"éàü"}'

    def test_many_records(self, temp_wal_path):
        """Write and read 1000 records."""
        with WALWriter.create(temp_wal_path, "test", "graph") as writer:
            for i in range(1000):
                writer.append(f'{{"seq":{i}}}'.encode())

        reader = WALReader(temp_wal_path)
        records = list(reader)
        assert len(records) == 1000

        # Verify sequence
        for i, r in enumerate(records):
            assert r.sequence == i

    def test_closed_writer_raises(self, temp_wal_path, sample_canonical_bytes):
        writer = WALWriter.create(temp_wal_path, "test", "graph")
        writer.close()

        with pytest.raises(WALError):
            writer.append(sample_canonical_bytes)


# =============================================================================
# TEST: FSYNC POLICY
# =============================================================================

class TestFsyncPolicy:
    """Test fsync policy options."""

    def test_per_record_policy(self, temp_wal_path, sample_canonical_bytes):
        """Per-record fsync is the default."""
        writer = WALWriter.create(temp_wal_path, "test", "graph")
        assert writer._fsync_policy == "per_record"
        writer.close()

    def test_manual_policy(self, temp_wal_path, sample_canonical_bytes):
        """Manual fsync policy allows batching."""
        with WALWriter.create(temp_wal_path, "test", "graph", fsync_policy="manual") as writer:
            writer.append(sample_canonical_bytes)
            writer.append(sample_canonical_bytes)
            writer.sync()  # Explicit sync

        reader = WALReader(temp_wal_path)
        assert reader.count() == 2
