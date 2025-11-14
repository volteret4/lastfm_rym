#!/usr/bin/env bash

python="${HOME}/Scripts/python_venv/bin/python3"

run_years_back() {
    local script="$1"
    shift
    for y in "$@"; do
        "$python" "$script" --years-back "$y"
    done
    "$python" html_index.py
    gtd
}

run_yearly() {
    for y in $(seq 1 18); do
        "$python" html_temporal.py yearly --years-ago "$y"
    done
    "$python" html_index.py
    gtd
}

run_monthly() {
    for year in $(seq 2025 -1 2007); do
        for month in $(seq -w 12 -1 1); do
            "$python" html_temporal.py monthly --month "$month" --year "$year"
        done
    done
    "$python" html_index.py
    gtd
}

run_weekly() {
    rm docs/esta-semana.html docs/semana-pasada.html docs/hace-dos-semanas.html docs/hace-tres-semanas.html
    for w in 0 1 2 3; do
        if [[ $w -eq 0 ]]; then
            "$python" html_temporal.py weekly
        else
            "$python" html_temporal.py weekly --week-offset "$w"
        fi
    done
    "$python" html_index.py
    gtd
}

case "$1" in
    usuarios)
        run_years_back html_usuarios.py 1 5 10 15 18
        ;;
    grupo)
        run_years_back html_grupo.py 1 5 10 15 18
        ;;
    anuales)
        run_yearly
        ;;
    mensuales)
        run_monthly
        ;;
    semanales)
        run_weekly
        ;;
    todo)
        run_weekly ; run_monthly ; run_yearly ; run_years_back "html_grupo.py --no-json" 1 5 10 15 18 ; run_years_back html_usuarios.py 1 5 10 15 18


        ;;
    *)
        echo "Uso: $0 {usuarios|grupo|anuales|mensuales|semanales}"
        exit 1
        ;;
esac
