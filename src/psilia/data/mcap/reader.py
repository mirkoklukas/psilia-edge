from __future__ import annotations

from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Any, Callable
from itertools import islice

import numpy as np
from mcap.reader import make_reader  # type: ignore
from mcap_ros2.reader import McapROS2Message, read_ros2_messages
from pandas import DataFrame

from psilia.data.mcap.nested_dict import extract
from psilia.data.mcap.parsers import base_message_parser, parse_msg


def stack_dicts(dicts: list[dict]) -> dict:
    """Convert a list of dicts to a dict of lists."""
    if not dicts:
        return {}
    keys = dicts[0].keys()
    return {k: [d[k] for d in dicts] for k in keys}


def unstack_dicts(d: dict) -> list[dict]:
    """Convert a dict of lists to a list of dicts."""
    if not d:
        return []
    keys = list(d.keys())
    n = len(d[keys[0]])
    return [{k: d[k][i] for k in keys} for i in range(n)]


def get_summary(mcap: Path | str):
    with open(mcap, "rb") as f:
        return make_reader(f).get_summary()


def get_channel_overview(
    mcap: Path | str, *, filter_by_schema: str | list[str] | None = None, **kwargs: Any
) -> DataFrame:
    """Gets overview of the channels (topics and schemas) in a MCAP file."""
    mcap = Path(mcap)

    if filter_by_schema is not None:
        if isinstance(filter_by_schema, str):
            filter_by_schema = [filter_by_schema]

    summary = get_summary(mcap)
    channels = summary.channels
    schemas = summary.schemas
    counts = summary.statistics.channel_message_counts

    data = []
    for c in channels.values():
        if filter_by_schema is not None:
            if schemas[c.schema_id].name not in filter_by_schema:
                continue
        data.append(
            {
                "topic": c.topic,
                "schema": schemas[c.schema_id].name,
                "count": counts[c.id],
                "channel_id": c.id,
                "schema_id": c.schema_id,
                # "mcap": str(mcap),
            }
        )

    df = DataFrame(data=data).sort_values("topic")
    t0 = summary.statistics.message_start_time * 1e-9
    t1 = summary.statistics.message_end_time * 1e-9

    ts = get_summary(mcap).statistics.message_start_time * 1e-9
    timestamp = datetime.fromtimestamp(ts)

    df.attrs = {
        "mcap": str(mcap),
        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "duration": t1 - t0,
        "start_time": t0,
        "end_time": t1,
    }
    return df


def list_mcaps(path: Path | str):
    """Returns a DataFrame of MCAP files in a directory."""
    path = Path(path).expanduser()
    mcaps = glob(str(path / "**/*.mcap"), recursive=True)
    data = [{"name": Path(fname).name, "path": Path(fname)} for fname in mcaps]
    df = DataFrame(data=data)
    df.attrs = {
        "dir": str(path),
    }
    return df


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Internal: read and parse messages
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def read_nth_message(
    mcap: Path | str,
    topic: str,
    n: int = 0,
    # Enables to feed a dictionary with additional unused keys
    **kwargs: Any,
) -> McapROS2Message:
    """
    Reads the nth message from a MCAP file.

    Args:
        mcap: Path to the MCAP file.
        topic: Topic to read the message from.
        n: Index of the message to read.
    """
    it = read_ros2_messages(mcap, topics=[topic], log_time_order=False)
    return next(islice(it, n, None))


