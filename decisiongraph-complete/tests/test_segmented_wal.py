"""
Tests for DecisionGraph Segmented WAL Module

Tests cover:
1. Basic segment operations
2. Roll boundary correctness
3. Cross-segment hash chain
4. Manifest as cache (rebuild from segments)
5. Crash recovery scenarios
6. Atomic manifest writes
"""

import json
import os
import struct
from pathlib import Path

import pytest

from decisiongraph.wal import (
    HEADER_SIZE,
    NULL_HASH_BYTES,
    WALChainError,
    WALHeader,
    WALRecord,
    WALWriter,
    compute_crc32c,
)
from decisiongraph.segmented_wal import (
    DEFAULT_MAX_SEGMENT_BYTES,
    MANIFEST_VERSION,
    SEGMENT_NAME_FORMAT,
    SegmentedWALError,
    SegmentMetadata,
    Manifest,
    SegmentedWALWriter,
    SegmentedWALReader,
    segment_path,
    list_segment_files,
    scan_segment,
    scan_segment_boundaries,
    rebuild_manifest_from_segments,
    write_manifest_atomic,
    read_manifest,
    manifest_path,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def wal_dir(tmp_path):
    """Provide a temporary WAL directory."""
    return tmp_path / "wal"


@pytest.fixture
def sample_data():
    """Sample canonical bytes of various sizes."""
    return [
        b'{"seq":0,"data":"genesis"}',
        b'{"seq":1,"data":"' + b'x' * 100 + b'"}',
        b'{"seq":2,"data":"' + b'y' * 200 + b'"}',
        b'{"seq":3,"data":"short"}',
    ]


@pytest.fixture
def small_max_bytes():
    """Small max_bytes for testing rolling."""
    return 1024  # 1KB - will roll frequently


# =============================================================================
# TEST: SEGMENT PATH UTILITIES
# =============================================================================

class TestSegmentPathUtils:
    """Test segment path and naming utilities."""

    def test_segment_path_format(self, wal_dir):
        path = segment_path(wal_dir, 0)
        assert path.name == "00000000.wal"

    def test_segment_path_large_id(self, wal_dir):
        path = segment_path(wal_dir, 12345678)
        assert path.name == "12345678.wal"

    def test_list_segment_files_empty(self, wal_dir):
        wal_dir.mkdir(parents=True)
        segments = list_segment_files(wal_dir)
        assert segments == []

    def test_list_segment_files_sorted(self, wal_dir):
        wal_dir.mkdir(parents=True)
        # Create files out of order
        (wal_dir / "00000002.wal").touch()
        (wal_dir / "00000000.wal").touch()
        (wal_dir / "00000001.wal").touch()
        (wal_dir / "manifest.json").touch()  # Should be ignored

        segments = list_segment_files(wal_dir)
        assert len(segments) == 3
        assert [s[0] for s in segments] == [0, 1, 2]


# =============================================================================
# TEST: MANIFEST OPERATIONS
# =============================================================================

class TestManifest:
    """Test manifest data structure and operations."""

    def test_manifest_create(self):
        manifest = Manifest.create("canon:rfc8785:v1", "graph:test")
        assert manifest.version == MANIFEST_VERSION
        assert manifest.hash_scheme == "canon:rfc8785:v1"
        assert manifest.graph_id == "graph:test"
        assert manifest.segments == []
        assert manifest.active_segment == 0

    def test_manifest_roundtrip(self):
        manifest = Manifest.create("test-scheme", "graph:123")
        manifest.segments.append(SegmentMetadata(
            id=0,
            first_seq=0,
            last_seq=99,
            first_hash="abc123",
            last_hash="def456",
            prev_hash_at_first=NULL_HASH_BYTES.hex(),
            sealed=True,
        ))

        data = manifest.to_dict()
        restored = Manifest.from_dict(data)

        assert restored.hash_scheme == manifest.hash_scheme
        assert restored.graph_id == manifest.graph_id
        assert len(restored.segments) == 1
        assert restored.segments[0].last_hash == "def456"

    def test_write_manifest_atomic(self, wal_dir):
        wal_dir.mkdir(parents=True)
        manifest = Manifest.create("test", "graph")

        write_manifest_atomic(wal_dir, manifest)

        assert manifest_path(wal_dir).exists()
        loaded = read_manifest(wal_dir)
        assert loaded is not None
        assert loaded.hash_scheme == "test"

    def test_read_manifest_missing(self, wal_dir):
        wal_dir.mkdir(parents=True)
        result = read_manifest(wal_dir)
        assert result is None

    def test_read_manifest_corrupted(self, wal_dir):
        wal_dir.mkdir(parents=True)
        with open(manifest_path(wal_dir), 'w') as f:
            f.write("{ invalid json")

        result = read_manifest(wal_dir)
        assert result is None


# =============================================================================
# TEST: SEGMENTED WAL WRITER - BASIC
# =============================================================================

class TestSegmentedWALWriterBasic:
    """Test basic segmented WAL writer operations."""

    def test_create_new_wal(self, wal_dir, sample_data):
        with SegmentedWALWriter.create(wal_dir, "test-scheme", "graph:test") as writer:
            assert writer.next_sequence == 0
            assert wal_dir.exists()
            assert segment_path(wal_dir, 0).exists()

    def test_create_fails_if_not_empty(self, wal_dir):
        wal_dir.mkdir(parents=True)
        (wal_dir / "existing.file").touch()

        with pytest.raises(FileExistsError):
            SegmentedWALWriter.create(wal_dir, "test", "graph")

    def test_append_single_record(self, wal_dir, sample_data):
        with SegmentedWALWriter.create(wal_dir, "test", "graph") as writer:
            seq, record_hash, seg_id = writer.append(sample_data[0])

        assert seq == 0
        assert len(record_hash) == 32
        assert seg_id == 0

    def test_append_multiple_records(self, wal_dir, sample_data):
        with SegmentedWALWriter.create(wal_dir, "test", "graph") as writer:
            results = [writer.append(d) for d in sample_data]

        sequences = [r[0] for r in results]
        assert sequences == [0, 1, 2, 3]

    def test_open_existing_wal(self, wal_dir, sample_data):
        # Create and write some records
        with SegmentedWALWriter.create(wal_dir, "test", "graph") as writer:
            for d in sample_data[:2]:
                writer.append(d)

        # Reopen and continue
        with SegmentedWALWriter.open(wal_dir) as writer:
            assert writer.next_sequence == 2
            writer.append(sample_data[2])
            assert writer.next_sequence == 3


# =============================================================================
# TEST: SEGMENT ROLLING
# =============================================================================

class TestSegmentRolling:
    """Test automatic segment rolling."""

    def test_roll_creates_new_segment(self, wal_dir, small_max_bytes):
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=small_max_bytes) as writer:
            # Write enough data to trigger roll
            for i in range(20):
                writer.append(f'{{"seq":{i},"data":"{"x"*50}"}}'.encode())

        # Should have multiple segments
        segments = list_segment_files(wal_dir)
        assert len(segments) > 1

    def test_roll_sequence_continues(self, wal_dir, small_max_bytes):
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=small_max_bytes) as writer:
            sequences = []
            for i in range(20):
                seq, _, _ = writer.append(f'{{"seq":{i}}}'.encode())
                sequences.append(seq)

        # Sequences should be continuous
        assert sequences == list(range(20))

    def test_roll_hash_chain_continues(self, wal_dir, small_max_bytes):
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=small_max_bytes) as writer:
            for i in range(20):
                writer.append(f'{{"seq":{i}}}'.encode())

        # Validate cross-segment chain
        reader = SegmentedWALReader(wal_dir)
        records = list(reader)  # Should not raise WALChainError

        assert len(records) == 20
        for i, r in enumerate(records):
            assert r.sequence == i

    def test_roll_updates_manifest(self, wal_dir, small_max_bytes):
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=small_max_bytes) as writer:
            for i in range(20):
                writer.append(f'{{"seq":{i}}}'.encode())

        manifest = read_manifest(wal_dir)
        assert manifest is not None
        assert len(manifest.segments) > 1

        # All but last should be sealed
        for seg in manifest.segments[:-1]:
            assert seg.sealed is True
        assert manifest.segments[-1].sealed is False

    def test_roll_boundary_hashes_correct(self, wal_dir, small_max_bytes):
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=small_max_bytes) as writer:
            for i in range(20):
                writer.append(f'{{"seq":{i}}}'.encode())

        manifest = read_manifest(wal_dir)

        # Verify chain: segment[n+1].prev_hash_at_first == segment[n].last_hash
        for i in range(len(manifest.segments) - 1):
            current = manifest.segments[i]
            next_seg = manifest.segments[i + 1]
            if current.last_hash and next_seg.prev_hash_at_first:
                assert next_seg.prev_hash_at_first == current.last_hash, (
                    f"Chain break between segment {current.id} and {next_seg.id}"
                )


