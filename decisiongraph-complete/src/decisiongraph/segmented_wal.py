"""
DecisionGraph Segmented WAL Module

Scalable append-only persistence with automatic segment rolling.

DESIGN PRINCIPLES:
1. Segment files are SOURCE OF TRUTH
2. Manifest is a CACHE (can be rebuilt from segments)
3. Immutable once sealed (only active segment is mutable)
4. Global monotonic sequence across segments
5. Hash chain crosses segment boundaries

DIRECTORY STRUCTURE:
    wal/
      00000000.wal    # segment 0
      00000001.wal    # segment 1
      manifest.json   # metadata cache

MANIFEST FORMAT:
    {
      "version": 1,
      "hash_scheme": "canon:rfc8785:v1",
      "graph_id": "graph:example",
      "segments": [
        {
          "id": 0,
          "first_seq": 0,
          "last_seq": 999,
          "first_hash": "abc...",
          "last_hash": "def...",
          "prev_hash_at_first": "000...000",
          "sealed": true
        },
        ...
      ],
      "active_segment": 2,
      "roll_policy": {"max_bytes": 268435456}
    }

RECOVERY:
    1. Scan segment files to rebuild state (manifest is just optimization)
    2. Truncate corruption in active segment only
    3. Sealed segments with corruption = fatal error (disk failure)
"""

import json
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from .wal import (
    HEADER_SIZE,
    NULL_HASH_BYTES,
    WALChainError,
    WALCorruptionError,
    WALError,
    WALHeader,
    WALHeaderError,
    WALReader,
    WALRecord,
    WALWriter,
    recover_wal,
)


# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_MAX_SEGMENT_BYTES = 256 * 1024 * 1024  # 256MB
MANIFEST_VERSION = 1
SEGMENT_NAME_FORMAT = "{:08d}.wal"


class SegmentedWALError(WALError):
    """Base exception for segmented WAL operations."""
    pass


class SegmentCorruptionError(SegmentedWALError):
    """Sealed segment is corrupted (serious - indicates disk failure)."""
    pass


class ManifestError(SegmentedWALError):
    """Manifest is invalid or corrupted."""
    pass


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class SegmentMetadata:
    """Metadata for a single WAL segment."""
    id: int
    first_seq: int
    last_seq: Optional[int]  # None if segment is empty or active
    first_hash: Optional[str]  # hex string, None if empty
    last_hash: Optional[str]  # hex string, None if empty/active
    prev_hash_at_first: Optional[str]  # hex string, the prev_hash of first record
    sealed: bool

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "first_seq": self.first_seq,
            "last_seq": self.last_seq,
            "first_hash": self.first_hash,
            "last_hash": self.last_hash,
            "prev_hash_at_first": self.prev_hash_at_first,
            "sealed": self.sealed,
        }

    @staticmethod
    def from_dict(data: Dict) -> 'SegmentMetadata':
        return SegmentMetadata(
            id=data["id"],
            first_seq=data["first_seq"],
            last_seq=data.get("last_seq"),
            first_hash=data.get("first_hash"),
            last_hash=data.get("last_hash"),
            prev_hash_at_first=data.get("prev_hash_at_first"),
            sealed=data.get("sealed", False),
        )


