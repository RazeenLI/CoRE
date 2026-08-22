-- Foreign keys transcribed from MONDIAL's official referential-dependency
-- diagram (Mondial-III, 2022). The official PostgreSQL schema does not ship
-- executable FOREIGN KEY declarations.
-- Source: https://www.dbis.informatik.uni-goettingen.de/Mondial/mondial-abh.pdf

ALTER TABLE Country ADD CONSTRAINT CountryCapitalFK
  FOREIGN KEY (Capital, Code, Province) REFERENCES City (Name, Country, Province);

ALTER TABLE City ADD CONSTRAINT CityProvinceFK
  FOREIGN KEY (Province, Country) REFERENCES Province (Name, Country);

ALTER TABLE Province ADD CONSTRAINT ProvinceCountryFK
  FOREIGN KEY (Country) REFERENCES Country (Code);
ALTER TABLE Province ADD CONSTRAINT ProvinceCapitalFK
  FOREIGN KEY (Capital, Country, CapProv) REFERENCES City (Name, Country, Province);

ALTER TABLE Economy ADD CONSTRAINT EconomyCountryFK
  FOREIGN KEY (Country) REFERENCES Country (Code);
ALTER TABLE Population ADD CONSTRAINT PopulationCountryFK
  FOREIGN KEY (Country) REFERENCES Country (Code);
ALTER TABLE Politics ADD CONSTRAINT PoliticsCountryFK
  FOREIGN KEY (Country) REFERENCES Country (Code);
ALTER TABLE Politics ADD CONSTRAINT PoliticsDependentFK
  FOREIGN KEY (Dependent) REFERENCES Country (Code);
-- Politics.WasDependent is shown as a dependency in the official diagram, but
-- contains historical entities and a mixture of names/codes that are absent
-- from Country. It is intentionally not encoded as an executable foreign key.

ALTER TABLE Religion ADD CONSTRAINT ReligionCountryFK
  FOREIGN KEY (Country) REFERENCES Country (Code);
ALTER TABLE EthnicGroup ADD CONSTRAINT EthnicGroupCountryFK
  FOREIGN KEY (Country) REFERENCES Country (Code);
ALTER TABLE Spoken ADD CONSTRAINT SpokenCountryFK
  FOREIGN KEY (Country) REFERENCES Country (Code);
ALTER TABLE Spoken ADD CONSTRAINT SpokenLanguageFK
  FOREIGN KEY (Language) REFERENCES Language (Name);
ALTER TABLE Language ADD CONSTRAINT LanguageSuperlanguageFK
  FOREIGN KEY (Superlanguage) REFERENCES Language (Name);

ALTER TABLE Countrypops ADD CONSTRAINT CountrypopsCountryFK
  FOREIGN KEY (Country) REFERENCES Country (Code);
ALTER TABLE Countryothername ADD CONSTRAINT CountryothernameCountryFK
  FOREIGN KEY (Country) REFERENCES Country (Code);
ALTER TABLE Countrylocalname ADD CONSTRAINT CountrylocalnameCountryFK
  FOREIGN KEY (Country) REFERENCES Country (Code);
ALTER TABLE Provpops ADD CONSTRAINT ProvpopsProvinceFK
  FOREIGN KEY (Province, Country) REFERENCES Province (Name, Country);
ALTER TABLE Provinceothername ADD CONSTRAINT ProvinceothernameProvinceFK
  FOREIGN KEY (Province, Country) REFERENCES Province (Name, Country);
ALTER TABLE Provincelocalname ADD CONSTRAINT ProvincelocalnameProvinceFK
  FOREIGN KEY (Province, Country) REFERENCES Province (Name, Country);
ALTER TABLE Citypops ADD CONSTRAINT CitypopsCityFK
  FOREIGN KEY (City, Country, Province) REFERENCES City (Name, Country, Province);
ALTER TABLE Cityothername ADD CONSTRAINT CityothernameCityFK
  FOREIGN KEY (City, Country, Province) REFERENCES City (Name, Country, Province);
ALTER TABLE Citylocalname ADD CONSTRAINT CitylocalnameCityFK
  FOREIGN KEY (City, Country, Province) REFERENCES City (Name, Country, Province);