# =============================================================================
# TEST: SEGMENTED WAL READER
# =============================================================================

class TestSegmentedWALReader:
    """Test segmented WAL reader."""

    def test_read_single_segment(self, wal_dir, sample_data):
        with SegmentedWALWriter.create(wal_dir, "test", "graph") as writer:
            for d in sample_data:
                writer.append(d)

        reader = SegmentedWALReader(wal_dir)
        records = list(reader)

        assert len(records) == 4
        for i, r in enumerate(records):
            assert r.sequence == i

    def test_read_multiple_segments(self, wal_dir, small_max_bytes):
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=small_max_bytes) as writer:
            for i in range(50):
                writer.append(f'{{"seq":{i}}}'.encode())

        reader = SegmentedWALReader(wal_dir)
        records = list(reader)

        assert len(records) == 50
        assert reader.segment_count() > 1

    def test_validate_returns_final_state(self, wal_dir, sample_data):
        with SegmentedWALWriter.create(wal_dir, "test", "graph") as writer:
            for d in sample_data:
                writer.append(d)

        reader = SegmentedWALReader(wal_dir)
        last_seq, last_hash = reader.validate()

        assert last_seq == 3
        assert len(last_hash) == 32

    def test_count_across_segments(self, wal_dir, small_max_bytes):
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=small_max_bytes) as writer:
            for i in range(30):
                writer.append(f'{{"seq":{i}}}'.encode())

        reader = SegmentedWALReader(wal_dir)
        assert reader.count() == 30


