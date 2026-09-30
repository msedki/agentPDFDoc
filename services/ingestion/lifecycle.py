"""Drain the locked Docling iterator before its native parser is unloaded."""

import itertools
import json
import os
import threading
import time
from functools import lru_cache
from pathlib import Path

_TRACE_LOCK = threading.Lock()


def lifecycle_event(event, **fields):
    """Trace only lifecycle identifiers, ranges and counters, never PDF text."""
    record = {"event": event, "monotonic_seconds": time.monotonic(),
              "thread_id": threading.get_ident(), **fields}
    target = os.environ.get("RAG_INGESTION_LIFECYCLE_TRACE")
    if target:
        with _TRACE_LOCK, Path(target).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    return record


def draining_results(results, make_page, telemetry, record):
    """Closing the outer generator still exhausts the raw result iterator.

    Use an explicit loop: ``yield from`` would close the delegated iterator
    before the finally block can drain it. Discarded results are never sent to
    layout/OCR or converted into page objects.
    """
    try:
        for result in results:
            number = int(result.page_number)
            telemetry["yielded_page_numbers"].append(number)
            record("page_yield", page_number=number)
            yield make_page(result)
    finally:
        record("drain_start")
        for result in results:
            number = int(result.page_number)
            telemetry["drained_page_numbers"].append(number)
            record("page_drain", page_number=number)
        telemetry["iterator_exhausted"] = True
        record("iterator_exhausted")


@lru_cache(maxsize=1)
def draining_backend_class():
    """Use the official backend and parser; change only iterator teardown."""
    from docling.backend.docling_parse_backend import (
        ThreadedDoclingParseDocumentBackend,
        ThreadedDoclingParsePageBackend,
    )

    class DrainingDoclingParseBackend(ThreadedDoclingParseDocumentBackend):
        _sequence = itertools.count(1)

        def __init__(self, in_doc, path_or_stream, options=None):
            self.lifecycle = {"page_range": list(in_doc.limits.page_range),
                              "backend_name": "docling_parse", "iteration_mode": "threaded",
                              "backend_sequence": next(self._sequence),
                              "yielded_page_numbers": [], "drained_page_numbers": [],
                              "iterator_exhausted": False, "unload_completed": False}
            super().__init__(in_doc, path_or_stream, options)
            self.lifecycle["backend_instance"] = id(self)
            self.lifecycle["parser_instance"] = id(self.parser)
            self._record("backend_created")

        def _record(self, event, **fields):
            lifecycle_event(event, backend_instance=id(self), parser_instance=id(self.parser),
                            backend_sequence=self.lifecycle["backend_sequence"],
                            page_range=self.lifecycle["page_range"], **fields)

        def iter_pages(self):
            self._iterating = True
            self._record("producer_start")
            try:
                yield from draining_results(
                    self.parser.iterate_results(),
                    lambda result: ThreadedDoclingParsePageBackend(result, rendered=self._render_pages),
                    self.lifecycle, self._record,
                )
            finally:
                self._iterating = False
                self._record("producer_end")

        def unload(self):
            if self._closed:
                return
            self._record("unload_start")
            super().unload()
            self.lifecycle["unload_completed"] = True
            first, last = self.lifecycle["page_range"]
            self.lifecycle["drained_outside_page_range"] = [
                page for page in self.lifecycle["drained_page_numbers"] if not first <= page <= last
            ]
            self._record("unload_end", drained_page_numbers=self.lifecycle["drained_page_numbers"],
                         drained_outside_page_range=self.lifecycle["drained_outside_page_range"])

    return DrainingDoclingParseBackend


@lru_cache(maxsize=1)
def observed_pdfium_backend_class():
    """Observe the official Docling PDFium backend without changing its parser."""
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

    class ObservedPdfiumBackend(PyPdfiumDocumentBackend):
        _sequence = itertools.count(1)

        def __init__(self, in_doc, path_or_stream, options=None):
            self.lifecycle = {"page_range": list(in_doc.limits.page_range),
                              "backend_name": "pypdfium2", "iteration_mode": "random_access",
                              "backend_sequence": next(self._sequence),
                              "yielded_page_numbers": [], "drained_page_numbers": [],
                              "unload_completed": False}
            super().__init__(in_doc, path_or_stream, options)
            self.lifecycle["backend_instance"] = id(self)
            self._record("backend_created")

        def _record(self, event, **fields):
            lifecycle_event(event, backend_instance=id(self),
                            backend_sequence=self.lifecycle["backend_sequence"],
                            page_range=self.lifecycle["page_range"], backend_name="pypdfium2", **fields)

        def load_page(self, page_no):
            page = super().load_page(page_no)
            self.lifecycle["yielded_page_numbers"].append(page_no + 1)
            self._record("page_load", page_number=page_no + 1)
            return page

        def unload(self):
            if self._closed:
                return
            self._record("unload_start")
            super().unload()
            first, last = self.lifecycle["page_range"]
            actual = self.lifecycle["yielded_page_numbers"]
            self.lifecycle["unload_completed"] = True
            self.lifecycle["drained_outside_page_range"] = []
            self.lifecycle["loaded_outside_page_range"] = [page for page in actual if not first <= page <= last]
            self.lifecycle["requested_pages_complete"] = sorted(set(actual)) == list(range(first, last + 1))
            self._record("unload_end", yielded_page_numbers=actual,
                         loaded_outside_page_range=self.lifecycle["loaded_outside_page_range"])

    return ObservedPdfiumBackend