@dataclass
class Manifest:
    """Segmented WAL manifest (cache of segment metadata)."""
    version: int
    hash_scheme: str
    graph_id: str
    segments: List[SegmentMetadata]
    active_segment: int
    roll_policy: Dict

    def to_dict(self) -> Dict:
        return {
            "version": self.version,
            "hash_scheme": self.hash_scheme,
            "graph_id": self.graph_id,
            "segments": [s.to_dict() for s in self.segments],
            "active_segment": self.active_segment,
            "roll_policy": self.roll_policy,
        }

    @staticmethod
    def from_dict(data: Dict) -> 'Manifest':
        return Manifest(
            version=data["version"],
            hash_scheme=data["hash_scheme"],
            graph_id=data["graph_id"],
            segments=[SegmentMetadata.from_dict(s) for s in data.get("segments", [])],
            active_segment=data.get("active_segment", 0),
            roll_policy=data.get("roll_policy", {"max_bytes": DEFAULT_MAX_SEGMENT_BYTES}),
        )

    @staticmethod
    def create(hash_scheme: str, graph_id: str, max_bytes: int = DEFAULT_MAX_SEGMENT_BYTES) -> 'Manifest':
        """Create a new empty manifest."""
        return Manifest(
            version=MANIFEST_VERSION,
            hash_scheme=hash_scheme,
            graph_id=graph_id,
            segments=[],
            active_segment=0,
            roll_policy={"max_bytes": max_bytes},
        )


# =============================================================================
# SEGMENT SCANNING (TRUTH FROM FILES)
# =============================================================================

def segment_path(wal_dir: Path, segment_id: int) -> Path:
    """Get path for a segment file."""
    return wal_dir / SEGMENT_NAME_FORMAT.format(segment_id)


def list_segment_files(wal_dir: Path) -> List[Tuple[int, Path]]:
    """
    List all segment files in directory, sorted by ID.

    Returns list of (segment_id, path) tuples.
    """
    segments = []
    if not wal_dir.exists():
        return segments

    for f in wal_dir.iterdir():
        if f.suffix == '.wal' and f.stem.isdigit():
            segment_id = int(f.stem)
            segments.append((segment_id, f))

    return sorted(segments, key=lambda x: x[0])


def scan_segment(path: Path) -> Tuple[Optional[WALHeader], List[WALRecord]]:
    """
    Scan a segment file and return header + all valid records.

    Stops at first invalid record (for recovery).
    """
    if not path.exists():
        return None, []

    try:
        with open(path, 'rb') as f:
            header_bytes = f.read(HEADER_SIZE)
            if len(header_bytes) < HEADER_SIZE:
                return None, []
            header = WALHeader.from_bytes(header_bytes)
    except WALHeaderError:
        return None, []

    records = []
    # Use start_sequence=None to skip sequence validation (segments may start at any sequence)
    for record, _ in WALReader._iter_records_raw(path, header, start_sequence=None):
        records.append(record)

    return header, records


def scan_segment_boundaries(path: Path) -> Optional[SegmentMetadata]:
    """
    Scan a segment to extract boundary metadata.

    Only reads first and last records (efficient for large segments).
    Returns None if segment is invalid/empty.
    """
    if not path.exists():
        return None

    segment_id = int(path.stem)

    try:
        header, records = scan_segment(path)
        if header is None:
            return None
    except Exception:
        return None

    if not records:
        # Empty segment (header only)
        return SegmentMetadata(
            id=segment_id,
            first_seq=0,  # Will be determined by context
            last_seq=None,
            first_hash=None,
            last_hash=None,
            prev_hash_at_first=None,
            sealed=False,
        )

    first_record = records[0]
    last_record = records[-1]

    return SegmentMetadata(
        id=segment_id,
        first_seq=first_record.sequence,
        last_seq=last_record.sequence,
        first_hash=first_record.compute_record_hash().hex(),
        last_hash=last_record.compute_record_hash().hex(),
        prev_hash_at_first=first_record.prev_hash.hex(),
        sealed=False,  # Caller determines this
    )