# NOTE: Do remapping of topics before and after the call,
#   for schema_transforms before and for the returned dict afterwards.
#
#   Limits are the limits for the actual topics, indices and keys are
#   for remapped topics and subkeys. Topics are those that the keys refer to, where
#   the keys refer to the re-mapped topics.
#
#   `limits = Limits(default_limit, inds, keys, topic_map, [topics])`
#   `topics` = Topics(keys, topic_map, [topics])`
#
#   _read_and_parse(mcap, TIME, PARSER, TOPICS, LIMITS, TRANSFORMS)
def _read_and_parse_messages(  # noqa: PLR0912
    mcap: str | Path,
    t_start: float,
    t_end: float,
    *,
    msg_parser: Callable = parse_msg,
    limits: dict[str, int] | None = None,
    default_limit: int | None = 10,
    topics: list[str] | None = None,
    schema_transforms: dict | None = None,
    topic_transforms: dict | None = None,
    reverse=True,
    debug=None,
) -> tuple[dict, dict]:
    """
    Returns a dictionary, indexed by topics, that contains
    stacked dictionaries of parsed ROS2 messages from an MCAP file.

    Returns:
        Dict of the form {topic: {entry: list[Any]}}.

    Example:
    ```
    data = _read_and_parse_messages(mcap, t_end=10., t_start=0.,
            topics=topics,
            limits=limits,
            default_limit=default_limit,
            schema_transforms=schema_transforms,
            parse_msg=parse_msg,
            debug=None
        )
    ```
    """
    summary = get_summary(mcap)
    message_start = summary.statistics.message_start_time * 1e-9
    t_end_ns = int(t_end * 1e9)
    t_start_ns = int(t_start * 1e9)
    schema_transforms = schema_transforms or {}
    topic_transforms = topic_transforms or {}
    topics = topics or [channel.topic for channel in summary.channels.values()]
    data = {}
    limits = limits or {}
    if default_limit is None:
        default_limit = np.inf
    for t in topics:
        data[t] = []
        if t in limits:
            continue
        limits[t] = default_limit
    counts = {t: 0 for t in topics}
    skipped = []
    msg_counter = 0
    for msg in read_ros2_messages(
        mcap,
        start_time=t_start_ns,
        end_time=t_end_ns,
        topics=topics,
        log_time_order=True,
        reverse=reverse,
    ):
        msg_counter += 1

        topic = msg.channel.topic
        schema = msg.schema.name
        # We might already have collected enough messages
        if all(counts[k] >= limits[k] for k in counts):
            break
        if counts[topic] >= limits[topic]:
            continue
        else:
            counts[topic] += 1

        if schema in msg_parser.registry:
            parsed_msg = msg_parser(msg)
            if isinstance(parsed_msg, list):
                parsed_msg = stack_dicts(parsed_msg)
        else:
            parsed_msg = base_message_parser(msg, include_ros_msg=True)
            skipped.append({"topic": topic, "schema": schema})

        # TODO: Not sure where to put this.
        parsed_msg["__mcap_start__"] = message_start

        # Apply transforms
        for k, f in schema_transforms.get(schema, {}).items():
            parsed_msg[k] = f(parsed_msg)
        for k, f in topic_transforms.get(topic, {}).items():
            parsed_msg[k] = f(parsed_msg)

        data[topic].append(parsed_msg)

    if debug is not None:
        debug.update(
            {"counts": counts, "message_count": msg_counter, "skipped": skipped}
        )

    return data


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   MCAP Taker
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
class IndexerField:
    """Enables bracket-based chaining (e.g. `taker.k[...].i[...]`) by setting
    an attribute on the parent object and returning it."""

    def __init__(self, obj, attr_name, index_transform=None):
        self.obj = obj
        self.attr_name = attr_name
        self.index_transform = index_transform

    def __getitem__(self, index):
        if self.index_transform is not None:
            index = self.index_transform(index)
        setattr(self.obj, self.attr_name, index)
        return self.obj


def _get_values(data, keys, inds):
    """Extract values from parsed MCAP data by key and index.

    Each key is of the form "/my/topic" or "/my/topic:path:to:field".
    The corresponding index (int or slice) selects from the message stack.
    """

    def resolve_nodes(v):
        if isinstance(v, dict) and "__node__" in v:
            return v["__node__"]
        else:
            return v

    results = []
    for k, i in zip(keys, inds):
        # topic (t) and address path (a) from key "/my/topic:path:to:field"
        t, *a = k.split(":")
        stack = data[t]
        # TODO: How to handle empty stacks?
        try:
            if len(a) == 0:
                vs = stack[i]
            else:
                vs = [extract(x, [a])[0] for x in stack][i]
        except Exception as e:
            raise e

        # TODO: resolve this better
        if isinstance(i, int):
            # Single element
            vs = resolve_nodes(vs)
        else:
            vs = [resolve_nodes(v) for v in vs]
        results.append(vs)

    return results


