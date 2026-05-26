# tests/test_errors.py
from forge.errors import (
    AuthError,
    ForgeError,
    NotFoundError,
    ServerError,
    UsageError,
    ValidationError,
)


def test_base_forge_error_default_exit_code_is_1():
    err = ForgeError("something broke")
    assert err.code == 1
    assert str(err) == "something broke"


def test_exit_code_mapping():
    assert UsageError("x").code == 2
    assert NotFoundError("x").code == 3
    assert AuthError("x").code == 4
    assert ServerError("x").code == 5
    assert ValidationError("x").code == 6


def test_subclasses_are_forge_errors():
    for cls in (UsageError, NotFoundError, AuthError, ServerError, ValidationError):
        assert issubclass(cls, ForgeError)
