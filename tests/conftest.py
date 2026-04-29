"""Stub out JVM-dependent modules so tests can import wbjdbc without Java."""
import sys
import types


def _build_jpype_stub():
    jpype = types.ModuleType("jpype")
    jpype.isJVMStarted = lambda: False
    jpype.startJVM = lambda *a, **kw: None
    jpype.JClassNotFoundException = Exception
    jpype.JVMNotSupportedException = Exception
    jpype.JObject = object
    jpype.JArray = object
    jpype.JByte = object

    java = types.SimpleNamespace(
        lang=types.SimpleNamespace(
            Class=types.SimpleNamespace(forName=lambda *a: None),
            Boolean=object,
            Integer=object,
            Long=object,
            Short=object,
            Byte=object,
            Float=object,
            Double=object,
        ),
        sql=types.SimpleNamespace(
            Date=object,
            Time=object,
            Timestamp=object,
            DriverManager=types.SimpleNamespace(
                getConnection=lambda *a: None,
            ),
        ),
        math=types.SimpleNamespace(BigDecimal=object),
    )
    jpype.java = java
    jpype.JClass = lambda name: object
    return jpype


def _build_jaydebeapi_stub():
    jdb = types.ModuleType("jaydebeapi")
    jdb.connect = lambda *a, **kw: None

    class _DBError(Exception):
        pass

    jdb.DatabaseError = _DBError
    return jdb


for _name, _builder in [("jpype", _build_jpype_stub), ("jaydebeapi", _build_jaydebeapi_stub)]:
    if _name not in sys.modules:
        sys.modules[_name] = _builder()

pkg = types.ModuleType("pkg_resources")
pkg.resource_filename = lambda *a: ""
if "pkg_resources" not in sys.modules:
    sys.modules["pkg_resources"] = pkg
