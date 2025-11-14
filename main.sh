#!/users/bin/env bash
python="${HOME}/Scripts/python_venv/bin/python3"

#cp -r docs docs_bak

# usuarios
if [[ $1 == "usuarios" ]]; then
    ${python} html_usuarios.py --years-back 1
    ${python} html_usuarios.py --years-back 5
    ${python} html_usuarios.py --years-back 10
    ${python} html_usuarios.py --years-back 15
    ${python} html_usuarios.py --years-back 18
    exit 0
fi
# grupo
if [[ $1 == "grupo" ]]; then
    ${python} html_grupo.py --years-back 1
    ${python} html_grupo.py --years-back 5
    ${python} html_grupo.py --years-back 10
    ${python} html_grupo.py --years-back 15
    ${python} html_grupo.py --years-back 18
    exit 0
fi
# temporal

# TEMPORAL
# Anuales
if [[ $1 == "anuales" ]]; then
    ${python} html_temporal.py yearly --years-ago 1
    ${python} html_temporal.py yearly --years-ago 2
    ${python} html_temporal.py yearly --years-ago 3
    ${python} html_temporal.py yearly --years-ago 4
    ${python} html_temporal.py yearly --years-ago 5
    ${python} html_temporal.py yearly --years-ago 6
    ${python} html_temporal.py yearly --years-ago 7
    ${python} html_temporal.py yearly --years-ago 8
    ${python} html_temporal.py yearly --years-ago 9
    ${python} html_temporal.py yearly --years-ago 10
    ${python} html_temporal.py yearly --years-ago 11
    ${python} html_temporal.py yearly --years-ago 12
    ${python} html_temporal.py yearly --years-ago 13
    ${python} html_temporal.py yearly --years-ago 14
    ${python} html_temporal.py yearly --years-ago 15
    ${python} html_temporal.py yearly --years-ago 16
    ${python} html_temporal.py yearly --years-ago 17
    ${python} html_temporal.py yearly --years-ago 18
    exit 0
fi