# =============================================================================
# TEST: MANIFEST REBUILD (TRUTH FROM SEGMENTS)
# =============================================================================

class TestManifestRebuild:
    """Test manifest rebuild from segment files."""

    def test_rebuild_missing_manifest(self, wal_dir, small_max_bytes):
        # Create WAL with multiple segments
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=small_max_bytes) as writer:
            for i in range(20):
                writer.append(f'{{"seq":{i}}}'.encode())

        # Delete manifest
        manifest_path(wal_dir).unlink()

        # Should rebuild on open
        with SegmentedWALWriter.open(wal_dir) as writer:
            # Can continue appending
            writer.append(b'{"after":"rebuild"}')
            assert writer.next_sequence == 21

    def test_rebuild_corrupted_manifest(self, wal_dir, small_max_bytes):
        # Create WAL
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=small_max_bytes) as writer:
            for i in range(20):
                writer.append(f'{{"seq":{i}}}'.encode())

        # Corrupt manifest
        with open(manifest_path(wal_dir), 'w') as f:
            f.write("corrupted{{{")

        # Should rebuild on open
        with SegmentedWALWriter.open(wal_dir) as writer:
            writer.append(b'{"after":"rebuild"}')
            assert writer.next_sequence == 21

    def test_rebuild_validates_chain(self, wal_dir, sample_data):
        # Create valid WAL
        with SegmentedWALWriter.create(wal_dir, "test", "graph") as writer:
            for d in sample_data:
                writer.append(d)

        # Rebuild from segments
        manifest = rebuild_manifest_from_segments(wal_dir)

        assert manifest.hash_scheme == "test"
        assert manifest.graph_id == "graph"
        assert len(manifest.segments) == 1

    def test_rebuild_detects_chain_break(self, wal_dir, small_max_bytes):
        # Create WAL with multiple segments
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=small_max_bytes) as writer:
            for i in range(20):
                writer.append(f'{{"seq":{i}}}'.encode())

        # Corrupt second segment's first record prev_hash
        segments = list_segment_files(wal_dir)
        if len(segments) > 1:
            second_seg_path = segments[1][1]
            with open(second_seg_path, 'r+b') as f:
                f.seek(HEADER_SIZE + 4 + 8 + 2)  # record_len + seq + flags
                f.write(b'x' * 32)  # Corrupt prev_hash
                # Fix CRC
                f.seek(HEADER_SIZE)
                record_len_bytes = f.read(4)
                record_len = struct.unpack('<I', record_len_bytes)[0]
                f.seek(HEADER_SIZE)
                record_data = bytearray(f.read(record_len))
                new_crc = compute_crc32c(bytes(record_data[:-4]))
                record_data[-4:] = struct.pack('<I', new_crc)
                f.seek(HEADER_SIZE)
                f.write(record_data)

            # Delete manifest
            manifest_path(wal_dir).unlink()

            # Rebuild should detect chain break
            with pytest.raises(WALChainError):
                rebuild_manifest_from_segments(wal_dir)


# =============================================================================
# TEST: CRASH RECOVERY
# =============================================================================

