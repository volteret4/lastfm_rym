#!/usr/bin/env python3
"""
Puente SOPS+age para reemplazar python-dotenv.

Uso (sustitución directa de load_dotenv):
    from sops_env import load_sops_env
    load_sops_env()

Equivalente al anterior:
    from dotenv import load_dotenv
    load_dotenv()
"""
import os
import subprocess
from pathlib import Path


def _find_encrypted_env(start: Path) -> Path:
    """Sube directorios desde `start` hasta encontrar .encrypted.env."""
    for directory in [start.resolve(), *start.resolve().parents]:
        candidate = directory / '.encrypted.env'
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"No se encontró .encrypted.env subiendo desde {start}"
    )


def load_sops_env(env_file: str | Path | None = None, override: bool = False) -> None:
    """
    Descifra un archivo .env cifrado con SOPS+age e inyecta las variables en os.environ.

    Args:
        env_file: Ruta al archivo cifrado. Si es None, busca .encrypted.env
                  subiendo desde el directorio de trabajo actual.
        override: Si True, sobreescribe variables ya presentes en os.environ.
    """
    if env_file is None:
        env_path = _find_encrypted_env(Path.cwd())
    else:
        env_path = Path(env_file)
        if not env_path.exists():
            raise FileNotFoundError(f"Archivo cifrado no encontrado: {env_path}")

    result = subprocess.run(
        ['sops', '--decrypt', str(env_path)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Error al descifrar {env_path} con sops:\n{result.stderr.strip()}"
        )

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if override or key not in os.environ:
            os.environ[key] = value


if __name__ == '__main__':
    before = set(os.environ)
    load_sops_env()
    loaded = {k: os.environ[k] for k in os.environ if k not in before}
    print(f"Variables cargadas ({len(loaded)}):")
    for key in sorted(loaded):
        value = loaded[key]
        masked = value[:4] + '***' if len(value) > 4 else '***'
        print(f"  {key}={masked}")
