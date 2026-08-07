#!/bin/bash
# Fetch gogov matkapital pages for the 15 regions and extract the amount section
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
mkdir -p /tmp/gogov
declare -A R=(
 [mo]=Московская_область [spb]=Санкт-Петербург [lo]=Ленинградская_область [rt]=Татарстан
 [krd]=Краснодарский_край [svo]=Свердловская_область [nso]=Новосибирская_область [rst]=Ростовская_область
 [ngo]=Нижегородская_область [bash]=Башкортостан [chlb]=Челябинская_область [smr]=Самарская_область
 [kry]=Красноярский_край [prim]=Приморский_край [vrzh]=Воронежская_область
)
for slug in mo spb lo rt krd svo nso rst ngo bash chlb smr kry prim vrzh; do
  name=${R[$slug]}
  curl -s -m 25 -A "$UA" -o /tmp/gogov/$slug.html "https://gogov.ru/mf-region/$slug"
  echo "fetched $slug ($name) size=$(wc -c < /tmp/gogov/$slug.html)"
  sleep 8
done
echo DONE
