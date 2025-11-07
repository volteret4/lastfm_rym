#!/users/bin/env bash
python="${HOME}/Scripts/python_venv/bin/python3"

cp -r docs docs_bak

${python} html_usuarios.py

${python} html_index.py

gitodo usuarios
