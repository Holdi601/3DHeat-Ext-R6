"""
The Match Replay file (`.rec`, "dissect"): one file a round.

    file     "dissect" and a header of strings, then zstd frames      (Y8S4 on)
             or the whole file one zstd stream holding both          (before)
    header   key/value strings, each `len:u8, 7 zero bytes, bytes`: the
             version, the map (`worldid`), the mode, the round number, the
             teams' names and scores, and per player of the recording's
             team `playerid`, `playername`, `team`, `rolename`...
    body     the frames decompressed and joined:
               a snapshot region (the players' blocks, the pawn table)
               then sections, each a 33-byte head (8-byte id, two u32, zeros)
               and blocks `tick:u32, size:u32, 0:u32, payload[size]`,
               ended by an empty block
             section 0 is the object stream: a block is a game tick,
             `count:u16` then packets `object:u32, aux:u32, size:u32, data`.
             Another section holds the game events (round clock, kill feed,
             defuser) in the tagged form `0x22, hash:u32, len:u8, value`.

The block and packet framing and the tick-tagged sections were worked out
here, from the files. The header strings and the event markers follow what
r6-dissect (github.com/redraskal/r6-dissect, MIT) documents; this is a new
implementation, no code of it is used.
"""

from __future__ import annotations

import bisect
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path

import zstandard

ZSTD = b"\x28\xb5\x2f\xfd"
MAGIC = b"dissect"
_STRING = re.compile(rb"(?s)([\x00-\xff])\x00{7}")


class RecError(ValueError):
    pass


@dataclass
class Block:
    section: int
    tick: int
    start: int  # payload start in the body
    end: int


@dataclass
class Section:
    index: int
    id: str
    a: int
    b: int
    start: int
    end: int
    blocks: int
    first_tick: int | None
    last_tick: int | None


@dataclass
class Rec:
    path: Path
    header: dict[str, str]
    header_players: list[dict[str, str]]
    gm_settings: list[str]
    body: bytes
    chunked: bool
    frames: int
    sections: list[Section] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)
    snapshot_end: int = 0
    _starts: list[int] = field(default_factory=list, repr=False)

    def code(self) -> int:
        try:
            return int(self.header.get("code", "0"))
        except ValueError:
            return 0

    def tick_at(self, offset: int) -> int | None:
        """The tick of the block holding a body offset; None in the snapshot region."""
        i = bisect.bisect_right(self._starts, offset) - 1
        if i < 0:
            return None
        b = self.blocks[i]
        return b.tick if offset < b.end else None

    def section_at(self, offset: int) -> int | None:
        i = bisect.bisect_right(self._starts, offset) - 1
        if i < 0 or offset >= self.blocks[i].end:
            return None
        return self.blocks[i].section


def _decompress_frames(data: bytes, start: int) -> tuple[bytes, int]:
    out = bytearray()
    d = zstandard.ZstdDecompressor()
    pos = data.find(ZSTD, start)
    n = 0
    while pos != -1:
        obj = d.decompressobj()
        try:
            out += obj.decompress(data[pos:])
        except zstandard.ZstdError:
            pos = data.find(ZSTD, pos + 4)
            continue
        n += 1
        used = len(data) - pos - len(obj.unused_data)
        pos = data.find(ZSTD, pos + max(used, 4))
    return bytes(out), n


def _strings(buf: bytes, start: int, stop: int) -> tuple[list[str], int]:
    """The header's strings from `start`, until one does not fit the layout."""
    out: list[str] = []
    p = start
    while p + 8 <= stop:
        if buf[p + 1 : p + 8] != b"\x00" * 7:
            break
        n = buf[p]
        s = buf[p + 8 : p + 8 + n]
        if len(s) < n:
            break
        out.append(s.decode("utf-8", "replace"))
        p += 8 + n
    return out, p


