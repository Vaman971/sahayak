"""
Ports: The Contracts

A port is a typing.Protocol, it describs what something can do, not who does it.
Any class with matching methods satisfies it, with no inheritence needed.
That's called structural typing, and mypy checks it at every call site
"""
