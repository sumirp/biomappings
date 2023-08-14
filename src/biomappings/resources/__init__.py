# -*- coding: utf-8 -*-

"""Biomappings resources."""

import csv
import itertools as itt
from collections import defaultdict
from pathlib import Path
from typing import (
    Any,
    DefaultDict,
    Dict,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import bioregistry
from tqdm.auto import tqdm

from biomappings.utils import OVERRIDE_MIRIAM, RESOURCE_PATH, get_canonical_tuple

MAPPINGS_HEADER = [
    "source prefix",
    "source identifier",
    "source name",
    "relation",
    "target prefix",
    "target identifier",
    "target name",
    "type",
    "source",
    "prediction_type",
    "prediction_source",
    "prediction_confidence",
]
PREDICTIONS_HEADER = [
    "source prefix",
    "source identifier",
    "source name",
    "relation",
    "target prefix",
    "target identifier",
    "target name",
    "type",
    "confidence",
    "source",
]


class MappingTuple(NamedTuple):
    """A named tuple class for mappings."""

    source_prefix: str
    source_id: str
    source_name: str
    relation: str
    target_prefix: str
    target_identifier: str
    target_name: str
    type: str
    source: str
    prediction_type: Optional[str]
    prediction_source: Optional[str]
    prediction_confidence: Optional[float]

    def as_dict(self) -> Mapping[str, Any]:
        """Get the mapping tuple as a dictionary."""
        return dict(zip(MAPPINGS_HEADER, self))  # type:ignore

    @classmethod
    def from_dict(cls, mapping: Mapping[str, str]) -> "MappingTuple":
        """Get the mapping tuple from a dictionary."""
        values = []
        for key in MAPPINGS_HEADER:
            value = mapping.get(key) or None
            if key == "prediction_confidence" and value is not None:
                value = float(value)  # type:ignore
            values.append(value)
        return cls(*values)  # type:ignore

    @property
    def source_curie(self) -> str:
        """Concatenate the source prefix and ID to a CURIE."""
        return f"{self.source_prefix}:{self.source_id}"

    @property
    def target_curie(self) -> str:
        """Concatenate the target prefix and ID to a CURIE."""
        return f"{self.target_prefix}:{self.target_identifier}"


class PredictionTuple(NamedTuple):
    """A named tuple class for predictions."""

    source_prefix: str
    source_id: str
    source_name: str
    relation: str
    target_prefix: str
    target_identifier: str
    target_name: str
    type: str
    confidence: float
    source: str

    def as_dict(self) -> Mapping[str, Any]:
        """Get the prediction tuple as a dictionary."""
        return dict(zip(PREDICTIONS_HEADER, self))  # type:ignore

    @classmethod
    def from_dict(cls, mapping: Mapping[str, str]) -> "PredictionTuple":
        """Get the prediction tuple from a dictionary."""
        values = []
        for key in PREDICTIONS_HEADER:
            value = mapping.get(key) or None
            if key == "confidence" and value is not None:
                value = float(value)  # type:ignore
            values.append(value)
        return cls(*values)  # type:ignore

    @classmethod
    def from_semra(cls, mapping, confidence) -> "PredictionTuple":
        """Instantiate from a SeMRA mapping."""
        import pyobo
        import semra

        s_name = pyobo.get_name(*mapping.s.pair)
        if not s_name:
            raise KeyError(f"could not look up name for {mapping.s.curie}")
        o_name = pyobo.get_name(*mapping.o.pair)
        if not o_name:
            raise KeyError(f"could not look up name for {mapping.o.curie}")
        # Assume that each mapping has a single simple evidence with a mapping set annotation
        if len(mapping.evidence) != 1:
            raise ValueError
        evidence = mapping.evidence[0]
        if not isinstance(evidence, semra.SimpleEvidence):
            raise TypeError
        if evidence.mapping_set is None:
            raise ValueError
        return cls(  # type:ignore
            *mapping.s.pair,
            s_name,
            mapping.p.curie,
            *mapping.o.pair,
            o_name,
            evidence.justification.curie,
            confidence,
            evidence.mapping_set.name,
        )

    @property
    def source_curie(self) -> str:
        """Concatenate the source prefix and ID to a CURIE."""
        return f"{self.source_prefix}:{self.source_id}"

    @property
    def target_curie(self) -> str:
        """Concatenate the target prefix and ID to a CURIE."""
        return f"{self.target_prefix}:{self.target_identifier}"


def get_resource_file_path(fname) -> Path:
    """Get a resource by its file name."""
    return RESOURCE_PATH.joinpath(fname)


def _load_table(fname) -> List[Dict[str, str]]:
    with open(fname, "r") as fh:
        reader = csv.reader(fh, delimiter="\t")
        header = next(reader)
        return [_clean(header, row) for row in reader]


def _clean(header, row):
    d = dict(zip(header, row))
    return {k: v if v else None for k, v in d.items()}


def _write_helper(
    header: Sequence[str], lod: Iterable[Mapping[str, str]], path: Union[str, Path], mode: str
) -> None:
    lod = sorted(lod, key=mapping_sort_key)
    with open(path, mode) as file:
        if mode == "w":
            print(*header, sep="\t", file=file)  # noqa:T201
        for line in lod:
            print(*[line[k] or "" for k in header], sep="\t", file=file)  # noqa:T201


def mapping_sort_key(prediction: Mapping[str, str]) -> Tuple[str, ...]:
    """Return a tuple for sorting mapping dictionaries."""
    return (
        prediction["source prefix"],
        prediction["source identifier"],
        prediction["relation"],
        prediction["target prefix"],
        prediction["target identifier"],
        prediction["type"],
        prediction["source"] or "",
    )


TRUE_MAPPINGS_PATH = get_resource_file_path("mappings.tsv")


def load_mappings(*, path: Optional[Path] = None) -> List[Dict[str, str]]:
    """Load the mappings table."""
    return _load_table(path or TRUE_MAPPINGS_PATH)


def append_true_mappings(
    m: Iterable[Mapping[str, str]],
    *,
    sort: bool = True,
    path: Optional[Path] = None,
) -> None:
    """Append new lines to the mappings table."""
    if path is None:
        path = TRUE_MAPPINGS_PATH
    _write_helper(MAPPINGS_HEADER, m, path, mode="a")
    if sort:
        lint_true_mappings(path=path)


def append_true_mapping_tuples(mappings: Iterable[MappingTuple]) -> None:
    """Append new lines to the mappings table."""
    append_true_mappings(mapping.as_dict() for mapping in set(mappings))


def write_true_mappings(m: Iterable[Mapping[str, str]], *, path: Optional[Path] = None) -> None:
    """Write mappigns to the true mappings file."""
    _write_helper(MAPPINGS_HEADER, m, path or TRUE_MAPPINGS_PATH, mode="w")


def lint_true_mappings(*, standardize: bool = False, path: Optional[Path] = None) -> None:
    """Lint the true mappings file."""
    mappings = load_mappings(path=path)
    mappings = _remove_redundant(mappings, MappingTuple, standardize=standardize)
    write_true_mappings(sorted(mappings, key=mapping_sort_key), path=path)


FALSE_MAPPINGS_PATH = get_resource_file_path("incorrect.tsv")


def load_false_mappings(*, path: Optional[Path] = None) -> List[Dict[str, str]]:
    """Load the false mappings table."""
    return _load_table(path or FALSE_MAPPINGS_PATH)


def append_false_mappings(
    m: Iterable[Mapping[str, str]],
    *,
    sort: bool = True,
    path: Optional[Path] = None,
) -> None:
    """Append new lines to the false mappings table."""
    if path is None:
        path = FALSE_MAPPINGS_PATH
    _write_helper(MAPPINGS_HEADER, m, path, mode="a")
    if sort:
        lint_false_mappings(path=path)


def write_false_mappings(m: Iterable[Mapping[str, str]], *, path: Optional[Path] = None) -> None:
    """Write mappings to the false mappings file."""
    _write_helper(MAPPINGS_HEADER, m, path or FALSE_MAPPINGS_PATH, mode="w")


def lint_false_mappings(*, standardize: bool = False, path: Optional[Path] = None) -> None:
    """Lint the false mappings file."""
    mappings = load_false_mappings(path=path)
    mappings = _remove_redundant(mappings, MappingTuple, standardize=standardize)
    write_false_mappings(sorted(mappings, key=mapping_sort_key), path=path)


UNSURE_PATH = get_resource_file_path("unsure.tsv")


def load_unsure(*, path: Optional[Path] = None) -> List[Dict[str, str]]:
    """Load the unsure table."""
    return _load_table(path or UNSURE_PATH)


def append_unsure_mappings(
    m: Iterable[Mapping[str, str]],
    *,
    sort: bool = True,
    path: Optional[Path] = None,
) -> None:
    """Append new lines to the "unsure" mappings table."""
    if path is None:
        path = UNSURE_PATH
    _write_helper(MAPPINGS_HEADER, m, path, mode="a")
    if sort:
        lint_unsure_mappings(path=path)


def write_unsure_mappings(m: Iterable[Mapping[str, str]], *, path: Optional[Path] = None) -> None:
    """Write mappings to the unsure mappings file."""
    _write_helper(MAPPINGS_HEADER, m, path or UNSURE_PATH, mode="w")


def lint_unsure_mappings(*, standardize: bool = False, path: Optional[Path] = None) -> None:
    """Lint the unsure mappings file."""
    mappings = load_unsure(path=path)
    mappings = _remove_redundant(mappings, MappingTuple, standardize=standardize)
    write_unsure_mappings(sorted(mappings, key=mapping_sort_key), path=path)


PREDICTIONS_PATH = get_resource_file_path("predictions.tsv")


def load_predictions(*, path: Optional[Path] = None) -> List[Dict[str, str]]:
    """Load the predictions table."""
    return _load_table(path or PREDICTIONS_PATH)


def write_predictions(m: Iterable[Mapping[str, str]], *, path: Optional[Path] = None) -> None:
    """Write new content to the predictions table."""
    _write_helper(PREDICTIONS_HEADER, m, path or PREDICTIONS_PATH, mode="w")


def append_prediction_tuples(
    prediction_tuples: Iterable[PredictionTuple],
    *,
    deduplicate: bool = True,
    sort: bool = True,
    standardize: bool = True,
) -> None:
    """Append new lines to the predictions table that come as canonical tuples."""
    append_predictions(
        (prediction_tuple.as_dict() for prediction_tuple in set(prediction_tuples)),
        deduplicate=deduplicate,
        sort=sort,
        standardize=standardize,
    )


def append_predictions(
    mappings: Iterable[Mapping[str, str]],
    *,
    deduplicate: bool = True,
    sort: bool = True,
    standardize: bool = True,
) -> None:
    """Append new lines to the predictions table."""
    if standardize:
        mappings = _standardize_mappings(mappings)
    if deduplicate:
        existing_mappings = {
            get_canonical_tuple(existing_mapping)
            for existing_mapping in itt.chain(
                load_mappings(),
                load_false_mappings(),
                load_unsure(),
                load_predictions(),
            )
        }
        mappings = (
            mapping for mapping in mappings if get_canonical_tuple(mapping) not in existing_mappings
        )

    _write_helper(PREDICTIONS_HEADER, mappings, PREDICTIONS_PATH, mode="a")
    if sort:
        lint_predictions()


def lint_predictions(standardize: bool = False) -> None:
    """Lint the predictions file.

    1. Make sure there are no redundant rows
    2. Make sure no rows in predictions match a row in the curated files
    3. Make sure it's sorted

    :param standardize: Should identifiers be standardized (against the
             combination of Identifiers.org and Bioregistry)?
    """
    curated_mappings = {
        get_canonical_tuple(mapping)
        for mapping in itt.chain(
            load_mappings(),
            load_false_mappings(),
            load_unsure(),
        )
    }
    mappings = [
        mapping
        for mapping in tqdm(
            load_predictions(), desc="Removing curated from predicted", unit_scale=True
        )
        if get_canonical_tuple(mapping) not in curated_mappings
    ]
    mappings = _remove_redundant(mappings, PredictionTuple, standardize=standardize)
    write_predictions(sorted(mappings, key=mapping_sort_key))


def _remove_redundant(mappings, tuple_cls, standardize: bool = False):
    if standardize:
        mappings = _standardize_mappings(mappings)
    return (mapping.as_dict() for mapping in {tuple_cls.from_dict(mapping) for mapping in mappings})


def _standardize_mappings(mappings, *, progress: bool = True):
    for mapping in tqdm(
        mappings,
        desc="Standardizing mappings",
        unit_scale=True,
        unit="mapping",
        disable=not progress,
    ):
        yield _standardize_mapping(mapping)


def _standardize_mapping(mapping):
    """Standardize a mapping."""
    for prefix_key, identifier_key in [
        ("source prefix", "source identifier"),
        ("target prefix", "target identifier"),
    ]:
        prefix, identifier = mapping[prefix_key], mapping[identifier_key]
        resource = bioregistry.get_resource(prefix)
        if resource is None:
            raise ValueError
        miriam_prefix = resource.get_miriam_prefix()
        if miriam_prefix is None or miriam_prefix in OVERRIDE_MIRIAM:
            mapping[identifier_key] = resource.standardize_identifier(identifier)
        else:
            mapping[identifier_key] = (
                resource.miriam_standardize_identifier(identifier) or identifier
            )

    return mapping


def load_curators():
    """Load the curators table."""
    return _load_table(get_resource_file_path("curators.tsv"))


def filter_predictions(custom_filter: Mapping[str, Mapping[str, Mapping[str, str]]]) -> None:
    """Filter all the predictions by removing what's in the custom filter then re-write.

    :param custom_filter: A filter 3-dictionary of source prefix to target prefix
        to source identifier to target identifier
    """
    predictions = load_predictions()
    predictions = [
        prediction for prediction in predictions if _check_filter(prediction, custom_filter)
    ]
    write_predictions(predictions)


def _check_filter(
    prediction: Mapping[str, str],
    custom_filter: Mapping[str, Mapping[str, Mapping[str, str]]],
) -> bool:
    source_prefix, target_prefix = prediction["source prefix"], prediction["target prefix"]
    source_id, target_id = prediction["source identifier"], prediction["target identifier"]
    return target_id != custom_filter.get(source_prefix, {}).get(target_prefix, {}).get(source_id)


def get_curated_filter() -> Mapping[str, Mapping[str, Mapping[str, str]]]:
    """Get a filter over all curated mappings."""
    d: DefaultDict[str, DefaultDict[str, Dict[str, str]]] = defaultdict(lambda: defaultdict(dict))
    for m in itt.chain(load_mappings(), load_false_mappings(), load_unsure()):
        d[m["source prefix"]][m["target prefix"]][m["source identifier"]] = m["target identifier"]
    return {k: dict(v) for k, v in d.items()}


def prediction_tuples_from_semra(
    mappings,
    *,
    confidence: float,
) -> List[PredictionTuple]:
    """Get prediction tuples from SeMRA mappings."""
    rows = []
    for mapping in mappings:
        try:
            row = PredictionTuple.from_semra(mapping, confidence)
        except KeyError as e:
            tqdm.write(str(e))
            continue
        rows.append(row)
    return rows
