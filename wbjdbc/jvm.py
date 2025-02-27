import os
import sys
import subprocess
import time
import jpype
from pkg_resources import resource_filename


class JVMError(Exception):
    """Custom class for JVM-related errors."""
    pass


def ensure_jpype_installed():
    """Ensures that JPype1 is correctly installed."""
    try:
        import jpype
        # Debug
        # print("✅ JPype1 is already installed.")
    except ImportError:
        wheels_dir = resource_filename("wbjdbc", "wheels")

        if not os.path.isdir(wheels_dir):
            raise JVMError(f"❌ Wheels directory not found: {wheels_dir}")

        wheel_file = next((f for f in os.listdir(wheels_dir) if "JPype1" in f and f.endswith(".whl")), None)
        if not wheel_file:
            raise JVMError("❌ JPype1 wheel not found in the wheels directory.")

        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", os.path.join(wheels_dir, wheel_file)])
            print("✅ JPype1 successfully installed.")
        except subprocess.CalledProcessError as e:
            raise JVMError(f"❌ Failed to install JPype1: {e}")


# Ensures JPype1 is installed before proceeding
ensure_jpype_installed()


def find_java_executable():
    """Finds the path of the Java executable (`java.exe` or `java`)."""
    try:
        java_path = subprocess.check_output("where java", shell=True).decode().strip().split("\n")[0]
        print(f"\n🔍 **Java Detected:** {java_path}\n")
        return java_path
    except subprocess.CalledProcessError:
        raise JVMError("❌ Could not locate Java executable (java.exe). Ensure it is installed and in the PATH.")


def detect_java_home():
    """Automatically detects the correct JAVA_HOME."""
    java_home = os.environ.get("JAVA_HOME")

    if java_home:
        java_exe = os.path.join(java_home, "bin", "java.exe") if os.name == "nt" else os.path.join(java_home, "bin", "java")
        if os.path.isfile(java_exe):
            return java_home  # Returns if JAVA_HOME is valid

    try:
        java_path = subprocess.check_output("where java", shell=True).decode().strip().split("\n")[0]
        java_home = os.path.dirname(os.path.dirname(java_path))  # Moves two directories up to find JDK
        if os.path.isdir(java_home):
            return java_home
    except Exception:
        pass

    return None  # Failed to detect Java


def start_jvm(jars=None, java_home=None, debug=0):
    """
    Starts the JVM, ensuring the correct Java version is used.

    :param jars: List of additional JAR files.
    :param java_home: Alternative JAVA_HOME path (optional).
    :param debug: Enables additional logs.
    """
    try:
        if debug == 1:
            # Debug
            print("\n🔹 VALIDATING REQUIRED JVM PATHS...\n")

        # Automatically detects JAVA_HOME if not provided
        java_home = java_home or detect_java_home()
        if not java_home:
            raise JVMError("❌ No valid Java installation found.")

        print(f"🟢 JAVA_HOME detected: {java_home}\n")

        # Defines the JVM path
        jvm_path = os.path.join(java_home, "bin", "server", "jvm.dll") if os.name == "nt" else os.path.join(java_home,
                                                                                                            "lib",
                                                                                                            "server",
                                                                                                            "libjvm.so")

        if not os.path.isfile(jvm_path):
            raise JVMError(f"❌ JVM not found: {jvm_path}")

        if debug == 1:
            # Debug
            print(f"🟢 JVM Path: {jvm_path}  -->  ✅ Found\n")

        # JAR configuration
        if jars is None:
            jars = []

        # Adds the Informix JAR
        informix_jar = resource_filename("wbjdbc", "resources/maven/com.ibm.informix/jdbc-4.50.10.1.jar")
        jars.insert(0, informix_jar)

        # Adds the BSON JAR (MongoDB)
        bson_jar = resource_filename("wbjdbc", "resources/maven/org.mongodb/bson-3.8.0.jar")
        if os.path.isfile(bson_jar):
            jars.append(bson_jar)
        else:
            raise JVMError(f"❌ BSON JAR file not found: {bson_jar}")

        # Verifies that all JARs exist
        for jar in jars:
            if not os.path.isfile(jar):
                raise JVMError(f"❌ JAR file not found: {jar}")

        classpath = os.pathsep.join(jars)  # `;` on Windows, `:` on Linux/Mac

        if debug == 1:
            # Debug
            print("🔹 VALIDATING REQUIRED JARS...\n")
            for jar in jars:
                print(f"🟢 JAR: {jar}  -->  ✅ Found")

            print(f"\n🔹 Final Classpath: {classpath}\n")

        # Starts the JVM only if it's not already running
        if not jpype.isJVMStarted():
            print("\n🔄 Attempting to start JVM...\n")
            jpype.startJVM(jvm_path, f"-Djava.class.path={classpath}")

            time.sleep(1)

            # Verifies if the JDBC DriverManager class is correctly loaded
            try:
                jpype.java.lang.Class.forName("java.sql.DriverManager")
                if debug == 1:
                    # Debug
                    print("✅ Class java.sql.DriverManager successfully loaded!")
                else:
                    return
            except jpype.JClassNotFoundException:
                raise JVMError("❌ Error: Could not load the java.sql.DriverManager class!")

            print("✅ JVM successfully started!")
        else:
            print("✅ JVM is already running.")

    except JVMError as e:
        print(f"❌ JVM Initialization Error: {e}")
        raise
    except jpype.JVMNotSupportedException as e:
        print(f"❌ The JVM is not supported: {e}")
        raise
    except Exception as e:
        print(f"❌ Unexpected error while starting the JVM: {e}")
        raise