"""Unit tests for filename → corpus path routing."""

from pathlib import Path

from filename_parser import build_corpus_path, parse_filename


def test_full_clues():
    p = parse_filename("IBPS_PO_Prelims_Memory_Based_2024_Shift1.pdf")
    assert p.skip_reason is None
    assert p.year == "2024"
    assert p.bank == "IBPS"
    assert p.role == "PO"
    assert p.stage == "Prelims"
    assert p.shift == "Shift_1"
    assert p.memory_based is True
    dest = build_corpus_path(Path("corpus"), p, "IBPS_PO_Prelims_Memory_Based_2024_Shift1.pdf")
    assert dest == Path("corpus/IBPS/PO/2024/Prelims/Shift_1/IBPS_PO_Prelims_Memory_Based_2024_Shift1.pdf")


def test_missing_shift():
    p = parse_filename("SBI Clerk Mains 2023.pdf")
    assert p.bank == "SBI"
    assert p.role == "Clerk"
    assert p.stage == "Mains"
    assert p.shift is None
    dest = build_corpus_path(Path("corpus"), p, "SBI Clerk Mains 2023.pdf")
    assert dest == Path("corpus/SBI/Clerk/2023/Mains/_unknown_shift/SBI Clerk Mains 2023.pdf")


def test_ibps_rrb():
    p = parse_filename("IBPS RRB PO Prelims 2025 Shift 2.pdf")
    assert p.bank == "IBPS"
    assert p.role == "RRB"
    assert p.year == "2025"
    assert p.shift == "Shift_2"


def test_skip_old_year():
    # Pre-2023 is kept now
    p = parse_filename("IBPS_PO_2022_Prelims.pdf")
    assert p.skip_reason is None
    assert p.year == "2022"
    assert p.bank == "IBPS"
    dest = build_corpus_path(Path("corpus"), p, "IBPS_PO_2022_Prelims.pdf")
    assert dest == Path("corpus/IBPS/PO/2022/Prelims/_unknown_shift/IBPS_PO_2022_Prelims.pdf")


def test_no_year_kept():
    p = parse_filename("IBPS_Clerk_Prelims_Memory_Based_English_Questions.pdf")
    assert p.skip_reason is None
    assert p.year is None
    assert p.bank == "IBPS"
    dest = build_corpus_path(Path("corpus"), p, "IBPS_Clerk_Prelims_Memory_Based_English_Questions.pdf")
    assert dest == Path(
        "corpus/IBPS/Clerk/no_year/Prelims/_unknown_shift/IBPS_Clerk_Prelims_Memory_Based_English_Questions.pdf"
    )


def test_year_from_extra_url():
    p = parse_filename("memory_based.pdf", extra_text="https://x.com/ibps-po-2024-shift-1.pdf")
    assert p.year == "2024"
    assert p.bank == "IBPS"
    assert p.role == "PO"
    assert p.shift == "Shift_1"


def test_unsorted_no_bank():
    p = parse_filename("Memory_Based_Paper_2024_Shift3.pdf")
    assert p.year == "2024"
    assert p.bank is None
    dest = build_corpus_path(Path("corpus"), p, "Memory_Based_Paper_2024_Shift3.pdf")
    assert dest == Path("corpus/_unsorted/2024/Memory_Based_Paper_2024_Shift3.pdf")


def test_ordinal_shift():
    p = parse_filename("RBI Grade B 2024 2nd shift.pdf")
    assert p.bank == "RBI"
    assert p.role == "Grade_B"
    assert p.shift == "Shift_2"


def test_nabard():
    p = parse_filename("NABARD_Grade_A_2023_Mains.pdf")
    assert p.bank == "NABARD"
    assert p.year == "2023"
    assert p.stage == "Mains"


if __name__ == "__main__":
    tests = [
        test_full_clues,
        test_missing_shift,
        test_ibps_rrb,
        test_skip_old_year,
        test_no_year_kept,
        test_year_from_extra_url,
        test_unsorted_no_bank,
        test_ordinal_shift,
        test_nabard,
    ]
    for t in tests:
        t()
        print(f"OK {t.__name__}")
    print(f"All {len(tests)} tests passed.")