# TODO: Maybe add/overwrite .items(), .keys() and .values().
#   Probably should be that __iter__ returns values(). That would be the main
#   difference to a dict I guess.
class TakerResult(dict):
    """Result of a Taker query. Supports tuple unpacking via __iter__,
    which yields the extracted values for each key/index pair rather
    than dict keys."""

    def __init__(self, data, keys=None, inds=None, debug=None):
        super().__init__(data)
        self._keys = keys or list(data.keys())
        self._inds = inds or [slice(None, None, None) for _ in range(len(self._keys))]
        self._debug = debug or {}

    def to_dict(self):
        return dict(self._raw_items())

    def __iter__(self):
        return iter(self.values())

    def items(self):
        return zip(self._keys, self.values())

    def values(self):
        return _get_values(self.to_dict(), self._keys, self._inds)

    # def keys(self):
    #     return self._keys

    def _raw_items(self):
        return super().items()

    def _raw_values(self):
        return super().values()

    def _raw_keys(self):
        return super().keys()

    # # TODO: __getitem__, The question is really what data the result carries.
    # #   Does it only contain the keys it was querried with, or
    # #   the whole parsed message. I think I lean towards the whole message.
    # #   Or I could at least just allow keys of the form topix:address.
    # #   If the original querry key was just a topic then it would contain everything.
    # #   But then we had __node__, so dunno.
    # def __getitem__(self, key):
    #     return self.values()[key]