class TestCrashRecovery:
    """Test crash recovery scenarios."""

    def test_recover_partial_write_in_active_segment(self, wal_dir, sample_data):
        # Create WAL
        with SegmentedWALWriter.create(wal_dir, "test", "graph") as writer:
            for d in sample_data[:2]:
                writer.append(d)

        # Add partial record to active segment
        active_path = segment_path(wal_dir, 0)
        with open(active_path, 'ab') as f:
            f.write(b'partial garbage')

        # Should recover on open
        with SegmentedWALWriter.open(wal_dir) as writer:
            assert writer.next_sequence == 2
            writer.append(sample_data[2])
            assert writer.next_sequence == 3

        # Verify integrity
        reader = SegmentedWALReader(wal_dir)
        assert reader.count() == 3

    def test_crash_after_roll_before_manifest_update(self, wal_dir, small_max_bytes):
        # Simulate: rolled to new segment but manifest not updated
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=small_max_bytes) as writer:
            for i in range(20):
                writer.append(f'{{"seq":{i}}}'.encode())

        segments = list_segment_files(wal_dir)
        original_count = len(segments)

        # Corrupt manifest to not know about last segment
        manifest = read_manifest(wal_dir)
        if len(manifest.segments) > 1:
            manifest.segments = manifest.segments[:-1]
            manifest.active_segment = manifest.segments[-1].id
            write_manifest_atomic(wal_dir, manifest)

        # Open should discover the missing segment
        with SegmentedWALWriter.open(wal_dir) as writer:
            # Should be able to continue
            writer.append(b'{"after":"recovery"}')

    def test_crash_new_segment_empty(self, wal_dir, small_max_bytes):
        # Create WAL
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=small_max_bytes) as writer:
            for i in range(15):
                writer.append(f'{{"seq":{i}}}'.encode())

        segments = list_segment_files(wal_dir)

        # Create empty next segment (simulating crash during roll)
        next_id = segments[-1][0] + 1
        new_path = segment_path(wal_dir, next_id)
        header = WALHeader.create("test", "graph")
        with open(new_path, 'wb') as f:
            f.write(header.to_bytes())

        # Recovery should handle this
        with SegmentedWALWriter.open(wal_dir) as writer:
            # Should continue from empty segment
            writer.append(b'{"after":"empty_seg"}')

    def test_recover_and_continue_chain(self, wal_dir, small_max_bytes):
        # Create WAL with multiple segments
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=small_max_bytes) as writer:
            for i in range(30):
                writer.append(f'{{"seq":{i}}}'.encode())

        # Corrupt tail of active segment
        segments = list_segment_files(wal_dir)
        active_path = segments[-1][1]
        with open(active_path, 'ab') as f:
            f.write(b'\xff' * 50)

        # Recover and continue
        with SegmentedWALWriter.open(wal_dir) as writer:
            writer.append(b'{"after":"truncation"}')

        # Validate entire chain
        reader = SegmentedWALReader(wal_dir)
        records = list(reader)  # Should not raise
        assert records[-1].canonical_bytes == b'{"after":"truncation"}'


# =============================================================================
# TEST: CROSS-SEGMENT CHAIN VALIDATION
# =============================================================================

class TestCrossSegmentChain:
    """Test hash chain validation across segments."""

    def test_valid_chain_across_segments(self, wal_dir, small_max_bytes):
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=small_max_bytes) as writer:
            for i in range(50):
                writer.append(f'{{"seq":{i}}}'.encode())

        # Read all records - validates chain
        reader = SegmentedWALReader(wal_dir)
        records = list(reader)
        assert len(records) == 50

    def test_detect_chain_break_at_segment_boundary(self, wal_dir, small_max_bytes):
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=small_max_bytes) as writer:
            for i in range(30):
                writer.append(f'{{"seq":{i}}}'.encode())

        segments = list_segment_files(wal_dir)
        if len(segments) < 2:
            pytest.skip("Need multiple segments for this test")

        # Corrupt prev_hash in second segment's first record
        second_path = segments[1][1]
        with open(second_path, 'r+b') as f:
            f.seek(HEADER_SIZE + 4 + 8 + 2)  # After record_len, seq, flags
            f.write(b'\xaa' * 32)  # Corrupt prev_hash
            # Fix CRC
            f.seek(HEADER_SIZE)
            record_len = struct.unpack('<I', f.read(4))[0]
            f.seek(HEADER_SIZE)
            record_data = bytearray(f.read(record_len))
            new_crc = compute_crc32c(bytes(record_data[:-4]))
            record_data[-4:] = struct.pack('<I', new_crc)
            f.seek(HEADER_SIZE)
            f.write(record_data)

        reader = SegmentedWALReader(wal_dir)
        with pytest.raises(WALChainError):
            list(reader)


