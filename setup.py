import os
import subprocess
from setuptools import setup, find_packages
import pathlib

# Caminho para o README.md
current_dir = pathlib.Path(__file__).parent.resolve()
long_description = (current_dir / "README.md").read_text(encoding="utf-8")

def install_dependencies():
    try:
        import jpype
        print("JPype1 já está instalado.")
    except ImportError:
        wheel_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'wbjdbc', 'resources', 'dependencies', 'jpype1-1.5.1-cp312-cp312-win_amd64.whl'))
        print(f"Instalando JPype1 de {wheel_path}")
        subprocess.check_call(['pip', 'install', wheel_path])


# Chama a função para instalar JPype1
install_dependencies()

setup(
    name="wbjdbc",
    version="1.0.2",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "wbjdbc": [
            "resources/server/**",
            "resources/maven/com.ibm.informix/*",
            "resources/maven/org.mongodb/*",
            "resources/dependencies/*",
        ]
    },
    install_requires=[],  # Não lista JPype1 aqui, pois ele é instalado manualmente
    description="Library to simplify JDBC and JVM configuration for Informix and MongoDB",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Wanderson Batista",
    author_email="wanderfreitasb@gmail.com",
    url="https://github.com/wanderbatistaf/wbjdbc",
)