ALTER TABLE borders ADD CONSTRAINT BordersCountry1FK
  FOREIGN KEY (Country1) REFERENCES Country (Code);
ALTER TABLE borders ADD CONSTRAINT BordersCountry2FK
  FOREIGN KEY (Country2) REFERENCES Country (Code);
ALTER TABLE encompasses ADD CONSTRAINT EncompassesCountryFK
  FOREIGN KEY (Country) REFERENCES Country (Code);
ALTER TABLE encompasses ADD CONSTRAINT EncompassesContinentFK
  FOREIGN KEY (Continent) REFERENCES Continent (Name);
ALTER TABLE Organization ADD CONSTRAINT OrganizationCityFK
  FOREIGN KEY (City, Country, Province) REFERENCES City (Name, Country, Province);
ALTER TABLE isMember ADD CONSTRAINT IsMemberCountryFK
  FOREIGN KEY (Country) REFERENCES Country (Code);
ALTER TABLE isMember ADD CONSTRAINT IsMemberOrganizationFK
  FOREIGN KEY (Organization) REFERENCES Organization (Abbreviation);

ALTER TABLE River ADD CONSTRAINT RiverRiverFK
  FOREIGN KEY (River) REFERENCES River (Name);
ALTER TABLE River ADD CONSTRAINT RiverLakeFK
  FOREIGN KEY (Lake) REFERENCES Lake (Name);
ALTER TABLE River ADD CONSTRAINT RiverSeaFK
  FOREIGN KEY (Sea) REFERENCES Sea (Name);
ALTER TABLE Lake ADD CONSTRAINT LakeRiverFK
  FOREIGN KEY (River) REFERENCES River (Name);
ALTER TABLE RiverThrough ADD CONSTRAINT RiverThroughRiverFK
  FOREIGN KEY (River) REFERENCES River (Name);
ALTER TABLE RiverThrough ADD CONSTRAINT RiverThroughLakeFK
  FOREIGN KEY (Lake) REFERENCES Lake (Name);
ALTER TABLE mergesWith ADD CONSTRAINT MergesWithSea1FK
  FOREIGN KEY (Sea1) REFERENCES Sea (Name);
ALTER TABLE mergesWith ADD CONSTRAINT MergesWithSea2FK
  FOREIGN KEY (Sea2) REFERENCES Sea (Name);

ALTER TABLE geo_Mountain ADD CONSTRAINT GeoMountainMountainFK
  FOREIGN KEY (Mountain) REFERENCES Mountain (Name);
ALTER TABLE geo_Mountain ADD CONSTRAINT GeoMountainProvinceFK
  FOREIGN KEY (Province, Country) REFERENCES Province (Name, Country);
ALTER TABLE geo_Desert ADD CONSTRAINT GeoDesertDesertFK
  FOREIGN KEY (Desert) REFERENCES Desert (Name);
ALTER TABLE geo_Desert ADD CONSTRAINT GeoDesertProvinceFK
  FOREIGN KEY (Province, Country) REFERENCES Province (Name, Country);
ALTER TABLE geo_Island ADD CONSTRAINT GeoIslandIslandFK
  FOREIGN KEY (Island) REFERENCES Island (Name);
ALTER TABLE geo_Island ADD CONSTRAINT GeoIslandProvinceFK
  FOREIGN KEY (Province, Country) REFERENCES Province (Name, Country);
ALTER TABLE geo_River ADD CONSTRAINT GeoRiverRiverFK
  FOREIGN KEY (River) REFERENCES River (Name);
ALTER TABLE geo_River ADD CONSTRAINT GeoRiverProvinceFK
  FOREIGN KEY (Province, Country) REFERENCES Province (Name, Country);
ALTER TABLE geo_Sea ADD CONSTRAINT GeoSeaSeaFK
  FOREIGN KEY (Sea) REFERENCES Sea (Name);
ALTER TABLE geo_Sea ADD CONSTRAINT GeoSeaProvinceFK
  FOREIGN KEY (Province, Country) REFERENCES Province (Name, Country);
