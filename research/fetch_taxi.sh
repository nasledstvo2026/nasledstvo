#!/bin/bash
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
mkdir -p /tmp/gogov/taxi
for slug in mo spb lo rt krd svo nso rst ngo bash chlb smr kry prim vrzh; do
  curl -s -m 25 -A "$UA" -o /tmp/gogov/taxi/$slug.html "https://gogov.ru/soc-taxi/$slug"
  echo "fetched $slug $(wc -c < /tmp/gogov/taxi/$slug.html)"
  sleep 6
done
echo TAXI_DONE
