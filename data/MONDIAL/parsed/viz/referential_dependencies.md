# Referential Dependencies

- database: `MONDIAL`
- dialect: `None`

## Tables

| table | rows | columns | primary_key |
|---|---:|---|---|
| country | 246 | name, code, capital, province, area, population | code |
| city | 3427 | name, country, province, population, latitude, longitude, elevation | province, country, name |
| province | 1648 | name, country, population, area, capital, capprov | country, name |
| economy | 246 | country, gdp, agriculture, service, industry, inflation, unemployment | country |
| population | 246 | country, population_growth, infant_mortality | country |
| politics | 246 | country, independence, wasdependent, dependent, government | country |
| religion | 956 | country, name, percentage | country, name |
| ethnicgroup | 1472 | country, name, percentage | country, name |
| spoken | 1416 | country, language, percentage | language, country |
| language | 892 | name, superlanguage | name |
| countrypops | 2285 | country, year, population | country, year |
| countryothername | 3 | country, othername | othername, country |
| countrylocalname | 199 | country, localname | country |
| provpops | 5858 | province, country, year, population | province, country, year |
| provinceothername | 91 | province, country, othername | province, othername, country |
| provincelocalname | 381 | province, country, localname | province, country |
| citypops | 12336 | city, country, province, year, population | province, country, city, year |
| cityothername | 557 | city, country, province, othername | province, othername, country, city |
| citylocalname | 609 | city, country, province, localname | province, country, city |
| continent | 6 | name, area | name |
| borders | 326 | country1, country2, length | country2, country1 |
| encompasses | 251 | country, continent, percentage | country, continent |
| organization | 169 | abbreviation, name, city, country, province, established | abbreviation |
| ismember | 10091 | country, organization, type | organization, country |
| mountain | 587 | name, mountains, elevation, type, coordinates | name |
| desert | 66 | name, area, coordinates | name |
| island | 382 | name, islands, area, elevation, type, coordinates | name |
| lake | 225 | name, river, area, elevation, depth, height, type, coordinates | name |
| sea | 56 | name, area, depth | name |
| river | 665 | name, river, lake, sea, length, area, source, mountains, sourceelevation, estuary, estuaryelevation | name |
| riverthrough | 74 | river, lake | river, lake |
| geo_mountain | 713 | mountain, country, province | province, country, mountain |
| geo_desert | 185 | desert, country, province | province, country, desert |
| geo_island | 501 | island, country, province | province, country, island |
| geo_river | 2033 | river, country, province | province, river, country |
| geo_sea | 944 | sea, country, province | province, country, sea |
| geo_lake | 401 | lake, country, province | province, country, lake |
| geo_source | 686 | river, country, province | province, river, country |
| geo_estuary | 759 | river, country, province | province, river, country |
| mergeswith | 92 | sea1, sea2 | sea2, sea1 |
| located | 1774 | city, province, country, river, lake, sea |  |
| locatedon | 510 | city, province, country, island | city, province, country, island |
| islandin | 514 | island, sea, lake, river |  |
| mountainonisland | 203 | mountain, island | island, mountain |
| lakeonisland | 25 | lake, island | lake, island |
| riveronisland | 46 | river, island | river, island |
| airport | 1304 | iatacode, name, country, city, province, island, latitude, longitude, elevation, gmtoffset | iatacode |

## Foreign Keys

| child_table | child_columns | parent_table | parent_columns | on_delete | on_update |
|---|---|---|---|---|---|
| country | capital, code, province | city | name, country, province | None | None |
| city | province, country | province | name, country | None | None |
| province | country | country | code | None | None |
| province | capital, country, capprov | city | name, country, province | None | None |
| economy | country | country | code | None | None |
| population | country | country | code | None | None |
| politics | country | country | code | None | None |
| politics | dependent | country | code | None | None |
| religion | country | country | code | None | None |
| ethnicgroup | country | country | code | None | None |
| spoken | country | country | code | None | None |
| spoken | language | language | name | None | None |
| language | superlanguage | language | name | None | None |
| countrypops | country | country | code | None | None |
| countryothername | country | country | code | None | None |
| countrylocalname | country | country | code | None | None |
| provpops | province, country | province | name, country | None | None |
| provinceothername | province, country | province | name, country | None | None |
| provincelocalname | province, country | province | name, country | None | None |
| citypops | city, country, province | city | name, country, province | None | None |
| cityothername | city, country, province | city | name, country, province | None | None |
| citylocalname | city, country, province | city | name, country, province | None | None |
| borders | country1 | country | code | None | None |
| borders | country2 | country | code | None | None |
| encompasses | country | country | code | None | None |
| encompasses | continent | continent | name | None | None |
| organization | city, country, province | city | name, country, province | None | None |
| ismember | country | country | code | None | None |
| ismember | organization | organization | abbreviation | None | None |
| river | river | river | name | None | None |
| river | lake | lake | name | None | None |
| river | sea | sea | name | None | None |
| lake | river | river | name | None | None |
| riverthrough | river | river | name | None | None |
| riverthrough | lake | lake | name | None | None |
| mergeswith | sea1 | sea | name | None | None |
| mergeswith | sea2 | sea | name | None | None |
| geo_mountain | mountain | mountain | name | None | None |
| geo_mountain | province, country | province | name, country | None | None |
| geo_desert | desert | desert | name | None | None |
| geo_desert | province, country | province | name, country | None | None |
| geo_island | island | island | name | None | None |
| geo_island | province, country | province | name, country | None | None |
| geo_river | river | river | name | None | None |
| geo_river | province, country | province | name, country | None | None |
| geo_sea | sea | sea | name | None | None |
| geo_sea | province, country | province | name, country | None | None |
| geo_lake | lake | lake | name | None | None |
| geo_lake | province, country | province | name, country | None | None |
| geo_source | river | river | name | None | None |
| geo_source | province, country | province | name, country | None | None |
| geo_estuary | river | river | name | None | None |
| geo_estuary | province, country | province | name, country | None | None |
| located | city, country, province | city | name, country, province | None | None |
| located | river | river | name | None | None |
| located | lake | lake | name | None | None |
| located | sea | sea | name | None | None |
| locatedon | city, country, province | city | name, country, province | None | None |
| locatedon | island | island | name | None | None |
| islandin | island | island | name | None | None |
| islandin | sea | sea | name | None | None |
| islandin | lake | lake | name | None | None |
| islandin | river | river | name | None | None |
| mountainonisland | mountain | mountain | name | None | None |
| mountainonisland | island | island | name | None | None |
| lakeonisland | lake | lake | name | None | None |
| lakeonisland | island | island | name | None | None |
| riveronisland | river | river | name | None | None |
| riveronisland | island | island | name | None | None |
| airport | country | country | code | None | None |
| airport | city, country, province | city | name, country, province | None | None |
| airport | island | island | name | None | None |
