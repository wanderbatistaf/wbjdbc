import os
import sys
import subprocess
import time
import platform
import glob
import jpype

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))


def _pkg_path(*parts):
    return os.path.join(_PKG_DIR, *parts)

class JVMError(Exception):
    """Custom class for JVM-related errors."""
    pass

def ensure_jpype_installed():
    """Ensures that JPype1 is correctly installed."""
    try:
        import jpype
        # Debug
        # print("[OK] JPype1 is already installed.")
    except ImportError:
        wheels_dir = _pkg_path("wheels")
        if not os.path.isdir(wheels_dir):
            raise JVMError(f"[ERROR] Wheels directory not found: {wheels_dir}")

        wheel_file = next((f for f in os.listdir(wheels_dir) if "JPype1" in f and f.endswith(".whl")), None)
        if not wheel_file:
            raise JVMError("[ERROR] JPype1 wheel not found in the wheels directory.")

        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", os.path.join(wheels_dir, wheel_file)])
            print("[OK] JPype1 successfully installed.")
        except subprocess.CalledProcessError as e:
            raise JVMError(f"[ERROR] Failed to install JPype1: {e}")

# Ensures JPype1 is installed before proceeding
ensure_jpype_installed()

def find_java_executable():
    """Finds the path of the Java executable (`java.exe` or `java`)."""
    try:
        if os.name == "nt":  # Windows
            java_path = subprocess.check_output("where java", shell=True).decode().strip().split("\n")[0]
        else:  # Linux/macOS
            java_path = subprocess.check_output("which java", shell=True).decode().strip()
        print(f"\n[INFO] Java Detected: {java_path}\n")
        return java_path
    except subprocess.CalledProcessError:
        raise JVMError("[ERROR] Could not locate Java executable. Ensure it is installed and in the PATH.")

def detect_java_home():
    """Automatically detects the correct JAVA_HOME."""
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        java_exe = os.path.join(java_home, "bin", "java.exe") if os.name == "nt" else os.path.join(java_home, "bin", "java")
        if os.path.isfile(java_exe):
            return java_home  # Returns if JAVA_HOME is valid

    # Try to detect automatically
    try:
        if os.name == "nt":  # Windows
            java_path = subprocess.check_output("where java", shell=True).decode().strip().split("\n")[0]
            java_home = os.path.dirname(os.path.dirname(java_path))  # Moves two directories up to find JDK
        elif platform.system().lower() == "darwin":  # macOS
            try:
                java_home = subprocess.check_output(["/usr/libexec/java_home"]).decode().strip()
            except subprocess.CalledProcessError:
                # Fallback for macOS
                java_path = subprocess.check_output("which java", shell=True).decode().strip()
                java_home = os.path.dirname(os.path.dirname(java_path))
        else:  # Linux
            java_path = subprocess.check_output("which java", shell=True).decode().strip()
            java_home = os.path.dirname(os.path.dirname(java_path))

        if os.path.isdir(java_home):
            return java_home
    except Exception:
        pass

    return None  # Failed to detect Java

def find_jvm_library(java_home):
    """Finds the JVM library path based on the operating system."""
    system = platform.system().lower()

    candidates = []
    if system == "darwin":  # macOS
        candidates = [
            os.path.join(java_home, "lib", "server", "libjvm.dylib"),
            os.path.join(java_home, "jre", "lib", "server", "libjvm.dylib"),
        ]
    elif system == "linux":
        candidates = [
            os.path.join(java_home, "lib", "server", "libjvm.so"),
            os.path.join(java_home, "jre", "lib", "amd64", "server", "libjvm.so"),
            os.path.join(java_home, "jre", "lib", "server", "libjvm.so"),
        ]
    elif system == "windows":
        candidates = [
            os.path.join(java_home, "bin", "server", "jvm.dll"),
        ]

    # Check candidates first
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    # Fallback: recursive search
    patterns = []
    if system == "darwin":
        patterns = [os.path.join(java_home, "**", "libjvm.dylib")]
    elif system == "linux":
        patterns = [os.path.join(java_home, "**", "libjvm.so")]
    elif system == "windows":
        patterns = [os.path.join(java_home, "**", "jvm.dll")]

    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        for match in matches:
            if os.path.isfile(match):
                return match

    return None