ALTER TABLE geo_Lake ADD CONSTRAINT GeoLakeLakeFK
  FOREIGN KEY (Lake) REFERENCES Lake (Name);
ALTER TABLE geo_Lake ADD CONSTRAINT GeoLakeProvinceFK
  FOREIGN KEY (Province, Country) REFERENCES Province (Name, Country);
ALTER TABLE geo_Source ADD CONSTRAINT GeoSourceRiverFK
  FOREIGN KEY (River) REFERENCES River (Name);
ALTER TABLE geo_Source ADD CONSTRAINT GeoSourceProvinceFK
  FOREIGN KEY (Province, Country) REFERENCES Province (Name, Country);
ALTER TABLE geo_Estuary ADD CONSTRAINT GeoEstuaryRiverFK
  FOREIGN KEY (River) REFERENCES River (Name);
ALTER TABLE geo_Estuary ADD CONSTRAINT GeoEstuaryProvinceFK
  FOREIGN KEY (Province, Country) REFERENCES Province (Name, Country);

ALTER TABLE located ADD CONSTRAINT LocatedCityFK
  FOREIGN KEY (City, Country, Province) REFERENCES City (Name, Country, Province);
ALTER TABLE located ADD CONSTRAINT LocatedRiverFK
  FOREIGN KEY (River) REFERENCES River (Name);
ALTER TABLE located ADD CONSTRAINT LocatedLakeFK
  FOREIGN KEY (Lake) REFERENCES Lake (Name);
ALTER TABLE located ADD CONSTRAINT LocatedSeaFK
  FOREIGN KEY (Sea) REFERENCES Sea (Name);
ALTER TABLE locatedOn ADD CONSTRAINT LocatedOnCityFK
  FOREIGN KEY (City, Country, Province) REFERENCES City (Name, Country, Province);
ALTER TABLE locatedOn ADD CONSTRAINT LocatedOnIslandFK
  FOREIGN KEY (Island) REFERENCES Island (Name);
ALTER TABLE islandIn ADD CONSTRAINT IslandInIslandFK
  FOREIGN KEY (Island) REFERENCES Island (Name);
ALTER TABLE islandIn ADD CONSTRAINT IslandInSeaFK
  FOREIGN KEY (Sea) REFERENCES Sea (Name);
ALTER TABLE islandIn ADD CONSTRAINT IslandInLakeFK
  FOREIGN KEY (Lake) REFERENCES Lake (Name);
ALTER TABLE islandIn ADD CONSTRAINT IslandInRiverFK
  FOREIGN KEY (River) REFERENCES River (Name);
ALTER TABLE MountainOnIsland ADD CONSTRAINT MountainOnIslandMountainFK
  FOREIGN KEY (Mountain) REFERENCES Mountain (Name);
ALTER TABLE MountainOnIsland ADD CONSTRAINT MountainOnIslandIslandFK
  FOREIGN KEY (Island) REFERENCES Island (Name);
ALTER TABLE LakeOnIsland ADD CONSTRAINT LakeOnIslandLakeFK
  FOREIGN KEY (Lake) REFERENCES Lake (Name);
ALTER TABLE LakeOnIsland ADD CONSTRAINT LakeOnIslandIslandFK
  FOREIGN KEY (Island) REFERENCES Island (Name);
ALTER TABLE RiverOnIsland ADD CONSTRAINT RiverOnIslandRiverFK
  FOREIGN KEY (River) REFERENCES River (Name);
ALTER TABLE RiverOnIsland ADD CONSTRAINT RiverOnIslandIslandFK
  FOREIGN KEY (Island) REFERENCES Island (Name);
ALTER TABLE Airport ADD CONSTRAINT AirportCountryFK
  FOREIGN KEY (Country) REFERENCES Country (Code);
ALTER TABLE Airport ADD CONSTRAINT AirportCityFK
  FOREIGN KEY (City, Country, Province) REFERENCES City (Name, Country, Province);
ALTER TABLE Airport ADD CONSTRAINT AirportIslandFK
  FOREIGN KEY (Island) REFERENCES Island (Name);
