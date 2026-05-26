# src/forge/errors.py
class ForgeError(Exception):
    code = 1


class UsageError(ForgeError):
    code = 2


class NotFoundError(ForgeError):
    code = 3


class AuthError(ForgeError):
    code = 4


class ServerError(ForgeError):
    code = 5


class ValidationError(ForgeError):
    code = 6