def _header(buf: bytes, limit: int) -> tuple[dict[str, str], list[dict[str, str]], list[str], int]:
    m = None
    for m in _STRING.finditer(buf, 0, min(limit, len(buf))):
        n = m.group(1)[0]
        if buf[m.end() : m.end() + n] in (b"playerid", b"version"):
            break
    else:
        raise RecError("no header strings")
    strings, end = _strings(buf, m.start(), limit)
    props: dict[str, str] = {}
    players: list[dict[str, str]] = []
    gm: list[str] = []
    cur: dict[str, str] | None = None
    player_keys = {"playerid", "profileid", "playername", "team", "heroname", "alliance", "roleimage", "rolename",
                   "roleportrait"}
    for k, v in zip(strings[0::2], strings[1::2]):
        if k == "playerid":
            cur = {}
            players.append(cur)
        elif k not in player_keys:
            cur = None
        if cur is not None and k in player_keys:
            cur[k] = v
        elif k == "gmsetting":
            gm.append(v)
        else:
            props[k] = v
    return props, players, gm, end


def _walk_sections(body: bytes, start: int) -> tuple[list[Section], list[Block]]:
    sections: list[Section] = []
    blocks: list[Block] = []
    p = start
    while p + 33 + 12 <= len(body):
        sid = body[p : p + 8].hex()
        a, b = struct.unpack_from("<II", body, p + 8)
        q = p + 33
        first = last = None
        n = 0
        while q + 12 <= len(body):
            tick, size, zero = struct.unpack_from("<III", body, q)
            if zero != 0 or q + 12 + size > len(body) or (last is not None and tick < last):
                break
            first = tick if first is None else first
            last = tick
            n += 1
            if size == 0:
                q += 12
                break
            blocks.append(Block(len(sections), tick, q + 12, q + 12 + size))
            q += 12 + size
        if n == 0:
            break
        sections.append(Section(len(sections), sid, a, b, p, q, n, first, last))
        p = q
    return sections, blocks


def _first_section(body: bytes) -> int:
    """The first section: a 33-byte head followed by blocks of the object stream (packets marked `?? 73 85 fe`)."""
    p = body.find(b"\x73\x85\xfe")
    while p != -1:
        # block head (12) + packet count (2) + packet head (12) + first data byte
        s = p - 1 - 12 - 2 - 12 - 33
        if s >= 0:
            secs, _ = _walk_sections(body[s : s + 4_000_000], 0)
            if secs and secs[0].blocks >= 3:
                return s
        p = body.find(b"\x73\x85\xfe", p + 3)
    raise RecError("no object stream found")


def read(path: str | Path) -> Rec:
    path = Path(path)
    data = path.read_bytes()
    if data[:7] == MAGIC:
        first = data.find(ZSTD)
        if first < 0:
            raise RecError("no compressed data")
        props, players, gm, _ = _header(data, first)
        body, frames = _decompress_frames(data, first)
        chunked = True
    elif data[:4] == ZSTD:
        body, frames = _decompress_frames(data, 0)
        if body[:7] != MAGIC:
            raise RecError("not a dissect replay")
        props, players, gm, end = _header(body, min(len(body), 2_000_000))
        body = body[end:]
        chunked = False
    else:
        raise RecError("not a dissect replay")
    rec = Rec(path, props, players, gm, body, chunked, frames)
    try:
        start = _first_section(body)
    except RecError:
        return rec  # events can still be read; positions not
    rec.snapshot_end = start
    rec.sections, rec.blocks = _walk_sections(body, start)
    rec._starts = [b.start for b in rec.blocks]
    return rec


def packets(rec: Rec, block: Block):
    """The packets of one object-stream block: (object, aux, data offset, size)."""
    b = rec.body
    if block.end - block.start < 2:
        return
    count = struct.unpack_from("<H", b, block.start)[0]
    q = block.start + 2
    for _ in range(count):
        if q + 12 > block.end:
            return
        obj, aux, size = struct.unpack_from("<III", b, q)
        if q + 12 + size > block.end:
            return
        yield obj, aux, q + 12, size
        q += 12 + size