def start_jvm(jars=None, java_home=None, debug=0, db_type=None):
    """
    Starts the JVM, ensuring the correct Java version is used.
    :param jars: List of additional JAR files.
    :param java_home: Alternative JAVA_HOME path (optional).
    :param debug: Enables additional logs.
    :param db_type: Database type being connected to ("informix-sqli", "mysql",
        "postgresql", ...). Only Informix needs the bundled Informix/BSON jars added
        automatically; other database types use only the jars the caller passed in
        `jars`. When None (legacy callers), the Informix/BSON jars are added for
        backward compatibility, but only if present - a missing BSON jar no longer
        raises for non-Informix connections.
    """
    try:
        if debug == 1:
            # Debug
            print("\n[INFO] VALIDATING REQUIRED JVM PATHS...\n")

        # Automatically detects JAVA_HOME if not provided
        java_home = java_home or detect_java_home()
        if not java_home:
            raise JVMError("[ERROR] No valid Java installation found.")

        print(f"[OK] JAVA_HOME detected: {java_home}\n")

        # Find JVM library using cross-platform logic
        jvm_path = find_jvm_library(java_home)
        if not jvm_path:
            system = platform.system().lower()
            if system == "darwin":
                lib_name = "libjvm.dylib"
            elif system == "linux":
                lib_name = "libjvm.so"
            else:
                lib_name = "jvm.dll"

            raise JVMError(
                f"[ERROR] JVM library not found in JAVA_HOME={java_home}. "
                f"Looking for {lib_name}. "
                f"Ensure you have a complete JDK installation (not just JRE)."
            )

        if debug == 1:
            # Debug
            print(f"[OK] JVM Path: {jvm_path} --> Found\n")

        # JAR configuration
        if jars is None:
            jars = []

        # The Informix driver needs the BSON jar alongside it for its JSON/BSON
        # complex-type support. Only inject Informix+BSON when actually connecting
        # to Informix (or for legacy callers that don't pass db_type at all) -
        # MySQL/PostgreSQL connections must not require an unrelated MongoDB jar.
        if db_type in (None, "informix-sqli"):
            informix_jar = _pkg_path("resources", "maven", "com.ibm.informix", "jdbc-4.50.10.1.jar")
            if os.path.isfile(informix_jar) and informix_jar not in jars:
                jars.insert(0, informix_jar)

            bson_jar = _pkg_path("resources", "maven", "org.mongodb", "bson-3.8.0.jar")
            if os.path.isfile(bson_jar) and bson_jar not in jars:
                jars.append(bson_jar)
            elif db_type == "informix-sqli" and not os.path.isfile(bson_jar):
                raise JVMError(f"[ERROR] BSON JAR file not found: {bson_jar}")

        # Verifies that all JARs exist
        for jar in jars:
            if not os.path.isfile(jar):
                raise JVMError(f"[ERROR] JAR file not found: {jar}")

        classpath = os.pathsep.join(jars)  # `;` on Windows, `:` on Linux/Mac

        if debug == 1:
            # Debug
            print("[INFO] VALIDATING REQUIRED JARS...\n")
            for jar in jars:
                print(f"[OK] JAR: {jar} --> Found")
            print(f"\n[INFO] Final Classpath: {classpath}\n")

        # Starts the JVM only if it's not already running
        if not jpype.isJVMStarted():
            print("\n[INFO] Attempting to start JVM...\n")
            jpype.startJVM(jvm_path, f"-Djava.class.path={classpath}")
            time.sleep(1)

            # Verifies if the JDBC DriverManager class is correctly loaded
            try:
                jpype.java.lang.Class.forName("java.sql.DriverManager")
                if debug == 1:
                    # Debug
                    print("[OK] Class java.sql.DriverManager successfully loaded!")
                else:
                    return
            except jpype.JClassNotFoundException:
                raise JVMError("[ERROR] Could not load the java.sql.DriverManager class!")

            print("[OK] JVM successfully started!")
        else:
            print("[OK] JVM is already running.")

    except JVMError as e:
        print(f"[ERROR] JVM Initialization Error: {e}")
        raise
    except jpype.JVMNotSupportedException as e:
        print(f"[ERROR] The JVM is not supported: {e}")
        raise
    except Exception as e:
        print(f"[ERROR] Unexpected error while starting the JVM: {e}")
        raise