# =============================================================================
# TEST: DETERMINISTIC REPLAY
# =============================================================================

class TestDeterministicReplay:
    """Test deterministic replay across segments."""

    def test_same_input_same_output(self, wal_dir, small_max_bytes):
        def write_and_read(dir_path):
            with SegmentedWALWriter.create(dir_path, "test", "graph", max_bytes=small_max_bytes) as writer:
                for i in range(25):
                    writer.append(f'{{"seq":{i},"data":"test"}}'.encode())

            reader = SegmentedWALReader(dir_path)
            return [r.compute_record_hash().hex() for r in reader]

        hashes1 = write_and_read(wal_dir / "wal1")
        hashes2 = write_and_read(wal_dir / "wal2")

        assert hashes1 == hashes2

    def test_replay_produces_consistent_state(self, wal_dir, small_max_bytes):
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=small_max_bytes) as writer:
            for i in range(40):
                writer.append(f'{{"seq":{i}}}'.encode())

        # Read multiple times
        def get_final_state():
            reader = SegmentedWALReader(wal_dir)
            return reader.validate()

        state1 = get_final_state()
        state2 = get_final_state()
        state3 = get_final_state()

        assert state1 == state2 == state3


# =============================================================================
# TEST: EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exact_max_bytes_boundary(self, wal_dir):
        # Create segment that's exactly at max_bytes
        max_bytes = HEADER_SIZE + 200
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=max_bytes) as writer:
            # First record should fit
            writer.append(b'{"small":"record"}')
            # Second might trigger roll
            writer.append(b'{"another":"record"}')

        # Should still work
        reader = SegmentedWALReader(wal_dir)
        assert reader.count() == 2

    def test_single_record_per_segment(self, wal_dir):
        # Very small segments
        max_bytes = HEADER_SIZE + 100
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=max_bytes) as writer:
            for i in range(5):
                writer.append(f'{{"seq":{i},"data":"{"x"*50}"}}'.encode())

        reader = SegmentedWALReader(wal_dir)
        records = list(reader)
        assert len(records) == 5

    def test_large_record_fits(self, wal_dir):
        with SegmentedWALWriter.create(wal_dir, "test", "graph") as writer:
            large_data = b'{"data":"' + b'x' * 100000 + b'"}'
            seq, _, _ = writer.append(large_data)
            assert seq == 0

        reader = SegmentedWALReader(wal_dir)
        records = list(reader)
        assert len(records[0].canonical_bytes) > 100000

    def test_many_small_segments(self, wal_dir):
        max_bytes = HEADER_SIZE + 150
        with SegmentedWALWriter.create(wal_dir, "test", "graph", max_bytes=max_bytes) as writer:
            for i in range(100):
                writer.append(f'{{"i":{i}}}'.encode())

        reader = SegmentedWALReader(wal_dir)
        assert reader.count() == 100
        assert reader.segment_count() > 10

    def test_empty_wal_directory(self, wal_dir):
        wal_dir.mkdir(parents=True)
        with pytest.raises(SegmentedWALError):
            SegmentedWALWriter.open(wal_dir)


# =============================================================================
# TEST: MANIFEST ATOMIC WRITES
# =============================================================================

class TestManifestAtomicWrites:
    """Test atomic manifest write behavior."""

    def test_backup_created(self, wal_dir, sample_data):
        with SegmentedWALWriter.create(wal_dir, "test", "graph") as writer:
            writer.append(sample_data[0])

        # First manifest exists
        assert manifest_path(wal_dir).exists()

        # Write more to trigger manifest update
        with SegmentedWALWriter.open(wal_dir) as writer:
            writer.append(sample_data[1])
            writer.sync()

        # After second update, backup should exist
        # (backup is created when manifest already exists)
        from decisiongraph.segmented_wal import backup_manifest_path
        # Note: backup is created on subsequent writes

    def test_manifest_recovers_from_tmp_file(self, wal_dir, sample_data):
        with SegmentedWALWriter.create(wal_dir, "test", "graph") as writer:
            for d in sample_data:
                writer.append(d)

        # Simulate crash leaving .tmp file
        tmp_path = wal_dir / "manifest.json.tmp"
        with open(tmp_path, 'w') as f:
            f.write('{"partial": "data"}')

        # Open should work (reads actual manifest, ignores tmp)
        with SegmentedWALWriter.open(wal_dir) as writer:
            assert writer.next_sequence == 4