# Mensuales
# 2025
if [[ $1 == "mensuales" ]]; then
    ${python} html_temporal.py monthly --month 10 --year 2025
    ${python} html_temporal.py monthly --month 09 --year 2025
    ${python} html_temporal.py monthly --month 08 --year 2025
    ${python} html_temporal.py monthly --month 07 --year 2025
    ${python} html_temporal.py monthly --month 06 --year 2025
    ${python} html_temporal.py monthly --month 05 --year 2025
    ${python} html_temporal.py monthly --month 04 --year 2025
    ${python} html_temporal.py monthly --month 03 --year 2025
    ${python} html_temporal.py monthly --month 02 --year 2025
    ${python} html_temporal.py monthly --month 01 --year 2025

    # 2024
    ${python} html_temporal.py monthly --month 12 --year 2024
    ${python} html_temporal.py monthly --month 11 --year 2024
    ${python} html_temporal.py monthly --month 10 --year 2024
    ${python} html_temporal.py monthly --month 09 --year 2024
    ${python} html_temporal.py monthly --month 08 --year 2024
    ${python} html_temporal.py monthly --month 07 --year 2024
    ${python} html_temporal.py monthly --month 06 --year 2024
    ${python} html_temporal.py monthly --month 05 --year 2024
    ${python} html_temporal.py monthly --month 04 --year 2024
    ${python} html_temporal.py monthly --month 03 --year 2024
    ${python} html_temporal.py monthly --month 02 --year 2024
    ${python} html_temporal.py monthly --month 01 --year 2024

    # 2023
    ${python} html_temporal.py monthly --month 12 --year 2023
    ${python} html_temporal.py monthly --month 11 --year 2023
    ${python} html_temporal.py monthly --month 10 --year 2023
    ${python} html_temporal.py monthly --month 09 --year 2023
    ${python} html_temporal.py monthly --month 08 --year 2023
    ${python} html_temporal.py monthly --month 07 --year 2023
    ${python} html_temporal.py monthly --month 06 --year 2023
    ${python} html_temporal.py monthly --month 05 --year 2023
    ${python} html_temporal.py monthly --month 04 --year 2023
    ${python} html_temporal.py monthly --month 03 --year 2023
    ${python} html_temporal.py monthly --month 02 --year 2023
    ${python} html_temporal.py monthly --month 01 --year 2023

    # 2022
    ${python} html_temporal.py monthly --month 12 --year 2022
    ${python} html_temporal.py monthly --month 11 --year 2022
    ${python} html_temporal.py monthly --month 10 --year 2022
    ${python} html_temporal.py monthly --month 09 --year 2022
    ${python} html_temporal.py monthly --month 08 --year 2022
    ${python} html_temporal.py monthly --month 07 --year 2022
    ${python} html_temporal.py monthly --month 06 --year 2022
    ${python} html_temporal.py monthly --month 05 --year 2022
    ${python} html_temporal.py monthly --month 04 --year 2022
    ${python} html_temporal.py monthly --month 03 --year 2022
    ${python} html_temporal.py monthly --month 02 --year 2022
    ${python} html_temporal.py monthly --month 01 --year 2022

    # 2021
    ${python} html_temporal.py monthly --month 12 --year 2021
    ${python} html_temporal.py monthly --month 11 --year 2021
    ${python} html_temporal.py monthly --month 10 --year 2021
    ${python} html_temporal.py monthly --month 09 --year 2021
    ${python} html_temporal.py monthly --month 08 --year 2021
    ${python} html_temporal.py monthly --month 07 --year 2021
    ${python} html_temporal.py monthly --month 06 --year 2021
    ${python} html_temporal.py monthly --month 05 --year 2021
    ${python} html_temporal.py monthly --month 04 --year 2021
    ${python} html_temporal.py monthly --month 03 --year 2021
    ${python} html_temporal.py monthly --month 02 --year 2021
    ${python} html_temporal.py monthly --month 01 --year 2021

    # 2020
    ${python} html_temporal.py monthly --month 12 --year 2020
    ${python} html_temporal.py monthly --month 11 --year 2020
    ${python} html_temporal.py monthly --month 10 --year 2020
    ${python} html_temporal.py monthly --month 09 --year 2020
    ${python} html_temporal.py monthly --month 08 --year 2020
    ${python} html_temporal.py monthly --month 07 --year 2020
    ${python} html_temporal.py monthly --month 06 --year 2020
    ${python} html_temporal.py monthly --month 05 --year 2020
    ${python} html_temporal.py monthly --month 04 --year 2020
    ${python} html_temporal.py monthly --month 03 --year 2020
    ${python} html_temporal.py monthly --month 02 --year 2020
    ${python} html_temporal.py monthly --month 01 --year 2020

    # 2019
    ${python} html_temporal.py monthly --month 12 --year 2019
    ${python} html_temporal.py monthly --month 11 --year 2019
    ${python} html_temporal.py monthly --month 10 --year 2019
    ${python} html_temporal.py monthly --month 09 --year 2019
    ${python} html_temporal.py monthly --month 08 --year 2019
    ${python} html_temporal.py monthly --month 07 --year 2019
    ${python} html_temporal.py monthly --month 06 --year 2019
    ${python} html_temporal.py monthly --month 05 --year 2019
    ${python} html_temporal.py monthly --month 04 --year 2019
    ${python} html_temporal.py monthly --month 03 --year 2019
    ${python} html_temporal.py monthly --month 02 --year 2019
    ${python} html_temporal.py monthly --month 01 --year 2019
    # 2018
    ${python} html_temporal.py monthly --month 12 --year 2018
    ${python} html_temporal.py monthly --month 11 --year 2018
    ${python} html_temporal.py monthly --month 10 --year 2018
    ${python} html_temporal.py monthly --month 09 --year 2018
    ${python} html_temporal.py monthly --month 08 --year 2018
    ${python} html_temporal.py monthly --month 07 --year 2018
    ${python} html_temporal.py monthly --month 06 --year 2018
    ${python} html_temporal.py monthly --month 05 --year 2018
    ${python} html_temporal.py monthly --month 04 --year 2018
    ${python} html_temporal.py monthly --month 03 --year 2018
    ${python} html_temporal.py monthly --month 02 --year 2018
    ${python} html_temporal.py monthly --month 01 --year 2018
    # 2017
    ${python} html_temporal.py monthly --month 12 --year 2017
    ${python} html_temporal.py monthly --month 11 --year 2017
    ${python} html_temporal.py monthly --month 10 --year 2017
    ${python} html_temporal.py monthly --month 09 --year 2017
    ${python} html_temporal.py monthly --month 08 --year 2017
    ${python} html_temporal.py monthly --month 07 --year 2017
    ${python} html_temporal.py monthly --month 06 --year 2017
    ${python} html_temporal.py monthly --month 05 --year 2017
    ${python} html_temporal.py monthly --month 04 --year 2017
    ${python} html_temporal.py monthly --month 03 --year 2017
    ${python} html_temporal.py monthly --month 02 --year 2017
    ${python} html_temporal.py monthly --month 01 --year 2017
    # 2016
    ${python} html_temporal.py monthly --month 12 --year 2016
    ${python} html_temporal.py monthly --month 11 --year 2016
    ${python} html_temporal.py monthly --month 10 --year 2016
    ${python} html_temporal.py monthly --month 09 --year 2016
    ${python} html_temporal.py monthly --month 08 --year 2016
    ${python} html_temporal.py monthly --month 07 --year 2016
    ${python} html_temporal.py monthly --month 06 --year 2016
    ${python} html_temporal.py monthly --month 05 --year 2016
    ${python} html_temporal.py monthly --month 04 --year 2016
    ${python} html_temporal.py monthly --month 03 --year 2016
    ${python} html_temporal.py monthly --month 02 --year 2016
    ${python} html_temporal.py monthly --month 01 --year 2016
    # 2015
    ${python} html_temporal.py monthly --month 12 --year 2015
    ${python} html_temporal.py monthly --month 11 --year 2015
    ${python} html_temporal.py monthly --month 10 --year 2015
    ${python} html_temporal.py monthly --month 09 --year 2015
    ${python} html_temporal.py monthly --month 08 --year 2015
    ${python} html_temporal.py monthly --month 07 --year 2015
    ${python} html_temporal.py monthly --month 06 --year 2015
    ${python} html_temporal.py monthly --month 05 --year 2015
    ${python} html_temporal.py monthly --month 04 --year 2015
    ${python} html_temporal.py monthly --month 03 --year 2015
    ${python} html_temporal.py monthly --month 02 --year 2015
    ${python} html_temporal.py monthly --month 01 --year 2015
    # 2014
    ${python} html_temporal.py monthly --month 12 --year 2014
    ${python} html_temporal.py monthly --month 11 --year 2014
    ${python} html_temporal.py monthly --month 10 --year 2014
    ${python} html_temporal.py monthly --month 09 --year 2014
    ${python} html_temporal.py monthly --month 08 --year 2014
    ${python} html_temporal.py monthly --month 07 --year 2014
    ${python} html_temporal.py monthly --month 06 --year 2014
    ${python} html_temporal.py monthly --month 05 --year 2014
    ${python} html_temporal.py monthly --month 04 --year 2014
    ${python} html_temporal.py monthly --month 03 --year 2014
    ${python} html_temporal.py monthly --month 02 --year 2014
    ${python} html_temporal.py monthly --month 01 --year 2014

    # 2013
    ${python} html_temporal.py monthly --month 12 --year 2013
    ${python} html_temporal.py monthly --month 11 --year 2013
    ${python} html_temporal.py monthly --month 10 --year 2013
    ${python} html_temporal.py monthly --month 09 --year 2013
    ${python} html_temporal.py monthly --month 08 --year 2013
    ${python} html_temporal.py monthly --month 07 --year 2013
    ${python} html_temporal.py monthly --month 06 --year 2013
    ${python} html_temporal.py monthly --month 05 --year 2013
    ${python} html_temporal.py monthly --month 04 --year 2013
    ${python} html_temporal.py monthly --month 03 --year 2013
    ${python} html_temporal.py monthly --month 02 --year 2013
    ${python} html_temporal.py monthly --month 01 --year 2013

    # 2012
    ${python} html_temporal.py monthly --month 12 --year 2012
    ${python} html_temporal.py monthly --month 11 --year 2012
    ${python} html_temporal.py monthly --month 10 --year 2012
    ${python} html_temporal.py monthly --month 09 --year 2012
    ${python} html_temporal.py monthly --month 08 --year 2012
    ${python} html_temporal.py monthly --month 07 --year 2012
    ${python} html_temporal.py monthly --month 06 --year 2012
    ${python} html_temporal.py monthly --month 05 --year 2012
    ${python} html_temporal.py monthly --month 04 --year 2012
    ${python} html_temporal.py monthly --month 03 --year 2012
    ${python} html_temporal.py monthly --month 02 --year 2012
    ${python} html_temporal.py monthly --month 01 --year 2012
    # 2011
    ${python} html_temporal.py monthly --month 12 --year 2011
    ${python} html_temporal.py monthly --month 11 --year 2011
    ${python} html_temporal.py monthly --month 10 --year 2011
    ${python} html_temporal.py monthly --month 09 --year 2011
    ${python} html_temporal.py monthly --month 08 --year 2011
    ${python} html_temporal.py monthly --month 07 --year 2011
    ${python} html_temporal.py monthly --month 06 --year 2011
    ${python} html_temporal.py monthly --month 05 --year 2011
    ${python} html_temporal.py monthly --month 04 --year 2011
    ${python} html_temporal.py monthly --month 03 --year 2011
    ${python} html_temporal.py monthly --month 02 --year 2011
    ${python} html_temporal.py monthly --month 01 --year 2011
    # 2010
    ${python} html_temporal.py monthly --month 12 --year 2010
    ${python} html_temporal.py monthly --month 11 --year 2010
    ${python} html_temporal.py monthly --month 10 --year 2010
    ${python} html_temporal.py monthly --month 09 --year 2010
    ${python} html_temporal.py monthly --month 08 --year 2010
    ${python} html_temporal.py monthly --month 07 --year 2010
    ${python} html_temporal.py monthly --month 06 --year 2010
    ${python} html_temporal.py monthly --month 05 --year 2010
    ${python} html_temporal.py monthly --month 04 --year 2010
    ${python} html_temporal.py monthly --month 03 --year 2010
    ${python} html_temporal.py monthly --month 02 --year 2010
    ${python} html_temporal.py monthly --month 01 --year 2010
    # 2009
    ${python} html_temporal.py monthly --month 12 --year 2009
    ${python} html_temporal.py monthly --month 11 --year 2009
    ${python} html_temporal.py monthly --month 10 --year 2009
    ${python} html_temporal.py monthly --month 09 --year 2009
    ${python} html_temporal.py monthly --month 08 --year 2009
    ${python} html_temporal.py monthly --month 07 --year 2009
    ${python} html_temporal.py monthly --month 06 --year 2009
    ${python} html_temporal.py monthly --month 05 --year 2009
    ${python} html_temporal.py monthly --month 04 --year 2009
    ${python} html_temporal.py monthly --month 03 --year 2009
    ${python} html_temporal.py monthly --month 02 --year 2009
    ${python} html_temporal.py monthly --month 01 --year 2009
    # 2008
    ${python} html_temporal.py monthly --month 12 --year 2008
    ${python} html_temporal.py monthly --month 11 --year 2008
    ${python} html_temporal.py monthly --month 10 --year 2008
    ${python} html_temporal.py monthly --month 09 --year 2008
    ${python} html_temporal.py monthly --month 08 --year 2008
    ${python} html_temporal.py monthly --month 07 --year 2008
    ${python} html_temporal.py monthly --month 06 --year 2008
    ${python} html_temporal.py monthly --month 05 --year 2008
    ${python} html_temporal.py monthly --month 04 --year 2008
    ${python} html_temporal.py monthly --month 03 --year 2008
    ${python} html_temporal.py monthly --month 02 --year 2008
    ${python} html_temporal.py monthly --month 01 --year 2008
    # 2007
    ${python} html_temporal.py monthly --month 12 --year 2007
    ${python} html_temporal.py monthly --month 11 --year 2007
    ${python} html_temporal.py monthly --month 10 --year 2007
    ${python} html_temporal.py monthly --month 09 --year 2007
    ${python} html_temporal.py monthly --month 08 --year 2007
    exit 0
fi

# Semanales
if [[ $1 == "semanales" ]]; then
    rm docs/esta-semana.html docs/semana-pasada.html docs/hace-dos-semanas.html docs/hace-tres-semanas.html
    ${python} html_temporal.py weekly
    ${python} html_temporal.py weekly --week-offset 1
    ${python} html_temporal.py weekly --week-offset 2
    ${python} html_temporal.py weekly --week-offset 3
    exit 0
fi

${python} html_index.py

gtd