def rebuild_manifest_from_segments(
    wal_dir: Path,
    max_bytes: int = DEFAULT_MAX_SEGMENT_BYTES,
) -> Manifest:
    """
    Rebuild manifest by scanning all segment files.

    This is the RECOVERY path when manifest is missing/corrupted.
    Segment files are source of truth.
    """
    segment_files = list_segment_files(wal_dir)

    if not segment_files:
        raise SegmentedWALError("No segment files found in WAL directory")

    # Read header from first segment to get hash_scheme and graph_id
    first_path = segment_files[0][1]
    try:
        with open(first_path, 'rb') as f:
            header = WALHeader.from_bytes(f.read(HEADER_SIZE))
    except WALHeaderError as e:
        raise SegmentedWALError(f"First segment has invalid header: {e}")

    segments: List[SegmentMetadata] = []
    expected_prev_hash = NULL_HASH_BYTES.hex()

    for i, (segment_id, path) in enumerate(segment_files):
        meta = scan_segment_boundaries(path)
        if meta is None:
            raise SegmentedWALError(f"Segment {segment_id} is invalid")

        # Validate chain continuity
        if meta.first_hash is not None:
            if meta.prev_hash_at_first != expected_prev_hash:
                raise WALChainError(
                    f"Segment {segment_id} chain break: "
                    f"expected prev_hash={expected_prev_hash[:16]}..., "
                    f"got={meta.prev_hash_at_first[:16] if meta.prev_hash_at_first else 'None'}..."
                )
            expected_prev_hash = meta.last_hash

        # All segments except last are sealed
        is_last = (i == len(segment_files) - 1)
        meta.sealed = not is_last

        segments.append(meta)

    active_segment = segment_files[-1][0] if segment_files else 0

    return Manifest(
        version=MANIFEST_VERSION,
        hash_scheme=header.hash_scheme,
        graph_id=header.graph_id,
        segments=segments,
        active_segment=active_segment,
        roll_policy={"max_bytes": max_bytes},
    )


# =============================================================================
# ATOMIC MANIFEST OPERATIONS
# =============================================================================

def manifest_path(wal_dir: Path) -> Path:
    """Get path to manifest file."""
    return wal_dir / "manifest.json"


def backup_manifest_path(wal_dir: Path) -> Path:
    """Get path to backup manifest file."""
    return wal_dir / "manifest.json.bak"