# TODO: we might want to add different versions of the taker result
#   taker._folded().k[*keys].i[0,:2].t(3., 4.) >> is the current behaviour
#   taker._raw().k[*keys].i[0,:2].t(3., 4.) >> would be an iterator over raw messages
#   >> would be an iterator over parsed or raw messages; only allows topic keys,
#   or ignores the rest
#   ````
# TODO: We need a convenient way to get the timestamps as well
# TODO: allow nested keys to a degree: `taker.k[key1, [key2a, key2b], ...]``
# TODO: Allow key_map, not only topic. i.e. instead of only
# "/zed/zed_node/left/image_rect_color" --> "/im",
# "/zed/zed_node/left/image_rect_color:data" --> "/im"
# "/zed/zed_node/left/image_rect_color:data" --> "/im:__node__"
# TODO: How to hancle empty lists in the results
class McapTaker:
    """Chainable interface for extracting parsed messages from an MCAP file.

    Supports key selection (.k), per-key indexing (.i), and time-based
    queries (.t / .elapsed). Keys are of the form "/topic" or
    "/topic:nested:field".

    Example::

        taker = McapTaker(mcap,
            topic_map={"/zed/zed_node/pose": "/pose"},
            topic_transforms={"/pose": {
                "__node__": lambda d: Transform.from_dict(d)
            }})

        ps, ts, pcs = taker.k[
            "/pose", "/pose:translation", "/zed/zed_node/pose_with_covariance"
        ].i[0, :5, 0].t(3., 4.)

    The key ``"__node__"`` has a special role in parsed messages: when a
    result dict contains ``"__node__"``, the value at that key is returned
    instead of the dict itself. This allows transforms to replace the
    parsed dict with an arbitrary object, e.g.::

        topic_transforms={"/pose": {
            "__node__": lambda d: Transform.from_dict(d)
        }}

    Here, lookups on ``"/pose"`` will return ``Transform`` objects directly
    rather than raw dicts.

    Args:
        mcap: Path to the MCAP file.
        topic_map: Optional mapping from original topics to shorter aliases.
        schema_transforms: Per-schema transforms applied to parsed messages.
            Dict of ``{schema: {key: func}}``. For each parsed message matching
            the schema, ``msg[key] = func(msg)`` is called — setting or replacing
            the key in the parsed dict.
        topic_transforms: Per-topic transforms applied to parsed messages.
            Same structure as schema_transforms but keyed by topic:
            ``{topic: {key: func}}``.
        msg_parser: Callable to parse MCAP ROS2 messages into
            human readable dictionaries.
    """

    def __init__(
        self,
        mcap: str | Path,
        *,
        topic_map: dict | None = None,
        schema_transforms: dict | None = None,
        topic_transforms: dict | None = None,
        msg_parser: Callable[[McapROS2Message], dict] = parse_msg,
    ):
        summary = get_summary(mcap)
        self.mcap = mcap
        self._keys = None
        self._inds = None
        self.k = IndexerField(
            self, "_keys", lambda i: i if isinstance(i, tuple) else [i]
        )
        self.i = IndexerField(
            self, "_inds", lambda i: i if isinstance(i, tuple) else [i]
        )
        self.valid_topics = [channel.topic for channel in summary.channels.values()]

        self.topic_map = topic_map or {}
        self.reverse_topic_map = {v: k for k, v in self.topic_map.items()}

        topic_transforms = topic_transforms or {}
        self.topic_transforms = {
            self._unmap_topic(topic): f for topic, f in topic_transforms.items()
        }
        self.schema_transforms = schema_transforms or {}
        self.msg_parser = msg_parser

        self.start_time = summary.statistics.message_start_time * 1e-9
        self.end_time = summary.statistics.message_end_time * 1e-9
        self.duration = self.end_time - self.start_time

    @property
    def channel_overview(self):
        return get_channel_overview(self.mcap)

    def _unmap_topic(self, topic):
        return self.reverse_topic_map.get(topic, topic)

    def _map_topic(self, topic):
        return self.topic_map.get(topic, topic)

    def _map_key(self, key):
        topic, *path = key.split(":")
        return ":".join([self._map_topic(topic), *path])

    def _unmap_key(self, key):
        topic, *path = key.split(":")
        return ":".join([self._unmap_topic(topic), *path])

    def _read_interval(
        self, t0: float, t1: float, default_limit: int = 10, reverse: bool = True
    ):
        """Query messages in the elapsed time window [t0, t1] (seconds from start).

        Returns a TakerResult that can be tuple-unpacked into one value per key.
        """
        # TODO: should we hand in the time_key that we use as time reference.
        #   As of now it's log_time, which is the default in read_ros2_messages
        # TODO: split keys into topics and addresses; this is cleaner.

        keys = self._keys or []
        unmapped_keys = [self._unmap_key(k) for k in keys]

        # TODO: Correct this, might need to unmap topics
        topics = []
        for k in unmapped_keys:
            if k in self.valid_topics:
                topics.append(k)
                continue

            if ":" in k:
                topics.append(k.split(":", 1)[0])
                continue

            raise KeyError(f'This is NOT a valid key: "{k}" !!!')

        mcap = self.mcap

        # TODO: limits can be computed from self._inds and reverse
        limits = None

        aux = {}
        data = _read_and_parse_messages(
            mcap,
            t_start=t0 + self.start_time,
            t_end=t1 + self.start_time,
            topics=topics,
            limits=limits,
            default_limit=default_limit,
            schema_transforms=self.schema_transforms,
            topic_transforms=self.topic_transforms,
            msg_parser=self.msg_parser,
            reverse=reverse,
            debug=aux,
        )

        data = {self._map_topic(k): v for k, v in data.items()}

        # TODO: Remove debug once resolved?
        #   Could actually add the time args to the result.
        return TakerResult(data, self._keys, self._inds, debug={"t0": t0, "t1": t1})

    def _read_closest(self, t, lag=2.0, sort_key="message_time"):
        result = self._read_interval(t - lag, t + lag, default_limit=None)
        t_ns = int((t + self.start_time) * 1e9)
        for k, list_of_dicts in result._raw_items():
            dts = []
            for d in list_of_dicts:
                dt = (d[sort_key] - t_ns) * 1e-9  # Convert to seconds
                d["__dt__"] = dt
                d["__lag__"] = dt
                dts.append(dt)

            order = np.argsort(np.abs(dts))

            result[k] = [list_of_dicts[i] for i in order]

        return result

    def _read_all(self, reverse: bool = False):
        """Read all messages from the MCAP file."""
        return self._read_interval(
            -2.0, self.duration + 2.0, default_limit=None, reverse=reverse
        )

    def t(
        self,
        t0: float | None = None,
        t1: float | None = None,
        default_limit: int | None = None,
        reverse: bool = False,  # TODO: Default to False? or None?
        lag: float = 2.0,
        sort_key: str = "message_time",
    ):
        if t0 is not None and t1 is not None:
            return self._read_interval(
                t0, t1, default_limit=default_limit, reverse=reverse
            )
        elif t0 is not None and t1 is None:
            return self._read_closest(t0, lag=lag, sort_key=sort_key)
        elif t0 is None and t1 is None:
            return self._read_all(reverse=reverse)
        else:
            raise ValueError("Invalid combination of function arguments t0 and t1.")
