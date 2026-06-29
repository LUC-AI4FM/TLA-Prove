from src.validators.sany_validator import _parse_errors


def test_parse_errors_keeps_meaningful_sany_detail() -> None:
    output = """
****** SANY2 Version 2.2 created 08 July 2020

Parsing file /tmp/AddTwo.tla
Labels added.
Fatal errors while parsing TLA+ spec in file /tmp/AddTwo.tla

In module AddTwo

Cannot find source file for module TLAPS imported in module AddTwo.
*** Errors: 1

In module AddTwo

Cannot find source file for module TLAPS imported in module AddTwo.
"""

    assert _parse_errors(output) == [
        "Cannot find source file for module TLAPS imported in module AddTwo.",
        "*** Errors: 1",
    ]