def write_manifest_atomic(wal_dir: Path, manifest: Manifest) -> None:
    """
    Write manifest atomically (crash-safe).

    Process:
    1. Write to manifest.json.tmp
    2. fsync tmp file
    3. Rename to manifest.json (atomic on POSIX)
    4. fsync directory
    """
    manifest_file = manifest_path(wal_dir)
    tmp_file = wal_dir / "manifest.json.tmp"
    backup_file = backup_manifest_path(wal_dir)

    # Write to tmp
    data = json.dumps(manifest.to_dict(), indent=2)
    with open(tmp_file, 'w') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())

    # Backup current manifest if exists
    if manifest_file.exists():
        if backup_file.exists():
            backup_file.unlink()
        manifest_file.rename(backup_file)

    # Atomic rename
    tmp_file.rename(manifest_file)

    # Fsync directory
    dir_fd = os.open(str(wal_dir), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def read_manifest(wal_dir: Path) -> Optional[Manifest]:
    """
    Read manifest from disk.

    Returns None if manifest doesn't exist or is corrupted.
    """
    manifest_file = manifest_path(wal_dir)
    if not manifest_file.exists():
        return None

    try:
        with open(manifest_file, 'r') as f:
            data = json.load(f)
        return Manifest.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


# =============================================================================
# SEGMENTED WAL WRITER
# =============================================================================

class SegmentedWALWriter:
    """
    Segmented WAL writer with automatic rolling.

    Usage:
        writer = SegmentedWALWriter.create(wal_dir, hash_scheme, graph_id)
        writer.append(canonical_bytes)
        writer.close()

    Or open existing:
        writer = SegmentedWALWriter.open(wal_dir)
        writer.append(canonical_bytes)
    """

    def __init__(
        self,
        wal_dir: Path,
        manifest: Manifest,
        active_writer: WALWriter,
        active_segment_size: int,
    ):
        self._wal_dir = wal_dir
        self._manifest = manifest
        self._active_writer = active_writer
        self._active_segment_size = active_segment_size
        self._closed = False

    @property
    def wal_dir(self) -> Path:
        return self._wal_dir

    @property
    def manifest(self) -> Manifest:
        return self._manifest

    @property
    def next_sequence(self) -> int:
        return self._active_writer.next_sequence

    @property
    def prev_hash(self) -> bytes:
        return self._active_writer.prev_hash

    @property
    def max_bytes(self) -> int:
        return self._manifest.roll_policy.get("max_bytes", DEFAULT_MAX_SEGMENT_BYTES)

    @staticmethod
    def create(
        wal_dir: Path,
        hash_scheme: str,
        graph_id: str,
        max_bytes: int = DEFAULT_MAX_SEGMENT_BYTES,
    ) -> 'SegmentedWALWriter':
        """
        Create a new segmented WAL.

        Args:
            wal_dir: Directory for WAL files
            hash_scheme: Hash scheme for all segments
            graph_id: Graph identifier
            max_bytes: Max segment size before rolling

        Returns:
            SegmentedWALWriter instance
        """
        wal_dir = Path(wal_dir)
        if wal_dir.exists() and any(wal_dir.iterdir()):
            raise FileExistsError(f"WAL directory not empty: {wal_dir}")

        wal_dir.mkdir(parents=True, exist_ok=True)

        # Create first segment
        seg_path = segment_path(wal_dir, 0)
        active_writer = WALWriter.create(seg_path, hash_scheme, graph_id)

        # Create manifest
        manifest = Manifest.create(hash_scheme, graph_id, max_bytes)
        manifest.segments.append(SegmentMetadata(
            id=0,
            first_seq=0,
            last_seq=None,
            first_hash=None,
            last_hash=None,
            prev_hash_at_first=NULL_HASH_BYTES.hex(),
            sealed=False,
        ))

        write_manifest_atomic(wal_dir, manifest)

        return SegmentedWALWriter(
            wal_dir=wal_dir,
            manifest=manifest,
            active_writer=active_writer,
            active_segment_size=HEADER_SIZE,
        )

    @staticmethod
    def open(wal_dir: Path) -> 'SegmentedWALWriter':
        """
        Open an existing segmented WAL for appending.

        Rebuilds manifest from segments if missing/corrupted.
        Recovers active segment if needed.
        """
        wal_dir = Path(wal_dir)
        if not wal_dir.exists():
            raise FileNotFoundError(f"WAL directory not found: {wal_dir}")

        # Try to load manifest, rebuild if needed
        manifest = read_manifest(wal_dir)

        # Always verify manifest against actual segment files
        # (handles crash where segment was created but manifest not updated)
        segment_files = list_segment_files(wal_dir)
        manifest_segment_ids = {seg.id for seg in manifest.segments} if manifest else set()
        actual_segment_ids = {seg_id for seg_id, _ in segment_files}

        if manifest is None or actual_segment_ids != manifest_segment_ids:
            # Manifest missing or out of sync with files - rebuild
            manifest = rebuild_manifest_from_segments(wal_dir)
            write_manifest_atomic(wal_dir, manifest)

        # Find active segment
        active_id = manifest.active_segment
        active_path = segment_path(wal_dir, active_id)

        if not active_path.exists():
            # Active segment missing - find the actual last segment
            segment_files = list_segment_files(wal_dir)
            if not segment_files:
                raise SegmentedWALError("No segment files found")
            active_id = segment_files[-1][0]
            active_path = segment_files[-1][1]
            manifest.active_segment = active_id

        # Recover active segment (truncate corruption)
        last_seq, last_hash, truncated = recover_wal(active_path)

        # Update manifest with recovered state
        active_meta = None
        for seg in manifest.segments:
            if seg.id == active_id:
                active_meta = seg
                break

        if active_meta is None:
            # Segment not in manifest - add it
            active_meta = scan_segment_boundaries(active_path)
            if active_meta:
                active_meta.sealed = False
                manifest.segments.append(active_meta)

        if active_meta and truncated > 0:
            # Update metadata after truncation
            updated = scan_segment_boundaries(active_path)
            if updated:
                active_meta.last_seq = updated.last_seq
                active_meta.last_hash = updated.last_hash

        write_manifest_atomic(wal_dir, manifest)

        # Determine correct state for active writer
        # Need to find last_seq and last_hash across all segments
        total_last_seq = -1
        total_last_hash = NULL_HASH_BYTES
        for seg in manifest.segments:
            if seg.last_seq is not None and seg.last_seq > total_last_seq:
                total_last_seq = seg.last_seq
                if seg.last_hash:
                    total_last_hash = bytes.fromhex(seg.last_hash)

        # Open active segment file for appending
        # Don't use WALWriter.open() as it validates sequence from 0
        with open(active_path, 'rb') as f:
            header = WALHeader.from_bytes(f.read(HEADER_SIZE))

        active_size = active_path.stat().st_size
        file = open(active_path, 'r+b')
        file.seek(active_size)  # Position at end for appending

        active_writer = WALWriter(
            file=file,
            header=header,
            next_sequence=total_last_seq + 1,
            prev_hash=total_last_hash,
            fsync_policy="per_record",
        )

        return SegmentedWALWriter(
            wal_dir=wal_dir,
            manifest=manifest,
            active_writer=active_writer,
            active_segment_size=active_size,
        )

    def append(self, canonical_bytes: bytes) -> Tuple[int, bytes, int]:
        """
        Append a cell to the WAL.

        Automatically rolls to new segment if size exceeds max_bytes.

        Args:
            canonical_bytes: RFC 8785 canonical cell bytes

        Returns:
            Tuple of (sequence, record_hash, segment_id)
        """
        if self._closed:
            raise SegmentedWALError("SegmentedWAL is closed")

        # Check if we need to roll BEFORE writing
        # (ensures each segment stays under max_bytes)
        estimated_record_size = 82 + len(canonical_bytes)  # MIN_RECORD_SIZE + payload
        if self._active_segment_size + estimated_record_size > self.max_bytes:
            self._roll_segment()

        # Write to active segment
        seq, record_hash, offset = self._active_writer.append(canonical_bytes)
        self._active_segment_size = offset

        # Update manifest metadata for active segment
        active_meta = self._manifest.segments[-1]
        if active_meta.first_hash is None:
            # First record in segment
            active_meta.first_seq = seq
            active_meta.first_hash = record_hash.hex()
            # prev_hash_at_first was set when segment was created
        active_meta.last_seq = seq
        active_meta.last_hash = record_hash.hex()

        return (seq, record_hash, self._manifest.active_segment)

    def _roll_segment(self) -> None:
        """
        Roll to a new segment.

        1. Seal current segment
        2. Update manifest
        3. Create new segment
        """
        # Get state from current segment
        prev_hash = self._active_writer.prev_hash
        next_seq = self._active_writer.next_sequence

        # Close current segment
        self._active_writer.close()

        # Mark current segment as sealed
        current_meta = self._manifest.segments[-1]
        current_meta.sealed = True

        # Create new segment
        new_segment_id = self._manifest.active_segment + 1
        new_path = segment_path(self._wal_dir, new_segment_id)

        # Create new segment with same hash_scheme and graph_id
        new_writer = WALWriter.create(
            new_path,
            self._manifest.hash_scheme,
            self._manifest.graph_id,
        )

        # Manually set the writer's state to continue the chain
        new_writer._next_sequence = next_seq
        new_writer._prev_hash = prev_hash

        # Update manifest
        self._manifest.active_segment = new_segment_id
        self._manifest.segments.append(SegmentMetadata(
            id=new_segment_id,
            first_seq=next_seq,
            last_seq=None,
            first_hash=None,
            last_hash=None,
            prev_hash_at_first=prev_hash.hex(),
            sealed=False,
        ))

        write_manifest_atomic(self._wal_dir, self._manifest)

        # Update internal state
        self._active_writer = new_writer
        self._active_segment_size = HEADER_SIZE

    def sync(self) -> None:
        """Force sync active segment and manifest."""
        if not self._closed:
            self._active_writer.sync()
            write_manifest_atomic(self._wal_dir, self._manifest)

    def close(self) -> None:
        """Close the segmented WAL."""
        if not self._closed:
            self._active_writer.close()
            write_manifest_atomic(self._wal_dir, self._manifest)
            self._closed = True

    def __enter__(self) -> 'SegmentedWALWriter':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# =============================================================================
# SEGMENTED WAL READER
# =============================================================================

class SegmentedWALReader:
    """
    Reader for segmented WAL.

    Iterates records across all segments in order.
    Validates cross-segment hash chain continuity.
    """

    def __init__(self, wal_dir: Path):
        self._wal_dir = Path(wal_dir)
        self._manifest: Optional[Manifest] = None

    @property
    def wal_dir(self) -> Path:
        return self._wal_dir

    @property
    def manifest(self) -> Manifest:
        """Get manifest (loads/rebuilds if needed)."""
        if self._manifest is None:
            self._manifest = read_manifest(self._wal_dir)
            if self._manifest is None:
                self._manifest = rebuild_manifest_from_segments(self._wal_dir)
        return self._manifest

    def __iter__(self) -> Iterator[WALRecord]:
        """
        Iterate all records across all segments.

        Validates:
        - Per-record CRC
        - Per-record cell_hash
        - Cross-segment hash chain continuity
        """
        segment_files = list_segment_files(self._wal_dir)
        if not segment_files:
            return

        prev_hash = NULL_HASH_BYTES

        for segment_id, path in segment_files:
            # Use raw iteration to avoid WALReader's internal chain validation
            # (which starts from NULL_HASH for each segment)
            try:
                with open(path, 'rb') as f:
                    header_bytes = f.read(HEADER_SIZE)
                    if len(header_bytes) < HEADER_SIZE:
                        continue
                    header = WALHeader.from_bytes(header_bytes)
            except WALHeaderError:
                continue

            # Use start_sequence=None to skip per-segment sequence validation
            # (sequence spans segments, so segment 1 might start at seq=100)
            for record, _ in WALReader._iter_records_raw(path, header, start_sequence=None):
                # Validate cross-segment chain
                if record.prev_hash != prev_hash:
                    raise WALChainError(
                        f"Hash chain break at seq {record.sequence} in segment {segment_id}: "
                        f"expected prev_hash={prev_hash.hex()[:16]}..., "
                        f"got={record.prev_hash.hex()[:16]}..."
                    )

                yield record
                prev_hash = record.compute_record_hash()

    def validate(self) -> Tuple[int, bytes]:
        """
        Validate entire segmented WAL.

        Returns:
            Tuple of (last_sequence, last_record_hash)
            Returns (-1, NULL_HASH_BYTES) if empty
        """
        last_seq = -1
        last_hash = NULL_HASH_BYTES

        for record in self:
            last_seq = record.sequence
            last_hash = record.compute_record_hash()

        return last_seq, last_hash

    def count(self) -> int:
        """Count total records across all segments."""
        return sum(1 for _ in self)

    def segment_count(self) -> int:
        """Count number of segments."""
        return len(list_segment_files(self._wal_dir))


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Constants
    'DEFAULT_MAX_SEGMENT_BYTES',
    'MANIFEST_VERSION',
    'SEGMENT_NAME_FORMAT',

    # Exceptions
    'SegmentedWALError',
    'SegmentCorruptionError',
    'ManifestError',

    # Data structures
    'SegmentMetadata',
    'Manifest',

    # Core classes
    'SegmentedWALWriter',
    'SegmentedWALReader',

    # Utilities
    'segment_path',
    'list_segment_files',
    'scan_segment',
    'scan_segment_boundaries',
    'rebuild_manifest_from_segments',
    'write_manifest_atomic',
    'read_manifest',
]
