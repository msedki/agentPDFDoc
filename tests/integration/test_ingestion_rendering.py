"""Discriminate threaded-parser rendering without layout, OCR or Torch models."""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def install_seh_capture(directory):
    """Diagnostic observer: always continue normal Windows exception search."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class ExceptionRecord(ctypes.Structure):
        _fields_ = [("code", wintypes.DWORD), ("flags", wintypes.DWORD),
                    ("nested", ctypes.c_void_p), ("address", ctypes.c_void_p),
                    ("parameter_count", wintypes.DWORD), ("parameters", ctypes.c_size_t * 15)]

    class ExceptionPointers(ctypes.Structure):
        _fields_ = [("record", ctypes.POINTER(ExceptionRecord)), ("context", ctypes.c_void_p)]

    callback_type = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.POINTER(ExceptionPointers))
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.AddVectoredExceptionHandler.argtypes = [wintypes.ULONG, callback_type]
    kernel.AddVectoredExceptionHandler.restype = ctypes.c_void_p
    kernel.RemoveVectoredExceptionHandler.argtypes = [ctypes.c_void_p]
    kernel.RemoveVectoredExceptionHandler.restype = wintypes.ULONG
    kernel.GetModuleHandleExW.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    kernel.GetModuleHandleExW.restype = wintypes.BOOL
    kernel.GetModuleFileNameW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR, wintypes.DWORD]
    kernel.GetModuleFileNameW.restype = wintypes.DWORD
    kernel.GetCurrentThreadId.restype = wintypes.DWORD
    target = Path(directory) / "native-seh-addresses.jsonl"

    @callback_type
    def observe(pointer):
        try:
            record = pointer.contents.record.contents
            if record.code == 0xC0000005:
                module = ctypes.c_void_p()
                name = ctypes.create_unicode_buffer(32768)
                located = kernel.GetModuleHandleExW(0x00000004 | 0x00000002, record.address, ctypes.byref(module))
                if located:
                    kernel.GetModuleFileNameW(module, name, len(name))
                evidence = {"exception_code": hex(record.code), "exception_flags": record.flags,
                            "monotonic_seconds": time.monotonic(),
                            "exception_address": hex(record.address or 0), "module": name.value or None,
                            "module_offset": hex(record.address - module.value) if located and module.value else None,
                            "thread_id": kernel.GetCurrentThreadId(), "observer": "vectored",
                            "operation": record.parameters[0] if record.parameter_count else None,
                            "accessed_address": hex(record.parameters[1]) if record.parameter_count >= 2 else None,
                            "disposition": "EXCEPTION_CONTINUE_SEARCH"}
                with target.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(evidence) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
        except Exception:
            # An observer must never replace the original Windows disposition.
            pass
        return 0

    handle = kernel.AddVectoredExceptionHandler(1, observe)
    if not handle:
        raise OSError(ctypes.get_last_error(), "Cannot register diagnostic SEH observer")
    return kernel, handle, observe


# Défaut tiers connu (W-PDF01) : avec Torch chargé, le rendu concurrent de docling_parse provoque par intermittence
# une violation d'accès native ; la voie nominale n'utilise plus ce rendu (DECISIONS.md, W009). Le diagnostic
# reste exécuté : un passage est signalé XPASS et montrerait que le défaut a disparu.
# Constaté sous Windows seulement (pdf_parsers.cp312-win_amd64.pyd) : ailleurs, ces essais sont ordinaires et toute
# faute les fait échouer (aucune sous Linux aarch64 le 01/10, W018). Non strict sous Windows : le défaut est
# intermittent (journal du 30/09, 21:46-22:02 : le cas à une itération est passé au second essai) ; un XPASS
# strict y ferait échouer une série sans faute.
KNOWN_TORCH_RENDER_FAULT = pytest.mark.xfail(sys.platform == "win32", reason="W-PDF01 : faute native de docling_parse avec Torch chargé ; voie nominale pypdfium2 (W009)", strict=False)


@pytest.mark.parametrize("threads,concurrent,load_torch", [(2, False, False), (2, True, False), (1, True, False),
                                                           pytest.param(2, True, True, marks=KNOWN_TORCH_RENDER_FAULT)])
def test_real_docling_parser_render_lifecycle(tmp_path, threads, concurrent, load_torch):
    assert_render_diagnostic(tmp_path, threads, concurrent, load_torch)


@KNOWN_TORCH_RENDER_FAULT
def test_real_docling_parser_render_stress_with_torch(tmp_path):
    assert_render_diagnostic(tmp_path, 2, True, True, iterations=16)


def assert_render_diagnostic(tmp_path, threads, concurrent, load_torch, iterations=1):
    from test_ingestion_ocr import write_printed_pdf

    source = write_printed_pdf(tmp_path / "scan90.pdf", native=False, image_rotation=90)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    diagnostic = tmp_path / "render-diagnostic.json"
    process = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), str(source), str(tmp_path),
         str(threads), str(int(concurrent)), str(int(load_torch)), str(iterations)],
        stdin=subprocess.DEVNULL, capture_output=True, close_fds=True,
        timeout=120, check=False,
    )
    assert diagnostic.is_file(), {"exit_code": process.returncode}
    result = json.loads(diagnostic.read_text(encoding="utf-8"))
    assert process.returncode == 0, result
    assert result["source_sha256"] == source_hash == hashlib.sha256(source.read_bytes()).hexdigest()
    assert len(result["images"]) == 2 * iterations
    assert result["images"][0]["size"] == [600, 800]
    assert result["images"][1]["size"] == [1800, 2400]
    assert result["native_fault_bytes"] == 0, result


def test_seh_observer_records_a_deliberately_handled_access_violation(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows SEH control.")
    code = (
        "import ctypes, faulthandler, json, pathlib, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from test_ingestion_rendering import install_seh_capture\n"
        "directory = pathlib.Path(sys.argv[2])\n"
        "with (directory / 'control-faulthandler.log').open('ab', buffering=0) as stream:\n"
        "    faulthandler.enable(file=stream, all_threads=True)\n"
        "    capture = install_seh_capture(directory)\n"
        "    handled = False\n"
        "    try:\n"
        "        ctypes.string_at(0)\n"
        "    except OSError:\n"
        "        handled = True\n"
        "    finally:\n"
        "        capture[0].RemoveVectoredExceptionHandler(capture[1])\n"
        "        faulthandler.disable()\n"
        "(directory / 'control.json').write_text(json.dumps({'handled': handled}))\n"
    )
    child = subprocess.run([sys.executable, "-c", code, str(Path(__file__).parent.resolve()), str(tmp_path)],
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=30, close_fds=True, check=False)
    assert child.returncode == 0
    assert json.loads((tmp_path / "control.json").read_text())["handled"] is True
    records = [json.loads(line) for line in (tmp_path / "native-seh-addresses.jsonl").read_text().splitlines()]
    assert len(records) == 1
    assert records[0]["exception_code"] == "0xc0000005"
    assert records[0]["accessed_address"] == "0x0"
    assert records[0]["module"]
    assert b"Windows fatal exception: access violation" in (tmp_path / "control-faulthandler.log").read_bytes()


def run_diagnostic(source, directory, threads, concurrent, load_torch=False, iterations=1):
    import faulthandler
    import queue
    import threading

    from docling_parse.pdf_parser import (
        DoclingThreadedPdfParser,
        RenderConfig,
        ThreadedPdfParserConfig,
    )

    source, directory = Path(source), Path(directory)
    fault_path = directory / "render-native-fault.log"
    result = {"threads": threads, "concurrent": concurrent, "load_torch": load_torch, "iterations": iterations,
              "images": [], "phases": [],
              "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}

    def phase(name):
        record = {"phase": name, "time": time.monotonic(), "cycle": result.get("current_cycle"), "native_fault_bytes": fault_path.stat().st_size}
        result["phases"].append(record)
        with (directory / "render-phases.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def render(page):
        for scale in [1.0, 3.0]:
            phase(f"image_{scale}_start")
            image = page.get_image(scale=scale)
            image.save(directory / f"render-{result['current_cycle']}-{scale}.png")
            result["images"].append({"cycle": result["current_cycle"], "scale": scale, "size": list(image.size),
                                     "pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest()})
            phase(f"image_{scale}_end")

    with fault_path.open("ab", buffering=0) as stream:
        faulthandler.enable(file=stream, all_threads=True)
        capture = install_seh_capture(directory)
        try:
            if load_torch:
                phase("torch_import_start")
                import torch

                torch.set_num_threads(threads)
                torch.set_num_interop_threads(1)
                result["torch_version"] = torch.__version__
                phase("torch_import_end")
            for cycle in range(iterations):
                result["current_cycle"] = cycle
                phase("parser_create")
                config = ThreadedPdfParserConfig(threads=threads, render_config=RenderConfig())
                parser = DoclingThreadedPdfParser(parser_config=config)
                key = parser.load(source, page_range=(1, 1))
                phase("parser_loaded")
                if concurrent:
                    pages = queue.Queue()
                    producer_errors = []

                    def produce(parser=parser, pages=pages, producer_errors=producer_errors):
                        try:
                            for page in parser.iterate_results():
                                pages.put(page)
                            phase("producer_exhausted")
                        except Exception as exc:
                            producer_errors.append(type(exc).__name__)
                        finally:
                            pages.put(None)

                    producer = threading.Thread(target=produce, name="render-diagnostic-producer")
                    producer.start()
                    while (page := pages.get(timeout=30)) is not None:
                        render(page)
                    producer.join(timeout=30)
                    assert not producer.is_alive() and not producer_errors
                else:
                    for page in parser.iterate_results():
                        render(page)
                    phase("producer_exhausted")
                phase("parser_unload_start")
                parser.unload(key)
                phase("parser_unload_end")
        except Exception as exc:
            result["error_type"] = type(exc).__name__
        finally:
            if capture is not None:
                capture[0].RemoveVectoredExceptionHandler(capture[1])
            faulthandler.disable()
    result["native_fault_bytes"] = fault_path.stat().st_size
    (directory / "render-diagnostic.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if "error_type" not in result else 2


if __name__ == "__main__":
    raise SystemExit(run_diagnostic(sys.argv[1], sys.argv[2], int(sys.argv[3]), bool(int(sys.argv[4])), bool(int(sys.argv[5])), int(sys.argv[6]) if len(sys.argv) > 6 else 1))
