import tarfile
from pathlib import Path

from scripts.build_verified_tlaps_sft import build_rows


def _add_text(archive: tarfile.TarFile, name: str, text: str) -> None:
    data = text.encode("utf-8")
    info = tarfile.TarInfo(name)
    info.size = len(data)
    import io

    archive.addfile(info, fileobj=io.BytesIO(data))


def test_verified_tlaps_sft_rows_use_harmony_developer_and_final_channel(tmp_path: Path) -> None:
    artifact = tmp_path / "proofs.tar.gz"
    proof = "---- MODULE Mini ----\nEXTENDS TLAPS\nTHEOREM T == TRUE\nPROOF OBVIOUS\n====\n"
    with tarfile.open(artifact, "w:gz") as archive:
        _add_text(archive, "run/proofs/Mini.tla", proof)

    rows = build_rows(artifact, "TLAPS 1.5.0 --threads 1")

    assert len(rows) == 1
    messages = rows[0]["messages"]
    assert messages[0]["role"] == "developer"
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["channel"] == "final"
    assert messages[-1]["content"] == proof
